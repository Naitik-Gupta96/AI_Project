"""
In-process Hugging Face ``transformers`` provider with dynamic batching.

Agents call ``generate`` from many threads (parallel sessions, parallel
agents). A single worker thread owns the model: it collects up to
``batch_size`` waiting requests (waiting at most ``batch_wait`` seconds for a
batch to fill), runs one left-padded greedy ``generate`` call for all of them,
and hands each caller its own completion and token counts.

If ``lm-format-enforcer`` is installed, decoding is constrained to the
request's JSON schema; otherwise the schema is only in the prompt and the
parser and grammar catch malformed output.

    pip install -e ".[hf]"
    HFTransformersProvider("Qwen/Qwen2.5-7B-Instruct", load_in_4bit=True)
"""

import json
import queue
import threading
from concurrent.futures import Future
from typing import Any

from ai_project.llm import prompts
from ai_project.llm.base import LLMProvider, LLMProviderError, LLMRequest, LLMResponse


class HFTransformersProvider(LLMProvider):
    """
    Args:
        model_name: Hugging Face model id
        max_new_tokens: Completion budget per request
        batch_size: Requests per ``generate`` call
        batch_wait: Seconds to wait for a batch to fill
        load_in_4bit: Load with bitsandbytes 4-bit quantization (fits a 7B model in ~6 GB)
        model, tokenizer: Already loaded objects (skips loading; used by tests)
    """

    name = "hf"
    deterministic = True  # greedy decoding

    def __init__(
        self,
        model_name: str = "Qwen/Qwen2.5-7B-Instruct",
        max_new_tokens: int = 700,
        batch_size: int = 8,
        batch_wait: float = 0.02,
        load_in_4bit: bool = False,
        model: Any = None,
        tokenizer: Any = None,
    ) -> None:
        self.model_name = model_name
        self.max_new_tokens = max_new_tokens
        self.batch_size = batch_size
        self.batch_wait = batch_wait
        self.load_in_4bit = load_in_4bit
        self._model = model
        self._tokenizer = tokenizer
        self._queue: queue.Queue[tuple[LLMRequest, Future]] = queue.Queue()
        self._worker: threading.Thread | None = None
        self._lock = threading.Lock()
        self.batches: list[int] = []  # sizes of the batches run so far

    def describe(self) -> dict[str, Any]:
        return {"name": self.name, "deterministic": self.deterministic,
                "model": self.model_name, "max_new_tokens": self.max_new_tokens,
                "batch_size": self.batch_size, "load_in_4bit": self.load_in_4bit}

    def is_available(self) -> bool:
        try:
            import torch  # noqa: F401
            import transformers  # noqa: F401
        except ImportError:
            return self._model is not None
        return True

    def generate(self, request: LLMRequest) -> LLMResponse:
        self._ensure_worker()
        future: Future = Future()
        self._queue.put((request, future))
        return future.result()

    # ------------------------------------------------------------------ worker

    def _ensure_worker(self) -> None:
        with self._lock:
            if self._worker is None or not self._worker.is_alive():
                self._load()
                self._worker = threading.Thread(target=self._loop, daemon=True,
                                                name="hf-batcher")
                self._worker.start()

    def _load(self) -> None:
        if self._model is not None:
            return
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as exc:
            raise LLMProviderError("HFTransformersProvider needs: pip install -e '.[hf]'") from exc
        kwargs: dict[str, Any] = {"device_map": "auto", "torch_dtype": torch.bfloat16}
        if self.load_in_4bit:
            from transformers import BitsAndBytesConfig
            kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16)
        self._tokenizer = AutoTokenizer.from_pretrained(self.model_name, padding_side="left")
        if self._tokenizer.pad_token is None:
            self._tokenizer.pad_token = self._tokenizer.eos_token
        self._model = AutoModelForCausalLM.from_pretrained(self.model_name, **kwargs)
        self._model.eval()

    def _loop(self) -> None:
        while True:
            batch = [self._queue.get()]
            while len(batch) < self.batch_size:
                try:
                    batch.append(self._queue.get(timeout=self.batch_wait))
                except queue.Empty:
                    break
            self.batches.append(len(batch))
            try:
                responses = self._run([r for r, _ in batch])
            except Exception as exc:  # deliver the failure to every waiting caller
                for _, future in batch:
                    future.set_exception(LLMProviderError(f"generation failed: {exc}"))
                continue
            for (_, future), response in zip(batch, responses, strict=True):
                future.set_result(response)

    def _run(self, requests: list[LLMRequest]) -> list[LLMResponse]:
        tok = self._tokenizer
        texts = [
            tok.apply_chat_template(
                [{"role": "system", "content": r.system}, {"role": "user", "content": r.prompt}],
                tokenize=False, add_generation_prompt=True)
            for r in requests
        ]
        inputs = tok(texts, return_tensors="pt", padding=True)
        inputs = {k: v.to(self._model.device) for k, v in inputs.items()}
        kwargs: dict[str, Any] = {"max_new_tokens": self.max_new_tokens, "do_sample": False,
                                  "pad_token_id": tok.pad_token_id}
        constraint = self._constraint(requests)
        if constraint is not None:
            kwargs["prefix_allowed_tokens_fn"] = constraint
        output = self._model.generate(**inputs, **kwargs)
        prompt_len = inputs["input_ids"].shape[1]
        responses = []
        for i in range(len(requests)):
            prompt_tokens = int(inputs["attention_mask"][i].sum())
            completion = output[i][prompt_len:]
            completion_tokens = int((completion != tok.pad_token_id).sum())
            text = tok.decode(completion, skip_special_tokens=True)
            responses.append(LLMResponse(text=text, usage={
                "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens}))
        return responses

    def _constraint(self, requests: list[LLMRequest]) -> Any:
        schemas = {json.dumps(r.json_schema or prompts.schema(r.schema), sort_keys=True)
                   for r in requests}
        if len(schemas) != 1:
            return None  # different schemas in one batch: rely on the prompt
        try:
            from lmformatenforcer import JsonSchemaParser
            from lmformatenforcer.integrations.transformers import (
                build_transformers_prefix_allowed_tokens_fn,
            )
        except ImportError:
            return None
        parser = JsonSchemaParser(json.loads(schemas.pop()))
        return build_transformers_prefix_allowed_tokens_fn(self._tokenizer, parser)
