"""Attempt 2: add only the omitted real grader constant to the fixture namespace.

The failed original worker stays byte-identical. Output filenames/version change
to retain its first-attempt start/failure. No website source is modified.
"""
import hashlib
from pathlib import Path

worker = Path(__file__).with_name("category_topfive_original_threshold_checks_v1.py")
body = worker.read_bytes()
assert hashlib.sha256(body).hexdigest() == "bfe454ab56a37eff49687311aded55774bd275aaf6a9cd1a072e877ce1e9b769"
source = body.decode()
old = '"math": math, "GRADING_VERSION": "statistical-v3-identity-20261025"}'
new = '"math": math, "GRADING_VERSION": "statistical-v3-identity-20261025", "RESULTS": ("hit", "miss", "push", "dnp", "unresolved")}'
assert source.count(old) == 1
source = source.replace(old, new)
for old, new in [
    ("original-threshold-real-functions-fictional-cases-v1", "original-threshold-real-functions-fictional-cases-v1.1"),
    ("THRESHOLD_REAL_PATH_RESULTS_V1.json", "THRESHOLD_REAL_PATH_RESULTS_V1_1.json"),
    ("STARTED_V1.json", "STARTED_V1_1.json"),
    ("FAILURE_V1.json", "FAILURE_V1_1.json"),
]:
    assert source.count(old) == 1
    source = source.replace(old, new)
exec(compile(source, "<pinned-worker-namespace-correction-v1.1>", "exec"),
     {"__name__": "__main__", "__file__": str(worker)})
