"""Replay and score only immutable, timely persisted and remotely saved forecasts."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .evaluation import summarize
from .state import digest,records,resolved_outcomes,utc,validate_forecast
from .recorded_research import FUNCTIONAL


def score_saved(state:Path):
    outcomes=resolved_outcomes(state)
    persistence={r["batch"]:r for r in records(state,"persistence")}
    publication={r["batch"]:r for r in records(state,"publication")}
    rows=[];counts={"local_only":0,"late":0,"unknown":0,"pending":0,"conflicts":0,"timely_public_forecasts":0,"unverified_code":0}
    for batch in records(state,"forecasts"):
        key=digest(batch);persist=persistence.get(key);pub=publication.get(key)
        for r in batch["rows"]:
            if r.get("code_integrity")!="pre_post_source_digest_required":counts["unverified_code"]+=1;continue
            validate_forecast(r)
            point=r.get("prediction_functional")==FUNCTIONAL
            if not persist or not pub:counts["local_only"]+=1;continue
            kickoff=utc(r["kickoff_utc"])
            if utc(persist["completed_at"])>=kickoff or utc(pub["observed_remote_readback_at"])>=kickoff:
                counts["late"]+=1;continue
            counts["timely_public_forecasts"]+=1
            outcome=outcomes.get((r["player_id"],r["game_id"],r["target"]))
            if outcome is None:counts["pending"]+=1;outcome={"state":"pending","actual":None}
            if outcome["state"].startswith("unresolved"):counts["conflicts"]+=1
            participation="played" if outcome["state"] in ["played","played_corrected"] else "DNP" if outcome["state"]=="DNP" else "unknown"
            if participation=="unknown" and outcome["state"]!="pending":counts["unknown"]+=1
            rows.append({**r,"method":r["model_id"],"actual":outcome["actual"],"participation_state":participation,
                         "cohort":"unqualified_shadow_no_confirmation_registration" if point else "confirmation_window" if r["season"]>2026 or (r["season"]==2026 and r["week"]>=8) else "preconfirmation_shadow"})
    summaries=[]
    if rows:
        frame=pd.DataFrame(rows)
        for (model,target,cohort),g in frame.groupby(["model_id","target","cohort"]):
            point=cohort=="unqualified_shadow_no_confirmation_registration"
            summaries.append({"model":model,"target":target,"cohort":cohort,
                "confirmation_state":"UNREGISTERED_UNQUALIFIED_SHADOW" if point else "PENDING_REGISTERED_GATES",
                **summarize(g,include_distribution=not point,value_column="point" if point else "mean")})
    return {"schema_version":"lab-prospective-scorecard-v1","timing_scope":"local write completion and remote commit readback both strictly before kickoff",
            "forecast_counts":counts,"categories":summaries,"promotion":[],"future_confirmation":"not qualified merely by software tests or initial outcomes"}
