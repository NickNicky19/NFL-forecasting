"""Score already-frozen canonical-v2 forecasts; no model or prediction path."""
from contextlib import ExitStack
import json
from pathlib import Path
import time
from unittest.mock import patch

import pandas as pd
from threadpoolctl import threadpool_limits

from direct_booster_frozen_report import no_science,relative
from direct_xgboost_binary_recovery import Session as ParentSession,process_free_threads
from nfl_lab import direct_booster_screen as parent,source_matched_benchmark as shared
from nfl_lab.source_matched_reporting import CONTEXT as ORIGINAL_CONTEXT
from nfl_lab.owned_reference_batch import validate_owned_references
from nfl_lab.reference_runtime import _deadline

VERSION="direct-xgboost-binary-scoring-v3-20261023"
POLICY_SHA256="f9c9c97b1922ee1cccee43c70fdf0bd5d9e9b2f821a2a71a3ceb724213506e28"
CONTEXT=tuple(dict.fromkeys(shared.cdf.KEYS+list(ORIGINAL_CONTEXT)))
CELLS=tuple((y,level) for y in (2022,2023,2024) for level in ("small","medium"))


def cached_labels(query,donor,category):
    """Restore the actual parent metadata contract without inventing fields."""
    if (not query.columns.is_unique or not donor.columns.is_unique or len(query)!=len(donor)
            or any(name not in query or name not in donor for name in CONTEXT)):
        raise ValueError("query/donor original nine-column context is incomplete")
    pd.testing.assert_frame_equal(query[list(CONTEXT)].reset_index(drop=True),
        donor[list(CONTEXT)].reset_index(drop=True),check_dtype=True,check_exact=True)
    presence=("season_type" in query,"season_type" in donor)
    if presence[0]!=presence[1]:raise ValueError("season_type persisted on only one side")
    if presence[0]:
        pd.testing.assert_series_equal(query.season_type.reset_index(drop=True),
            donor.season_type.reset_index(drop=True),check_dtype=True,check_exact=True)
    if not donor.primary_role.equals(donor.position.isin(category["primary_roles"])):
        raise ValueError("cached donor primary-role mask changed")
    if not donor.target.eq("anytime_td").all() or not donor.method.eq("direct_lightgbm_small").all():
        raise ValueError("exact original cached donor required")
    if not donor.participation_state.isin(["played","DNP","unknown"]).all():
        raise ValueError("unregistered participation state")
    result=donor.copy()
    result["anytime_td"]=donor.actual.to_numpy()
    result["qualified_outcome_state"]=donor.outcome_state.to_numpy()
    receipt=dict(columns=list(CONTEXT),exact_identity_order_context_dtypes=True,
        season_type="PRESENT_BOTH_EXACT" if presence[0] else "ABSENT_BOTH_FROZEN_LEGACY_PROJECTIONS",
        invented_season_type_values=False,
        population_contract="unchanged authenticated parent source/category/population; missing row metadata remains absent")
    return result,receipt


class Session(ParentSession):
    def check(self):
        if time.monotonic()-self.start>=175:raise RuntimeError("scoring-only inner wall budget exhausted")


def metadata(spec):
    names=("v2_execution_freeze","v2_forecast_freeze","v2_FAILED_completion",
        "parent_execution_freeze","parent_forecast_freeze","parent_scored_freeze","parent_FAILED_completion",
        "parent_config","category_contract","control_scored_freeze")
    meta={k:json.loads(shared._spec(spec[k]).read_text()) for k in names}
    v2,freeze,terminal=meta["v2_execution_freeze"],meta["v2_forecast_freeze"],meta["v2_FAILED_completion"]
    if (terminal["state"]!="FAILED" or terminal["returncode"]==0 or freeze["state"]!="ALL_SIX_NEW_FORECASTS_FROZEN"
            or freeze["rows"]!=51744 or freeze["new_fits"]!=0 or freeze["cached_donor_label_values_read"]!=0):
        raise ValueError("failed v2 with all six pre-label frozen forecasts required")
    slots=freeze["slots"]
    if len(slots)!=6 or tuple((s["year"],s["complexity"]) for s in slots)!=CELLS:
        raise ValueError("exact six globally frozen cells required")
    if meta["parent_FAILED_completion"]["state"]!="FAILED" or meta["parent_forecast_freeze"]["fatal"] is not None:
        raise ValueError("original failed screen provenance changed")
    original=meta["parent_config"];v2spec=v2["execution_metadata"]
    for key in ("cache","control_root","source_policy","category_contract","control_scored_freeze"):
        if spec[key]!=original[key] or spec[key]!=v2spec[key]:raise ValueError("original contracts changed: "+key)
    if spec["queries"]!={str(y):next(c["query"] for c in v2spec["cells"] if c["year"]==y) for y in shared.YEARS}:
        raise ValueError("exact original three queries required")
    if spec["donors"]!=v2spec["donors"]:raise ValueError("exact original three donors required")
    owned={spec[k]["path"]:spec[k]["sha256"] for k in names if k not in ("parent_config","category_contract")}
    root=Path(spec["v2_root"])
    for slot,binding in zip(slots,spec["forecast_files"]):
        if (binding["path"]!=str(relative(root,slot["forecast"])) or
                binding["sha256"]!=freeze["bindings"][slot["forecast"]] or
                slot["method"]!=f"direct_xgboost_binary_canonical_v2_{slot['complexity']}" or
                slot["rows"]!={2022:8686,2023:8606,2024:8580}[slot["year"]]):
            raise ValueError("six original globally frozen forecast bindings required")
        owned[binding["path"]]=binding["sha256"]
    if len(spec["forecast_files"])!=6:raise ValueError("extra/missing frozen forecast file")
    for binding in [*spec["queries"].values(),*spec["donors"].values()]:owned[binding["path"]]=binding["sha256"]
    controls=meta["control_scored_freeze"]
    for year in shared.YEARS:
        for method in parent.CONTROLS:
            name=f"private/scored/{year}/anytime_td/{method}/rows.parquet"
            if name not in controls["scored_files"]:raise ValueError("original control absent")
            owned[str(relative(Path(spec["control_root"]),name))]=controls["bindings"][name]
    return meta,owned


def run(spec,*,plan_sha256,final_static):
    if plan_sha256!=POLICY_SHA256 or spec["registration_id"]!=VERSION:raise ValueError("exact score-only registration required")
    session=Session(spec);session.start=time.monotonic()
    if (session.output/"SCORING_V3_CONSUMED.json").exists():raise RuntimeError("scoring-only invocation already consumed")
    session.write("SCORING_V3_CONSUMED.json",dict(at=shared.now(),registration_sha256=plan_sha256,
        new_fits_predictions_model_unpickles_HTTP=0))
    state="FAILED"
    try:
        with _deadline(175),process_free_threads(spec["loaded_libc"]),threadpool_limits(limits=2),no_science(),ExitStack() as guards:
            import direct_xgboost_binary_recovery as replay
            guards.enter_context(patch.object(replay,"run",side_effect=AssertionError("score-only cannot replay models")))
            guards.enter_context(patch.object(replay,"canonical",side_effect=AssertionError("score-only cannot derive a model")))
            meta,owned=metadata(spec)
            session.authenticated_controls,receipt=validate_owned_references(session.storage,owned)
            session.control_freeze=meta["control_scored_freeze"];session.write("owned-input-entry.json",receipt)
            category=shared._category(meta["category_contract"]["categories"],"anytime_td")
            scored=[]
            for year in shared.YEARS:
                session.check()
                query=pd.read_parquet(spec["queries"][str(year)]["path"])
                donor=pd.read_parquet(spec["donors"][str(year)]["path"])
                offered,context=cached_labels(query,donor,category)
                session.write(f"context/{year}.json",dict(context,year=year,query=spec["queries"][str(year)],donor=spec["donors"][str(year)]))
                selected=[(slot,binding) for slot,binding in zip(meta["v2_forecast_freeze"]["slots"],spec["forecast_files"]) if slot["year"]==year]
                for slot,binding in selected:
                    frozen=pd.read_parquet(binding["path"])
                    if (len(frozen)!=slot["rows"] or not frozen.method.eq(slot["method"]).all()
                            or not frozen.target.eq("anytime_td").all()):raise ValueError("frozen forecast dimensions/method changed")
                    result=parent.direct.score_frozen_rows(offered,frozen,category)
                    name=f"private/scored/{year}/{slot['method']}.parquet"
                    session.frame(name,shared.normalized(result,category,slot["method"]))
                    scored.append(dict(slot,scored=name,state="COMPLETED"))
                del query,donor,offered,frozen,result
            session.write("scored-freeze.json",dict(state="SCORED_ROWS_FROZEN",slots=scored,bindings=dict(session.bindings)))
            rows=pd.concat([pd.read_parquet(session.output/s["scored"]) for s in scored],ignore_index=True)
            controls=pd.concat([parent._control(session,y,"anytime_td",m,category)
                for y in shared.YEARS for m in parent.CONTROLS],ignore_index=True)
            report,pairs=parent.target_report(rows,controls,category,session.check)
            session.frame("private/paired-losses/anytime_td.parquet",pairs)
            session.frame("private/subgroups/anytime_td.parquet",parent.subgroup_rows(rows,category))
            final_static();metadata(spec)
            owned.update({str(session.output/name):digest for name,digest in session.bindings.items()})
            _,receipt=validate_owned_references(session.storage,owned);session.write("owned-input-exit.json",receipt)
            session.check();session.write("report.json",dict(at=shared.now(),version=VERSION,report=report,
                evidence="EXPOSED_SOURCE_MATCHED_DEVELOPMENT; scoring-only continuation, no additional forecasts/observations",
                prior_executions="Original direct screen FAILED; canonical-v2 replay FAILED; both unchanged",
                source_forecast_freeze=spec["v2_forecast_freeze"],new_fits_predictions_model_unpickles_HTTP=0,
                scored_forecast_rows=51744,forecasts=6,promotion="NONE",future_confirmation="REQUIRED"),freeze=False)
            state="COMPLETED"
    except BaseException as error:session.failure("SCORING_V3_FAILURE.json",error);raise
    finally:
        session.write("SCORING_V3_FINISHED.json",dict(state=state,new_fits_predictions_model_unpickles_HTTP=0,
            retention=session.storage.report_retention()),freeze=False)
