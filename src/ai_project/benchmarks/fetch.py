"""
Download benchmark data into ``$BB_DATA_DIR`` (default ``data``): ``bb fetch <name>``.

    mscore         value-chain files from Hugging Face (about 450 MB; --small: 4 files, ~20 MB)
    kramabench     the KramaBench repository: workloads and six data lakes
                   (sparse git clone, about 530 MB; --small: workloads only)
    medagentbench  task and function files; prints the FHIR server and grader steps
"""

import json
import shutil
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

from ai_project.benchmarks.mscore import CHAINS
from ai_project.benchmarks.registry import data_dir

HF_DATASET = "032564yn/MSCoRe"
HF_REVISION = "main"
KRAMABENCH_REPO = "https://github.com/mitdbg/Kramabench.git"
MEDAGENT_RAW = "https://raw.githubusercontent.com/stanfordmlgroup/MedAgentBench/main/data/medagentbench"

MSCORE_SMALL = (
    "Automotive Value Chain/Medium/Design",
    "Pharmaceytical Value Chain/Medium/Multi-stage-task",
    "Electronic Commerce Value Chain/Hard/Full-Chain-task",
    "Automotive-Energy Chain/Electricity Storage",
)


def _download(url: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".part")
    with urllib.request.urlopen(url, timeout=120) as response, open(tmp, "wb") as f:
        shutil.copyfileobj(response, f, length=1 << 20)
    tmp.replace(target)


def fetch_mscore(small: bool = False, log=print) -> Path:
    root = data_dir("mscore")
    api = f"https://huggingface.co/api/datasets/{HF_DATASET}/tree/{HF_REVISION}?recursive=true"
    with urllib.request.urlopen(api, timeout=60) as response:
        entries = json.load(response)
    wanted = [e["path"] for e in entries
              if e.get("type") == "file" and e["path"].split("/")[0] in CHAINS.values()]
    if small:
        wanted = [p for p in wanted if p in MSCORE_SMALL]
    for path in wanted:
        target = root / path
        if target.is_file():
            continue
        url = (f"https://huggingface.co/datasets/{HF_DATASET}/resolve/{HF_REVISION}/"
               + urllib.parse.quote(path))
        log(f"  {path}")
        _download(url, target)
    return root


def fetch_kramabench(small: bool = False, log=print) -> Path:
    root = data_dir("kramabench")
    if not (root / ".git").is_dir():
        root.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "--depth", "1", "--filter=blob:none", "--sparse",
                        KRAMABENCH_REPO, str(root)], check=True)
    folders = ["workload"] if small else ["workload", "data"]
    subprocess.run(["git", "-C", str(root), "sparse-checkout", "set", *folders], check=True)
    log(f"  checked out: {', '.join(folders)}")
    return root


def fetch_medagentbench(log=print) -> Path:
    root = data_dir("medagentbench")
    for name in ("test_data_v2.json", "funcs_v1.json"):
        if not (root / name).is_file():
            log(f"  {name}")
            _download(f"{MEDAGENT_RAW}/{name}", root / name)
    log("\nTwo manual steps remain:")
    log("  1. Start the FHIR server:  docker compose up -d fhir   (image jyxsu6/medagentbench)")
    log("  2. Download the official grader refsol.py from the link in the MedAgentBench README")
    log("     (https://github.com/stanfordmlgroup/MedAgentBench) and save it as")
    log(f"     {root / 'refsol.py'}")
    return root


FETCHERS = {
    "mscore": fetch_mscore,
    "kramabench": fetch_kramabench,
    "medagentbench": lambda small=False, log=print: fetch_medagentbench(log),
}
