"""
Scoring helpers shared by the benchmark loaders.

ROUGE-L here is F1 over the longest common subsequence of tokens. Chinese text
is segmented with jieba when it is installed (as in MSCoRe's evaluation
script); otherwise each CJK character is a token. Latin words and numbers are
single tokens either way. The LCS uses Hyyrö's bit-parallel algorithm, so long
answers score in milliseconds.
"""

import json
import math
import re
from collections.abc import Sequence
from typing import Any

_TOKEN = re.compile(r"[㐀-鿿豈-﫿]|[A-Za-z0-9]+(?:[.,][0-9]+)*")
_CJK = re.compile(r"[㐀-鿿豈-﫿]")

try:
    import jieba

    jieba.setLogLevel(60)
except ImportError:  # optional: pip install -e ".[bench]"
    jieba = None


def tokenize(text: str, use_jieba: bool = True) -> list[str]:
    text = " ".join(str(text).split()).lower()
    if use_jieba and jieba is not None and _CJK.search(text):
        return [t for t in (w.strip() for w in jieba.cut(text)) if t and not _is_punct(t)]
    return _TOKEN.findall(text)


def _is_punct(token: str) -> bool:
    return not any(ch.isalnum() for ch in token)


def lcs_length(a: Sequence[Any], b: Sequence[Any]) -> int:
    """Length of the longest common subsequence (bit-parallel, Hyyrö 2004)."""
    if len(a) < len(b):
        a, b = b, a
    m = len(b)
    if m == 0:
        return 0
    masks: dict[Any, int] = {}
    for i, token in enumerate(b):
        masks[token] = masks.get(token, 0) | (1 << i)
    full = (1 << m) - 1
    v = full
    for token in a:
        u = v & masks.get(token, 0)
        v = ((v + u) | (v - u)) & full
    return m - bin(v).count("1")


def rouge_l(prediction: str, reference: str, use_jieba: bool = True) -> dict[str, float]:
    p = tokenize(prediction, use_jieba)
    r = tokenize(reference, use_jieba)
    if not p or not r:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    lcs = lcs_length(p, r)
    precision, recall = lcs / len(p), lcs / len(r)
    f1 = 0.0 if lcs == 0 else 2 * precision * recall / (precision + recall)
    return {"precision": precision, "recall": recall, "f1": f1}


def rouge_1(prediction: str, reference: str) -> float:
    """Unigram F1 (bag of tokens)."""
    p, r = tokenize(prediction), tokenize(reference)
    if not p or not r:
        return 0.0
    common = 0
    counts: dict[str, int] = {}
    for t in r:
        counts[t] = counts.get(t, 0) + 1
    for t in p:
        if counts.get(t, 0) > 0:
            counts[t] -= 1
            common += 1
    if common == 0:
        return 0.0
    precision, recall = common / len(p), common / len(r)
    return 2 * precision * recall / (precision + recall)


# ---------------------------------------------------------------- KramaBench-style values


def parse_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    text = str(value).strip().replace(",", "")
    try:
        if text.endswith("%"):
            return float(text[:-1]) / 100
        return float(text)
    except ValueError:
        match = re.search(r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", text)
        return float(match.group()) if match else None


def numbers_match(predicted: Any, target: Any, rel: float = 1e-6) -> bool:
    """KramaBench's ``success`` rule for numbers: tiny relative error, or a rounding difference."""
    p, t = parse_number(predicted), parse_number(target)
    if p is None or t is None or math.isnan(p):
        return False
    if t == 0:
        return abs(p) < 1e-6
    diff = abs(p - t)
    return diff / abs(t) < rel or diff < max(abs(p), abs(t)) * 1e-4


def parse_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    text = str(value).strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        pass
    return [item.strip() for item in text.strip("[]").split(",") if item.strip()]


def list_f1(predicted: Any, target: list[Any], rel: float = 1e-6) -> float:
    """F1 between lists: strings match case-insensitively, numbers within ``rel``."""
    pred, gold = parse_list(predicted), list(target)
    if not gold:
        return float(not pred)
    if not pred:
        return 0.0
    used: set[int] = set()
    hits = 0
    for t in gold:
        for j, p in enumerate(pred):
            if j in used:
                continue
            if isinstance(t, int | float) and not isinstance(t, bool):
                ok = numbers_match(p, t, rel)
            else:
                ok = str(p).strip().lower() == str(t).strip().lower()
            if ok:
                used.add(j)
                hits += 1
                break
    if hits == 0:
        return 0.0
    precision, recall = hits / len(pred), hits / len(gold)
    return 2 * precision * recall / (precision + recall)
