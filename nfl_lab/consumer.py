"""Read-only scalar consumer adapter; original evidence bytes are preserved."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from jsonschema import Draft202012Validator,FormatChecker

from .state import digest,utc,validate_forecast


def consumer_forecast(original:dict,*,schema_path:Path|None=None)->dict:
    row=deepcopy(original)
    # Early v1 scalar records used ISO8601's space separator. Normalize only
    # the consumer representation, with an explicit digest of the original.
    for key in ["kickoff_utc","issued_at"]:row[key]=utc(row[key]).isoformat()
    row["derived_from_original_row_sha256"]=digest(original)
    row["consumer_schema"]="nfl-lab-scalar-v1"
    validate_forecast(row)
    path=schema_path or Path(__file__).resolve().parents[1]/"schemas/forecast-v1.json"
    Draft202012Validator(json.loads(path.read_text()),format_checker=FormatChecker()).validate(row)
    return row
