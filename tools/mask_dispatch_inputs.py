"""Mask private workflow inputs before a step exposes its environment."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

CAP = 256 << 10
PRIVATE_FIELDS = ("bootstrap_locators_json", "build_registration_json",
                  "inference_builder_go_json", "public_release_go_json")


def main(environ=None, output=None):
    env = os.environ if environ is None else environ
    output = sys.stdout if output is None else output
    path = Path(env["GITHUB_EVENT_PATH"])
    with path.open("rb") as stream:
        body = stream.read(CAP + 1)
    if len(body) > CAP:
        raise ValueError("DISPATCH_EVENT_BOUND")
    event = json.loads(body)
    inputs = event.get("inputs") or {}
    if type(inputs) is not dict:
        raise ValueError("DISPATCH_INPUT_TYPE")
    values = [inputs.get(key, "") for key in PRIVATE_FIELDS]
    if any(type(value) is not str for value in values):
        raise ValueError("DISPATCH_INPUT_TYPE")
    for value in values:
        if value:
            escaped = value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
            output.write("::add-mask::" + escaped + "\n")
    output.flush()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        print("DISPATCH_INPUT_MASKING_FAILED", file=sys.stderr)
        raise SystemExit(1)
