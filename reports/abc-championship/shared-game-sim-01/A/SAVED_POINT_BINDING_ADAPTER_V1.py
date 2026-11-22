"""Identity-only saved-point binding; no simulator, model fitting or grading.

The current website ID namespace and horizon still require the website owner's
admission. Conditional counts from this adapter are not qualified prop grades.
Do not derive a probability from a point. Source rows remain owner-local.
"""
import hashlib
import json
import math
from datetime import date, datetime
from collections import Counter
from numbers import Real

VERSION = "A-SHARED-GAME-SIM-01-SAVED-POINT-BINDING-v1"


def encoded(value):
    def clock(item):
        if isinstance(item, (datetime, date)):
            return {"source_type": type(item).__name__, "value": item.isoformat()}
        raise TypeError("Unsupported commitment value type: " + type(item).__name__)
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      allow_nan=False, default=clock).encode()


def point_state(value):
    if value is None:
        return "MISSING_SAVED_POINT"
    if isinstance(value, bool) or not isinstance(value, Real):
        return "INVALID_SAVED_POINT_TYPE"
    if not math.isfinite(float(value)):
        return "NONFINITE_SAVED_POINT"
    return "CONDITIONALLY_BOUND_POINT"


def bind(query, forecasts, *, selector, sleeper_to_gsis, event_to_game):
    """Return aggregate conditional availability and a private-row commitment.

    Crosswalks must come from exact retained source bindings. No names,
    eventual participation, target results or success-dependent filters enter.
    Mapping absence is a binding gap, not a failed forecast or abstention.
    """
    if len({q["case_id"] for q in query}) != len(query):
        raise ValueError("Duplicate full-frame case IDs")
    lookup = {}
    for f in forecasts:
        if any(f[k] != selector[k] for k in ("target", "method", "product")):
            continue
        if f["output_procedure_version"] != selector["procedure_version"]:
            raise ValueError("Wrong saved procedure/output version")
        key = (int(f["season"]), int(f["week"]), f["game_id"], f["player_id"])
        if key in lookup:
            raise ValueError("Duplicate source forecast identity")
        lookup[key] = f
    weekly, reasons, fallback = {}, Counter(), Counter()
    rows = []
    for q in query:
        if q["category"] != selector["target"]:
            continue
        w = int(q["week"])
        counts = weekly.setdefault(str(w), Counter())
        counts["frame_rows"] += 1
        if w not in (1, 2, 3, 4, 5, 6, 7):
            reason, f = "NO_SAVED_ORIGIN_OUTPUT", None
        else:
            game = event_to_game.get((w, str(q["game_id"])))
            player = sleeper_to_gsis.get(str(q["player_id"]))
            f = lookup.get((int(q["season"]), w, game, player))
            reason = ("EVENT_MAP_NOT_RETAINED" if game is None else
                      "EXACT_PLAYER_MAP_NOT_RETAINED_OR_QUARANTINED" if player is None else
                      "NO_SAVED_QUERY_ROW" if f is None else
                      "ROLE_MISMATCH" if f["position"] != q["position"] else
                      point_state(f["prediction"]))
        counts[reason] += 1
        reasons[reason] += 1
        if reason == "CONDITIONALLY_BOUND_POINT":
            flag = f.get("fallback")
            flag = "NOT_RETAINED" if flag is None else str(flag)
            fallback[flag] += 1
            rows.append([q["case_id"], float(f["prediction"]), flag,
                         f.get("cutoff_utc"), f.get("source_issue_time_UTC")])
    return {"adapter": VERSION,
            "status": "CONDITIONAL_ID_BINDING_NOT_WEBSITE_ADMITTED_OR_GRADED",
            "weekly": {k: dict(v) for k, v in sorted(weekly.items())},
            "reasons": dict(reasons), "fallback_flags": dict(fallback),
            "bound_count": len(rows),
            "bound_case_prediction_clock_commitment": hashlib.sha256(encoded(rows)).hexdigest(),
            "target_outcomes_consumed": False, "grades_generated": 0}
