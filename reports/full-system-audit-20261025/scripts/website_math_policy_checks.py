#!/usr/bin/env python3
"""Run narrowly selected existing fictional checks with HTTP disabled and -B.

Every test's writable fixture is temporary; no source build, provider, browser,
workflow, lease, real outcome collection, or confirmation experiment is run.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

sys.dont_write_bytecode = True
from website_math_repro import AUDIT, install_network_guard


def module(root, name):
    spec = importlib.util.spec_from_file_location(name, root / "tests" / (name + ".py"))
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


def run(root):
    install_network_guard()
    sys.path[:0] = [str(root / "pull"), str(root / "tools"), str(root / "tests")]
    reliability = module(root, "test_reliability")
    classes = [reliability.GradingTests]
    if (root / "tests/test_scorecard.py").exists():
        scorecard = module(root, "test_scorecard")
        classes += [scorecard.ScorecardTests, scorecard.OutcomePrecedenceRegressionTests,
                    scorecard.AllPickableOutcomeTests, scorecard.OutcomeIdentityBindingRegressionTests]
        presence = module(root, "test_data_integrity_v2")
        classes += [presence.PresenceTests]
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(case) for case in classes)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)
    return {"tests": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
            "classes": [case.__name__ for case in classes], "http": "DISABLED", "bytecode_writes": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path)
    args = parser.parse_args()
    if args.root:
        result = run(args.root)
    else:
        result = {}
        for name in ("website-audit", "website-phase2"):
            child = subprocess.run([sys.executable, "-B", str(Path(__file__).resolve()), "--root", str(AUDIT / name)],
                                   text=True, capture_output=True)
            sys.stderr.write(child.stderr)
            if child.returncode:
                child.check_returncode()
            result[name] = json.loads(child.stdout)
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
