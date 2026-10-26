"""Reproduce the exact public canary admission defect without private IO.

Run with an installed research environment and a complete producer worktree:
    python checks.py --producer-tree /absolute/path/to/producer
The original Git object must be present. This does not establish native release
readiness, fetch data, read protected outcomes, fit models, or publish anything.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--producer-tree", type=Path, required=True)
    args = parser.parse_args()
    root = args.producer_tree.resolve()
    sys.path.insert(0, str(root))
    from nfl_lab import audit_weekly_controller_v1 as controller
    from nfl_lab import audit_weekly_hosted_v1 as hosted
    baseline = "b7a0f332274b79afddf176fb38f56c1c81cf8d22"
    module = "nfl_lab/audit_weekly_controller_v1.py"
    original = subprocess.check_output(["git", "show", baseline + ":" + module], cwd=root)
    old = next(node for node in ast.parse(original).body
               if isinstance(node, ast.FunctionDef) and node.name == "source_path")
    namespace = {"re": re, "require": controller.require}
    exec(compile(ast.Module(body=[old], type_ignores=[]), "<baseline-public-source-path>", "exec"), namespace)
    inventory = hosted.pins()
    assert len(inventory) == 128
    failures = []
    for path in inventory:
        try:
            namespace["source_path"](path)
        except controller.ControllerError as error:
            failures.append({"path": path, "error": str(error)})
    assert failures == [{"path": "reports/private-draft-canary-v2/ACTUAL_HOSTED_RESULT.json",
                         "error": "PUBLIC_SOURCE_PIN_PATH_ONLY"}]
    assert all(controller.source_path(path) == path for path in inventory)
    print(json.dumps({"state": "EXACT_BEFORE_AFTER_PATH_ADMISSION_REPRODUCED",
                      "baseline": baseline, "inventory_entries": len(inventory),
                      "before_rejected": failures,
                      "controller_sha256": hashlib.sha256((root / module).read_bytes()).hexdigest(),
                      "native_qualification_claimed": False}, sort_keys=True))


if __name__ == "__main__":
    main()
