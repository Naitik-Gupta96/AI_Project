"""
Tools agents may call before posting (KramaBench data lakes, MedAgentBench FHIR).

``PythonSandbox`` runs model-written code. Use ``mode="docker"`` for real
runs: a fresh container per call, no network, the data lake mounted
read-only, memory and CPU capped, killed after ``timeout`` seconds. The image
is built from ``docker/sandbox.Dockerfile``. ``mode="local"`` runs a plain
subprocess in the data directory; it is for tests and trusted development
only, because the code runs with your user's permissions.
"""

import json
import shutil
import subprocess
import sys
import urllib.parse
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ai_project.llm.base import LLMProviderError
from ai_project.llm.providers.http import get_json


def _clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n… [truncated, {len(text) - limit} more characters]"


class ListFiles:
    name = "list_files"
    description = ('List files in the data lake. Arguments: {"contains": "<optional substring>"}. '
                   "Returns relative paths with sizes.")

    def __init__(self, root: str | Path, limit: int = 300) -> None:
        self.root = Path(root)
        self.limit = limit

    def __call__(self, arguments: Mapping[str, Any]) -> str:
        needle = str(arguments.get("contains") or "").lower()
        rows = []
        for path in sorted(self.root.rglob("*")):
            if path.is_file():
                rel = path.relative_to(self.root).as_posix()
                if needle in rel.lower():
                    rows.append(f"{rel}  ({path.stat().st_size:,} bytes)")
        if not rows:
            return "no matching files"
        shown = rows[: self.limit]
        more = f"\n… {len(rows) - len(shown)} more" if len(rows) > len(shown) else ""
        return "\n".join(shown) + more


class PythonSandbox:
    name = "python"
    description = ('Run Python 3 code with pandas and numpy. Arguments: {"code": "..."}. The '
                   "working directory is the data lake (read-only); print() what you need. "
                   "Output is truncated; each call is a fresh process.")

    def __init__(self, root: str | Path, mode: str = "docker", image: str = "ai-project-sandbox",
                 timeout: float = 90, max_output: int = 4000, memory: str = "2g") -> None:
        if mode not in ("docker", "local"):
            raise ValueError("mode must be 'docker' or 'local'")
        if mode == "docker" and shutil.which("docker") is None:
            raise RuntimeError("Docker is not installed; build the sandbox or use mode='local'")
        self.root = Path(root).resolve()
        self.mode = mode
        self.image = image
        self.timeout = timeout
        self.max_output = max_output
        self.memory = memory

    def command(self, code: str) -> list[str]:
        if self.mode == "docker":
            return ["docker", "run", "--rm", "--network", "none", "--memory", self.memory,
                    "--cpus", "1", "--pids-limit", "128", "-v", f"{self.root}:/data:ro",
                    "-w", "/data", self.image, "python", "-c", code]
        return [sys.executable, "-c", code]

    def __call__(self, arguments: Mapping[str, Any]) -> str:
        code = str(arguments.get("code") or "")
        if not code.strip():
            return "error: no code given"
        try:
            done = subprocess.run(self.command(code), cwd=self.root, capture_output=True,
                                  text=True, timeout=self.timeout, encoding="utf-8",
                                  errors="replace")
        except subprocess.TimeoutExpired:
            return f"error: timed out after {self.timeout:g} s"
        out = done.stdout
        if done.returncode != 0:
            out += f"\n[exit code {done.returncode}]\n" + done.stderr[-2000:]
        return _clip(out.strip() or "(no output)", self.max_output)


class FhirGet:
    """
    GET requests against the MedAgentBench FHIR server. POST requests are not
    sent anywhere: as in MedAgentBench, they are part of the answer and graded
    from the transcript.
    """

    name = "fhir_get"

    def __init__(self, base_url: str, functions: list[dict[str, Any]] | None = None,
                 max_output: int = 6000, timeout: float = 30) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.max_output = max_output
        self.timeout = timeout
        listing = ""
        for f in functions or []:
            if str(f.get("name", "")).startswith("GET"):
                params = ", ".join((f.get("parameters") or {}).get("properties", {}))
                listing += f"\n  {f['name'].replace('{api_base}', '')}  params: {params}"
        self.description = (
            'GET a FHIR resource. Arguments: '
            '{"path": "Patient?name=<name>&birthdate=<YYYY-MM-DD>"} '
            "(relative to the FHIR base). Available searches:" + listing
        )

    def __call__(self, arguments: Mapping[str, Any]) -> str:
        path = str(arguments.get("path") or "").lstrip("/")
        parsed = urllib.parse.urlsplit(path)
        if parsed.scheme or parsed.netloc or ".." in parsed.path:
            return "error: give a path relative to the FHIR base, e.g. Patient?family=Smith"
        url = self.base_url + path
        if "_format=" not in url:
            url += ("&" if "?" in url else "?") + "_format=json"
        try:
            data = get_json(url, timeout=self.timeout)
        except LLMProviderError as exc:
            return f"error: {exc}"
        return _clip(json.dumps(data, ensure_ascii=False), self.max_output)
