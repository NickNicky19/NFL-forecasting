"""Replay only the actual six retained CI cases against already built fake data."""
import hashlib
import json
from pathlib import Path
import sys
import traceback

BASE = Path(__file__).parent
SOURCE = BASE / "patched-source"
sys.path[:0] = [str(SOURCE / "tests"), str(SOURCE / "tools"), str(SOURCE / "pull")]
import test_phase2_e2e as cases

family, phase = sys.argv[1:3]
assert family in {"e2d", "045"} and phase in {"before", "after"}
folder = BASE / "evidence" / family
seed = json.loads((folder / "result.json").read_text())
cls = cases.RetainedRankedSourcePipelineTests if family == "e2d" else cases.Retained045RankedSourcePipelineTests
cls.base = folder / "fictional-base"
cls.state = seed["fictional_fixture_state"]
cls.source = cls.state["source_sha"]
assert cls.state["clean_replay"] == "PASS"
assert len(cls.state["updates"]) == 3
positive = "test_closed_original_source_and_pinned_ledger_replay_and_cold_process" if family == "e2d" else "test_actual045_saved_observation_ledger_and_independent_cold_replay"
methods = ([positive] if phase == "after" else []) + [
    "test_retained_failure_markers_and_same_size_corruption_are_not_cached",
    "test_unknown_source_and_unknown_ledger_helpers_fail_without_fallback",
]

def inventory():
    return {p.relative_to(cls.base).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for lane in ("data", "output/data") for p in (cls.base / lane).rglob("*") if p.is_file()}

original = inventory()
results = []
for method in methods:
    case = cls(method)
    row = dict(test=cls.__name__ + "." + method)
    try:
        case.setUp()
        getattr(case, method)()
        row["state"] = "PASS"
    except Exception as error:
        row.update(state="FAIL", error_type=type(error).__name__, error=str(error))
        traceback.print_exc()
    finally:
        case.doCleanups()
    assert inventory() == original, "Preserved fictional fixture changed"
    results.append(row)
    print(json.dumps(row, sort_keys=True), flush=True)
result = dict(family=family, phase=phase, fixture_only=True, seed_reused_without_rebuilding=True,
              preserved_fake_data_files=len(original), preserved_fake_data_unchanged=True, results=results)
path = folder / (phase + "-cases.json")
path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
raise SystemExit(0 if all(row["state"] == "PASS" for row in results) else 1)
