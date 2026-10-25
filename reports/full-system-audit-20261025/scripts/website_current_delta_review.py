#!/usr/bin/env python3
"""Bounded successor review; no website worktree writes or release qualification."""
import copy
import difflib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
AUDIT = Path(__file__).resolve().parent
ROOT = AUDIT / "website-current"
PIN = "b32b13d2123e56ae9e490ab881d4306758a48db1"


def run(command, *, cwd, env=None):
    result = subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    return result


def main():
    assert run(["git", "rev-parse", "HEAD"], cwd=ROOT).stdout.strip() == PIN
    spec = importlib.util.spec_from_file_location("frozen_math_patches", AUDIT / "website_math_patch_check.py")
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    paths = ("pull/scoring.py", "pull/grade.py", "pull/build.py", "output/app.js")
    source = {name: (ROOT / name).read_text() for name in paths}
    changes = generator.proposed("05-half-ppr-missing-labels", source, False)
    patch = "".join("".join(difflib.unified_diff(source[name].splitlines(True), value.splitlines(True),
                                             fromfile="a/" + name, tofile="b/" + name)) for name, value in changes.items())
    patch_name = "patches/website-current-b32b13d2123-math-05-half-ppr-missing-labels.patch"
    (AUDIT / patch_name).write_text(patch)
    result = {"schema_version": "website-current-bounded-delta-review-v1", "source_pin": PIN,
              "full_release_regated": False,
              "half_ppr_patch": {"path": patch_name, "sha256": hashlib.sha256(patch.encode()).hexdigest(),
                                 "preimage_sha256": hashlib.sha256(source["output/app.js"].encode()).hexdigest()}}
    python = str(AUDIT / "venv/bin/python")
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHON=python, SELECTED_RANKINGS_BROWSER="0")
    with tempfile.TemporaryDirectory(prefix="website-current-bounded-") as directory:
        scratch = Path(directory)
        shutil.copytree(ROOT, scratch, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns(".git", "__pycache__", ".venv", "node_modules"))
        program = '''import sys,json,unittest,socket,requests
def blocked(*a,**k):raise AssertionError("NETWORK_DISABLED_SUCCESSOR_REVIEW")
requests.sessions.Session.request=blocked
socket.socket.connect=blocked;socket.socket.connect_ex=blocked;socket.create_connection=blocked
suite=unittest.defaultTestLoader.discover("tests",pattern="test_weekly_selected_rankings.py")
r=unittest.TextTestRunner(verbosity=2).run(suite)
print(json.dumps(dict(tests=r.testsRun,failures=len(r.failures),errors=len(r.errors),skipped=len(r.skipped))))
sys.exit(not r.wasSuccessful())
'''
        checked = run([python, "-B", "-c", program], cwd=scratch, env=env)
        result["python_selected_rankings"] = json.loads(checked.stdout.strip().splitlines()[-1])
        (AUDIT / "website-current-ranking-tests.log").write_text(checked.stderr.replace(str(scratch), "DISPOSABLE_SUCCESSOR_COPY"))
        checked = run(["node", "tests/test-selected-rankings.cjs"], cwd=scratch, env=env)
        result["node_selected_rankings"] = checked.stdout.strip()

        # A positive-score over remains an over internally when moved into the
        # under container. Python's public graph validator omits the side join.
        program = '''import sys,json,copy,tempfile,runpy
sys.path.insert(0,"tools")
import weekly_selected_rankings as r
import weekly_adaptive_overlay as o
from reliability import atomic_json
t=runpy.run_path("tests/test_weekly_selected_rankings.py")
board,doc=t["fixture"](); good=t["make"](board,doc)
bad=copy.deepcopy(good); item=bad["picks"]["over"].pop(0); bad["picks"]["under"].append(item)
bad["picks"]["under"].sort(key=r.order)
with tempfile.TemporaryDirectory() as d:
 pointer=r.write_public(bad,d,atomic_json,clock=lambda:t["PERSIST"])
 accepted=True
 try:r.validate_document(bad,pointer,board,o.digest(board),doc,root=d)
 except ValueError:accepted=False
 print(json.dumps(dict(python_accepts_wrong_side=accepted,item_direction=item["direction"],container="under",score=item["score"])))
'''
        checked = run([python, "-B", "-c", program], cwd=scratch, env=env)
        result["independent_wrong_side_counterexample"] = json.loads(checked.stdout)
        assert result["independent_wrong_side_counterexample"]["python_accepts_wrong_side"]
        node_test = scratch / "tests/test-selected-rankings.cjs"
        node_source = node_test.read_text()
        needle = '  const late = {...fixture.pointer,published_at:'
        assert node_source.count(needle) == 1
        extra = '''  const wrongSide = clone(fixture.ranking);
  wrongSide.picks.under.push(wrongSide.picks.over.shift());
  wrongSide.picks.under.sort(context.compareSelectedRankingItems);
  await assert.rejects(() => context.validateSelectedRankings(wrongSide, fixture.pointer, S.data, S.weeklyOverlay), /Ranking source\\/clock/); checks++;
'''
        node_test.write_text(node_source.replace(needle, extra + needle, 1))
        checked = run(["node", "tests/test-selected-rankings.cjs"], cwd=scratch, env=env)
        result["actual_js_wrong_side_rejection"] = checked.stdout.strip()
        ranking_path = scratch / "tools/weekly_selected_rankings.py"
        old = ranking_path.read_text()
        needle = '        for item in items:\n            validate_item(item, offers, selected)'
        assert old.count(needle) == 1
        fixed = old.replace(needle, '        for item in items:\n            if item["direction"] != side: raise ValueError("ranking side mismatch")\n            validate_item(item, offers, selected)', 1)
        test_path = scratch / "tests/test_weekly_selected_rankings.py"
        old_test = test_path.read_text()
        regression = '''
    def test_valid_over_cannot_be_rehomed_into_under_container(self):
        board, doc = fixture(); good = make(board, doc)
        with tempfile.TemporaryDirectory() as td:
            pointer = r.write_public(good, td, atomic_json, clock=lambda: PERSIST)
            r.validate_document(good, pointer, board, o.digest(board), doc, root=td)
            bad = copy.deepcopy(good)
            bad["picks"]["under"].append(bad["picks"]["over"].pop(0))
            bad["picks"]["under"].sort(key=r.order)
            pointer = r.write_public(bad, td, atomic_json, clock=lambda: PERSIST)
            with self.assertRaisesRegex(ValueError, "ranking side mismatch"):
                r.validate_document(bad, pointer, board, o.digest(board), doc, root=td)

'''
        end = '\n\nif __name__ == "__main__":'
        assert old_test.count(end) == 1
        new_test = old_test.replace(end, '\n' + regression + end, 1)
        test_path.write_text(new_test)
        before = subprocess.run([python, "-B", "-m", "unittest", "discover", "-s", "tests", "-p", "test_weekly_selected_rankings.py"],
                                cwd=scratch, env=env, text=True, capture_output=True)
        assert before.returncode != 0 and 'ValueError not raised' in before.stderr, before.stderr
        result["new_regression_before_guard"] = {"expected_failure": True, "reason": "ValueError not raised", "tests": 17}
        (AUDIT / "website-current-side-guard-before.log").write_text(before.stderr.replace(str(scratch), "DISPOSABLE_SUCCESSOR_COPY"))
        side_patch = "".join(difflib.unified_diff(old.splitlines(True), fixed.splitlines(True),
                             fromfile="a/tools/weekly_selected_rankings.py", tofile="b/tools/weekly_selected_rankings.py"))
        side_patch += "".join(difflib.unified_diff(old_test.splitlines(True), new_test.splitlines(True),
                             fromfile="a/tests/test_weekly_selected_rankings.py", tofile="b/tests/test_weekly_selected_rankings.py"))
        name = "patches/website-current-b32b13d2123-rankings-side-guard.patch"
        (AUDIT / name).write_text(side_patch)
        ranking_path.write_text(fixed)
        checked = run([python, "-B", "-c", program], cwd=scratch, env=env)
        corrected = json.loads(checked.stdout)
        assert not corrected["python_accepts_wrong_side"]
        result["side_guard_patch"] = {"path": name, "sha256": hashlib.sha256(side_patch.encode()).hexdigest(),
                                      "corrected_counterexample": corrected}
        run(["patch", "--batch", "--fuzz=0", "-p1", "-i", str(AUDIT / patch_name)], cwd=scratch)
        run(["node", "--check", "output/app.js"], cwd=scratch, env=env)
        checked = run(["node", str(AUDIT / "website_ppr_label_repro.cjs"), "--root", str(scratch), "--expect-patches"], cwd=scratch, env=env)
        result["half_ppr_scratch"] = json.loads(checked.stdout)
        checked = run([python, "-B", "-c", '''import unittest,sys,json
s=unittest.defaultTestLoader.discover("tests",pattern="test_weekly_selected_rankings.py")
r=unittest.TextTestRunner().run(s)
print(json.dumps(dict(tests=r.testsRun,failures=len(r.failures),errors=len(r.errors))))
sys.exit(not r.wasSuccessful())'''], cwd=scratch, env=env)
        result["patched_focused_python"] = json.loads(checked.stdout)
        checked = run(["node", "tests/test-selected-rankings.cjs"], cwd=scratch, env=env)
        result["patched_focused_node"] = checked.stdout.strip()
    # No old frozen artifacts are regenerated or overwritten.
    (AUDIT / "website-current-delta-validation.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
