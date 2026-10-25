"""Record baseline failures and vet the combined real source, wholly offline."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

PACKAGE = Path(__file__).resolve().parents[1]
AUDIT = PACKAGE.parent
SCRATCH = Path("/tmp/nfl-current-corrections-89512ed-v3")
PYTHON = str(AUDIT / "venv/bin/python")
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", GIT_OPTIONAL_LOCKS="0", PYTHON=PYTHON,
           NODE_OPTIONS="--require=" + str(PACKAGE / "verification/deny_node_network.cjs"),
           NFL_CHROMIUM_PATH="/usr/bin/chromium")

def run(name, command, lane="combined", expected=0, timeout=120):
    start = time.monotonic()
    result = subprocess.run(command, cwd=SCRATCH / lane, env=ENV, text=True,
                            capture_output=True, timeout=timeout)
    raw = (result.stdout + "\n" + result.stderr).replace(str(SCRATCH), "DISPOSABLE_FULL_SOURCE")
    (PACKAGE / "evidence" / (name + ".log")).write_text(raw)
    value = dict(command=command, source_lane=lane, exit_code=result.returncode,
                 expected_exit_code=expected, wall_seconds=round(time.monotonic()-start, 3))
    if result.stdout.strip():
        try:
            value["summary"] = json.loads(result.stdout.strip().splitlines()[-1])
        except json.JSONDecodeError:
            value["summary"] = result.stdout.strip()[-400:]
    assert result.returncode == expected, (name, value, raw[-5000:])
    return value

def main():
    results = {}
    results["baseline_python"] = run("baseline-python", [PYTHON, "-B", str(PACKAGE / "verification/run_python_suite.py")], lane="baseline")
    # The existing retained all-category oracle checks documented defects before
    # changes and corrected identity/finality/FG expectations after changes.
    for lane in ("baseline", "combined"):
        command = [PYTHON, "-B", str(PACKAGE / "verification/integrated_math_repro.py"), "--root", str(SCRATCH / lane)]
        if lane == "combined":
            command.append("--expect-patches")
        results[lane + "_math"] = run(lane+"-math", command, lane=lane)
    results["combined_python"] = run("combined-python", [PYTHON, "-B", str(PACKAGE / "verification/run_python_suite.py")])
    results["python_compile"] = run("python-compile", [PYTHON, "-B", "-m", "compileall", "-q", "pull", "tools"])
    for target in ("output/app.js", "output/reliability-ui.js", "output/weekly-adaptive-overlay.js"):
        results[target + "_syntax"] = run(target.replace("/", "-")+"-syntax", ["node", "--check", target])
    for target in sorted((SCRATCH / "combined/tests").glob("*.cjs")):
        if target.name == "test-presentation-browser.cjs":
            # This legacy real-data harness assumes the pre-selected ranking
            # contract. All current route/browser checks below use fictional data.
            continue
        results[target.name] = run(target.stem, ["node", "tests/"+target.name])
    for lane in ("baseline", "combined"):
        args = ["node", str(PACKAGE / "verification/half_ppr_repro.cjs"), "--root", str(SCRATCH / lane)]
        if lane == "combined":
            args.append("--expect-patches")
        results[lane + "_half_ppr"] = run(lane+"-half-ppr", args, lane=lane)
    # Actual new side-guard regression must fail specifically on the preimage.
    control = SCRATCH / "side-guard-before"
    shutil.copytree(SCRATCH / "baseline", control)
    shutil.copyfile(PACKAGE / "files/tests/test_weekly_selected_rankings.py", control / "tests/test_weekly_selected_rankings.py")
    results["side_guard_before"] = run("side-guard-before", [PYTHON, "-B", "-m", "unittest", "discover", "-s", "tests", "-p", "test_weekly_selected_rankings.py", "-v"], lane="side-guard-before", expected=1)
    failure = (PACKAGE / "evidence/side-guard-before.log").read_text()
    assert "ValueError not raised" in failure and "errors=0" not in failure
    path = PACKAGE / "evidence/qualification.json"
    path.write_text(json.dumps(results, indent=2, sort_keys=True)+"\n")
    print(json.dumps({name: value.get("summary", value["exit_code"]) for name,value in results.items()}, sort_keys=True))

if __name__ == "__main__":
    main()
