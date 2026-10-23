"""Six-cell, zero-fit replay using the accepted binary output canonicalizer."""
from contextlib import contextmanager,ExitStack
import importlib.util
import json
from pathlib import Path
import sys
import time
from unittest.mock import patch

import numpy as np
import pandas as pd
import threadpoolctl
from threadpoolctl import threadpool_limits

from nfl_lab import direct_booster_screen as parent
from nfl_lab import source_matched_benchmark as shared
from nfl_lab.operational_storage import OperationalStorage
from nfl_lab.owned_reference_batch import validate_owned_references
from nfl_lab.reference_runtime import _deadline
from direct_booster_frozen_report import cap_output,relative

VERSION="direct-xgboost-binary-recovery-v2-20261023"
POLICY_SHA256="81fcf8f0f24090b048d6dce1e72517bb4f0aa0f8eb2ffabc913ccf5f0098ada8"
CANONICAL_SHA256="0a3cb910fb12e7e2095132c4c28ead1ff1a6d0e3943696e78ffc8705fac233ce"
CELLS=tuple((year,level) for year in (2022,2023,2024) for level in ("small","medium"))
CONTEXT=tuple(dict.fromkeys(shared.cdf.KEYS+["team","opponent","position","cutoff_utc","kickoff_utc","season_type"]))


class Sequence:
    """Control the year boundary and global no-label-before-freeze boundary."""
    def __init__(self):self.frozen=[];self.rows=0;self.global_frozen=False;self.reserved=None
    def before_model(self,year,complexity):
        if len(self.frozen)>=6 or CELLS[len(self.frozen)]!=(year,complexity):
            raise ValueError("exact year-ascending six-cell sequence required")
    def reserve(self,year,complexity,rows):
        self.before_model(year,complexity)
        if self.reserved is not None or type(rows) is not int or rows<=0 or self.rows+rows>60000:
            raise ValueError("query prediction row budget exceeded")
        self.reserved=(year,complexity,rows);self.rows+=rows
    def freeze(self,year,complexity,rows):
        self.before_model(year,complexity)
        if self.reserved!=(year,complexity,rows):raise ValueError("prediction rows were not charged before inference")
        self.frozen.append((year,complexity));self.reserved=None
    def global_freeze(self):
        if tuple(self.frozen)!=CELLS or self.rows!=51744 or self.reserved is not None:
            raise ValueError("all six exact offered-population forecasts required")
        self.global_frozen=True
    def before_labels(self):
        if not self.global_frozen:raise ValueError("cached labels forbidden before global forecast freeze")


def donor_labels(query,donor,category):
    """Preserve cached football labels and every original participation state."""
    if (not query.columns.is_unique or not donor.columns.is_unique or len(query)!=len(donor)
            or any(name not in query or name not in donor for name in CONTEXT)):
        raise ValueError("query/donor context is incomplete")
    pd.testing.assert_frame_equal(query[list(CONTEXT)].reset_index(drop=True),
        donor[list(CONTEXT)].reset_index(drop=True),check_dtype=True,check_exact=True)
    expected=donor.position.isin(category["primary_roles"])
    if not donor.primary_role.equals(expected):raise ValueError("cached donor primary role changed")
    if not donor.target.eq("anytime_td").all() or not donor.method.eq("direct_lightgbm_small").all():
        raise ValueError("exact registered cached label donor required")
    if not donor.participation_state.isin(["played","DNP","unknown"]).all():
        raise ValueError("unsupported cached participation state")
    result=donor.copy()
    result["anytime_td"]=donor.actual.to_numpy()
    result["qualified_outcome_state"]=donor.outcome_state.to_numpy()
    return result


def canonical(binding):
    path=shared._spec(binding)
    if binding["sha256"]!=CANONICAL_SHA256:raise ValueError("accepted canonicalizer bytes required")
    name="nfl_lab.direct_binary_canonical_v2"
    if name in sys.modules:
        loaded=sys.modules[name]
        if Path(loaded.__file__).resolve()!=path.resolve():raise ValueError("canonical module path collision")
        return loaded
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module
    spec.loader.exec_module(module)
    return module


@contextmanager
def process_free_threads(binding):
    """Resolve threadpoolctl's already loaded libc without ldconfig processes."""
    path=shared._spec(binding)
    loaded={Path(line.split()[-1]).resolve() for line in Path("/proc/self/maps").read_text().splitlines()
        if len(line.split())>=6 and line.split()[-1].endswith("/libc.so.6")}
    if path.resolve() not in loaded:raise ValueError("frozen libc is not already loaded")
    def resolve(name):
        if name!="c":raise AssertionError("unregistered thread-controller library lookup")
        return str(path)
    with patch.object(threadpoolctl,"find_library",resolve):yield


def storage(spec):
    store=OperationalStorage(spec["cache"],json.loads(shared._spec(spec["source_policy"]).read_text()))
    output=store.register_root(spec["output"])
    cap_output(store,output)
    prior=store.write_bytes
    def bounded(path,body,*,replace=False):
        import hashlib
        incoming=0 if (store.blob_root/hashlib.sha256(body).hexdigest()).exists() else len(body)
        if store.report_retention()["charged_bytes"]+incoming>16777216:
            raise RuntimeError("16 MiB binary recovery retention exhausted before write")
        return prior(path,body,replace=replace)
    store.write_bytes=bounded
    prior_retention=store.report_retention
    def effective_retention():
        value=dict(prior_retention())
        value["borrowed_helper_limit_bytes"]=value["limit_bytes"]
        value["limit_bytes"]=16777216
        return value
    store.report_retention=effective_retention
    return store,output


class Session:
    write=shared.Session.write;frame=shared.Session.frame;failure=shared.Session.failure
    def __init__(self,spec):
        self.spec=spec;self.storage,self.output=storage(spec);self.bindings={}
    def check(self):
        if time.monotonic()-self.start>=115:raise RuntimeError("binary recovery inner wall budget exhausted")


@contextmanager
def no_fits_or_sources():
    def forbidden(*a,**k):raise AssertionError("binary recovery forbids fits and original source reads")
    with shared.no_fits(),ExitStack() as guards:
        import xgboost
        guards.enter_context(patch.object(xgboost.XGBClassifier,"fit",forbidden))
        guards.enter_context(patch.object(xgboost.XGBRegressor,"fit",forbidden))
        for owner,name in ((parent.direct.DirectBoosterModel,"fit"),(parent,"run_screen"),
                (parent,"report_screen"),(shared,"fold"),(shared,"read_partition"),
                (shared,"_dataset"),(shared,"_outcomes"),(shared.operational_sources,"_verify"),
                (shared.models,"fit_predict"),(shared.operational_models,"fit_operational_reference"),
                (shared.operational_models,"predict_operational_artifact")):
            guards.enter_context(patch.object(owner,name,forbidden))
        yield


def metadata(spec):
    values={key:json.loads(shared._spec(spec[key]).read_text()) for key in (
        "parent_execution_freeze","parent_forecast_freeze","parent_scored_freeze",
        "parent_FAILED_completion","parent_config","category_contract","control_scored_freeze")}
    forecast,scored,terminal=values["parent_forecast_freeze"],values["parent_scored_freeze"],values["parent_FAILED_completion"]
    if (forecast["state"]!="GLOBAL_FORECASTS_FROZEN" or forecast["fatal"] is not None
            or len(forecast["slots"])!=216 or len(scored["slots"])!=192 or terminal["state"]!="FAILED"
            or terminal["returncode"]!=-9):raise ValueError("original complete frozen experiment and retained failure required")
    selected=[s for s in forecast["slots"] if s["library"]=="xgboost" and s["target"]=="anytime_td"]
    if tuple((s["year"],s["complexity"]) for s in selected)!=CELLS or any(s["state"]!="FAILED" for s in selected):
        raise ValueError("exact six original failed cells required")
    original=values["parent_config"]
    if (original["source_policy"]!=spec["source_policy"] or original["category_contract"]!=spec["category_contract"]
            or original["control_scored_freeze"]!=spec["control_scored_freeze"] or original["cache"]!=spec["cache"]
            or original["control_root"]!=spec["control_root"] or original["output"]!=spec["parent_root"]):
        raise ValueError("original source/category/control contracts changed")
    if len(spec["cells"])!=6 or tuple((c["year"],c["complexity"]) for c in spec["cells"])!=CELLS:
        raise ValueError("fixed six-cell executable inventory required")
    owned={spec[key]["path"]:spec[key]["sha256"] for key in (
        "parent_execution_freeze","parent_forecast_freeze","parent_scored_freeze","parent_FAILED_completion","control_scored_freeze")}
    for cell in spec["cells"]:
        year,level=cell["year"],cell["complexity"]
        expected_rows=next(s["rows"] for s in forecast["slots"] if s["year"]==year and s["state"]=="PREDICTION_FROZEN")
        if cell["query_rows"]!=expected_rows:raise ValueError("original offered query population changed")
        for key,name in (("model",f"private/cells/{year}/anytime_td/direct_xgboost_{level}/model.joblib"),
                ("failure",f"private/cells/{year}/anytime_td/direct_xgboost_{level}/FAILURE.json"),
                ("query",f"private/queries/{year}.parquet")):
            binding=cell[key]
            if (binding["path"]!=str(relative(Path(spec["parent_root"]),name))
                    or forecast["bindings"].get(name)!=binding["sha256"]):
                raise ValueError("original model/failure/query binding changed")
            owned[binding["path"]]=binding["sha256"]
        donor=spec["donors"][str(year)]
        name=f"private/scored/{year}/anytime_td/direct_lightgbm_small.parquet"
        if donor["path"]!=str(relative(Path(spec["parent_root"]),name)) or scored["bindings"].get(name)!=donor["sha256"]:
            raise ValueError("exact original label donor binding required")
        owned[donor["path"]]=donor["sha256"]
    controls=values["control_scored_freeze"]
    for year in shared.YEARS:
        for method in parent.CONTROLS:
            name=f"private/scored/{year}/anytime_td/{method}/rows.parquet"
            if name not in controls["scored_files"]:raise ValueError("original control missing")
            owned[str(relative(Path(spec["control_root"]),name))]=controls["bindings"][name]
    if sum(c["query_rows"] for c in spec["cells"])!=51744:
        raise ValueError("exact original six-cell row-incidence inventory required")
    return values,owned


def run(spec,*,plan_sha256,final_static):
    if plan_sha256!=POLICY_SHA256 or spec["registration_id"]!=VERSION:
        raise ValueError("exact registered binary recovery required")
    sequence=Sequence();session=Session(spec);session.start=time.monotonic()
    if (session.output/"BINARY_RECOVERY_CONSUMED.json").exists():raise RuntimeError("sole binary recovery already consumed")
    session.write("BINARY_RECOVERY_CONSUMED.json",dict(at=shared.now(),registration_sha256=plan_sha256,new_fits=0))
    state="FAILED";phase="BEFORE_FORECASTS"
    try:
        with _deadline(115),process_free_threads(spec["loaded_libc"]),threadpool_limits(limits=2),no_fits_or_sources():
            values,owned=metadata(spec)
            session.authenticated_controls,receipt=validate_owned_references(session.storage,owned)
            session.control_freeze=values["control_scored_freeze"]
            session.write("owned-input-entry.json",receipt)
            accepted=canonical(spec["canonicalizer"])
            category=shared._category(values["category_contract"]["categories"],"anytime_td")
            import joblib
            frozen=[]
            for cell in spec["cells"]:
                year,level=cell["year"],cell["complexity"]
                session.check();sequence.before_model(year,level)
                query=pd.read_parquet(cell["query"]["path"])
                if len(query)!=cell["query_rows"]:raise ValueError("original query row count changed")
                sequence.reserve(year,level,len(query))
                model=joblib.load(cell["model"]["path"])
                derived=accepted.derive_model(model)
                rows=accepted.prediction_rows(derived,query)
                if not rows[shared.cdf.KEYS].equals(query[shared.cdf.KEYS]):raise ValueError("forecast identity/order changed")
                method=f"direct_xgboost_binary_canonical_v2_{level}"
                relative_name=f"private/forecasts/{year}/{method}.parquet"
                session.frame(relative_name,shared.normalized(rows,category,method))
                sequence.freeze(year,level,len(query))
                session.write(f"derivatives/{year}/{level}.json",dict(parent_model=cell["model"],
                    canonicalizer=spec["canonicalizer"],parent_configuration=spec["parent_config"],
                    parent_execution_environment=spec["parent_execution_freeze"],
                    source_preprocessing_and_weights="unchanged parent artifact",version=accepted.VERSION,
                    event_probability="unchanged exact native scalar; non-event component exact-complement validated",
                    new_fits=0,forecast=relative_name,forecast_sha256=session.bindings[relative_name]))
                frozen.append(dict(year=year,complexity=level,method=method,forecast=relative_name,rows=len(query)))
                del model,derived,rows,query
                session.write(f"forecast-checkpoints/{year}-{level}.json",dict(state="FROZEN",at=shared.now()))
            sequence.global_freeze()
            session.write("forecast-freeze.json",dict(state="ALL_SIX_NEW_FORECASTS_FROZEN",at=shared.now(),
                rows=sequence.rows,slots=frozen,bindings=dict(session.bindings),new_fits=0,
                cached_donor_label_values_read=0,original_cells="six original FAILED cells retained unchanged"))
            phase="SCORING_AFTER_GLOBAL_FREEZE"
            scored=[]
            for year in shared.YEARS:
                sequence.before_labels();session.check()
                donor=pd.read_parquet(spec["donors"][str(year)]["path"])
                query=pd.read_parquet(next(c["query"]["path"] for c in spec["cells"] if c["year"]==year))
                offered=donor_labels(query,donor,category)
                for slot in [s for s in frozen if s["year"]==year]:
                    rows=pd.read_parquet(session.output/slot["forecast"])
                    result=parent.direct.score_frozen_rows(offered,rows,category)
                    name=f"private/scored/{year}/{slot['method']}.parquet"
                    session.frame(name,shared.normalized(result,category,slot["method"]))
                    scored.append(dict(slot,scored=name,state="COMPLETED"))
                del donor,query,offered,rows,result
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
            session.check()
            session.write("report.json",dict(at=shared.now(),report=report,version=VERSION,
                evidence="EXPOSED_SOURCE_MATCHED_DEVELOPMENT; separately versioned zero-fit software replay",
                parent_original_screen="FAILED; original six cells remain FAILED",new_fits_HTTP=0,
                query_prediction_row_incidences=sequence.rows,parent_models_loaded=6,
                promotion="NONE",future_confirmation="REQUIRED"),freeze=False)
            state="COMPLETED"
    except BaseException as error:
        session.failure("BINARY_RECOVERY_FAILURE.json",error);raise
    finally:
        session.write("BINARY_RECOVERY_FINISHED.json",dict(state=state,phase=phase,
            query_prediction_row_incidences=sequence.rows,frozen_cells=len(sequence.frozen),
            global_freeze=sequence.global_frozen,retention=session.storage.report_retention()),freeze=False)
