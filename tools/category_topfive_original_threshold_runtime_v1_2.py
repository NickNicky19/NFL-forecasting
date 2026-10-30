"""Recorded runtime continuation; preserve both original failed attempts."""
import hashlib
import json
from pathlib import Path
import sys

worker = Path(__file__).with_name("category_topfive_original_threshold_checks_v1.py")
body = worker.read_bytes()
assert hashlib.sha256(body).hexdigest() == "bfe454ab56a37eff49687311aded55774bd275aaf6a9cd1a072e877ce1e9b769"
source = body.decode()
changes = [
    ('"math": math, "GRADING_VERSION": "statistical-v3-identity-20261025"}', '"math": math, "GRADING_VERSION": "statistical-v3-identity-20261025", "RESULTS": ("hit", "miss", "push", "dnp", "unresolved")}'),
    ("original-threshold-real-functions-fictional-cases-v1", "original-threshold-real-functions-fictional-cases-v1.2"),
    ("THRESHOLD_REAL_PATH_RESULTS_V1.json", "THRESHOLD_REAL_PATH_RESULTS_V1_2.json"),
    ("STARTED_V1.json", "STARTED_V1_2.json"),
    ("FAILURE_V1.json", "FAILURE_V1_2.json"),
    ("retained + len(encoded) > 65536", "retained + len(encoded) > 81920"),
]
for old, new in changes:
    assert source.count(old) == 1
    source = source.replace(old, new)
exec(compile(source, "<pinned-worker-runtime-continuation-v1.2>", "exec"),
     {"__name__": "__main__", "__file__": str(worker)})
folder = Path(sys.argv[sys.argv.index("--report-root") + 1])
receipt = json.loads((folder / "THRESHOLD_REAL_PATH_RESULTS_V1_2.json").read_text())
assert receipt["CPU_seconds"] <= 5 and receipt["wall_seconds"] <= 15
retained = sum(p.stat().st_size for p in folder.rglob("*") if p.is_file())
retained += sum(p.stat().st_size for p in worker.parent.glob("category_topfive_original_threshold*.py"))
assert retained <= 81920
