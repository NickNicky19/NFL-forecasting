"""Synthetic complete-law archive and coherent-publication controls.

The finite law fixture uses real prepared LeafCDF prediction without fitting or
NFL data. Explicit fixture authority supplies metadata/native acceptance for
unit tests; these tests never certify real Root/Actions/model admission.
"""
from copy import deepcopy
from datetime import timedelta
import gzip
import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import subprocess
import sys

import numpy as np
import pandas as pd
from scipy import sparse
import pytest

from nfl_lab import weekly_mae_point_inference_v2_1 as mae
from nfl_lab import weekly_future_inference as legacy
from nfl_lab import weekly_mae_display_archive_v1 as display
from nfl_lab import audit_weekly_archive_v1 as archive, audit_weekly_public_v1 as public
from nfl_lab import gha_private_checkpoint as cp, private_draft_store as store
from nfl_lab.operational_storage import OperationalStorage
from nfl_lab.cdf_engine import LeafCDFModel, SupportPrior
from tools import persist_state
from test_private_draft_store_v2 import SOURCE
from test_audit_weekly_archive_v1 import ROLES

BASE = Path(archive.__file__).resolve().parents[1]

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()

class FixedDesign:
    def transform(self, frame):
        return np.zeros((len(frame), 1))


class FixedForest:
    """Zero-fit shell. Real LeafCDF builds its real sparse leaf laws around it."""
    estimators_ = (None,)

    def apply(self, values):
        return np.zeros((len(values), 1), dtype=np.int64)


class Clock:
    def __init__(self, value="2099-10-31T00:08:00Z"):
        self.value = legacy.utc(value)

    def __call__(self):
        self.value += timedelta(microseconds=1)
        return self.value


class SyntheticPreparedLeaf:
    def __init__(self, directory, *, target="rush_att", support="count", no_prior=False,
                 rb_prior_q=.75, late_fit=False, storage=None):
        self.root, self.storage = Path(directory), storage
        category = dict(target=target, state="READY", support=support,
            modeled_roles=["RB"], primary_roles=["RB"],
            panels={"base": ["f_fixture"], "context": ["f_fixture"]})
        if support == "count":
            priors = {"RB": SupportPrior("count", q=rb_prior_q), "FB": SupportPrior("count", q=.5)}
            global_prior = SupportPrior("count", q=.9)
            atoms = np.array([0., 8.])
        else:
            priors = {"RB": SupportPrior("signed_integer", center=-3, q=.75),
                      "FB": SupportPrior("signed_integer", center=-2, q=.5)}
            global_prior = SupportPrior("signed_integer", center=-5, q=.9)
            atoms = np.array([-9., 8.])
        if no_prior:
            priors, global_prior = {}, None
        model = LeafCDFModel(category, "base", FixedDesign(), FixedForest(), atoms,
            leaf_histograms=[sparse.csr_matrix([[.8, .2]])], priors=priors, global_prior=global_prior)
        train = pd.DataFrame([dict(season=2098, week=1, game_id="fictional-old-" + str(i),
            player_id="fictional-train-" + str(i), position="RB", kickoff_utc="2098-06-01T00:00:00Z",
            outcome_available_utc="2098-06-08T00:00:00Z", **{target: i}) for i in range(3)])
        model.training_binding = train.copy()
        model.prior_training_binding = train.copy()
        model.weekly_fit_receipt = dict(training_source_capture_completed_at="2098-07-01T00:00:00Z",
            training_started_at="2098-07-02T00:00:00Z", training_completed_at="2098-07-03T00:00:00Z")
        if late_fit:
            model.weekly_fit_receipt["training_completed_at"] = "2099-11-01T00:00:00Z"
        self.frame = pd.DataFrame([dict(season=2099, week=8, game_id="fictional-game",
            player_id="fictional-player-" + str(i), team="A", opponent="B", position=role,
            kickoff_utc="2099-10-31T03:00:00Z", cutoff_utc="2099-10-31T01:00:00Z",
            f_player_games_prior=history, f_fixture=1.,
            feature_max_source_available_utc=None if i == 2 else "2099-10-30T20:00:00Z")
            for i, (role, history) in enumerate([("RB", 4.), ("FB", 3.), ("RB", 0.), ("ZZ", 2.)])],
            index=[91, 13, 44, 8])
        self.contract = dict(source_policy_sha256=cp.POLICY_SHA, feature_builder_sha256="b" * 64,
            availability_rule="FROZEN_KICKOFF_PLUS_7DAY_RECONSTRUCTION")
        raw = self.put_bytes("raw/fictional-source", b"FICTIONAL_SOURCE_NOT_NFL_DATA")
        self.artifact = legacy.export_trained_artifact(self.root / "artifact", model,
            family="leaf_cdf_base", method_id="LAB_CDF", training_frame=train,
            training_cutoff_utc="2098-09-01T00:00:00Z", source_contract=self.contract,
            training_sources=[raw], replay_fixture=self.frame, storage=self.storage)
        self.authentications = []

        def authenticate(items):
            self.authentications.append(deepcopy(items))
            for ref in items:
                if legacy.binding(ref["path"]) != ref:
                    raise ValueError("FICTIONAL_AUTHENTICATION_FAILED")
            return {r["path"]: deepcopy(r) for r in items}

        self.session = legacy.FutureInferenceSession(authenticate)
        self.session.prepare([self.artifact])
        self.manifest, self.model = self.session.models[self.artifact["sha256"]]
        source = dict(schema_version="audit-weekly-runtime-v1-source", state="FRESH_E7_SOURCE_PREPARED",
            fits=0, protected_confirmation_reads=0, asof_utc="2099-10-31T00:05:00Z",
            actual_source_started_at="2099-10-31T00:00:00Z", actual_completed_at="2099-10-31T00:06:00Z",
            raw={"fictional": raw}, manifest={"source_receipts": {"fictional": dict(status="acquired",
                bytes=raw["bytes"], sha256=raw["sha256"], retrieved_utc="2099-10-31T00:04:00Z")}})
        self.source_ref = self.put("source.json", source)
        self._counter = 0
        self.rebind_features()
        self.doc = dict(schema_version=mae.PROFILE_VERSION, selection_product="stat_point_mae_v2",
            selection_metric="MAE", target=target, scoring_target=target, base_learner_id="LAB_CDF",
            method_id="LAB_CDF_FULL_LAW_MEDIAN_V2", artifact=self.artifact,
            base_procedure_version=self.manifest["procedure_version"], procedure_version="",
            feature_schema_sha256=mae.feature_schema(self.manifest), public_roles=["RB"],
            registered_at="2099-10-30T00:00:00Z", owner_admission_receipt_sha256="c" * 64,
            adapter_pins=mae.implementation_pins())
        self.doc["procedure_version"] = mae.view_procedure(self.doc)
        self.admission_requests = []

        def verify_owner(body, request):
            # Independently configured fixture authority, never a client flag.
            self.admission_requests.append(deepcopy(request))
            if body != canonical(self.doc):
                raise ValueError("FICTIONAL_OWNER_PROFILE_NOT_REGISTERED")
            if request["phase"] == "PROFILE":
                if request["artifact"] != self.artifact:
                    raise ValueError("FICTIONAL_OWNER_ARTIFACT_NOT_ADMITTED")
            elif request["phase"] == "CURRENT_SNAPSHOT":
                expected = dict(phase="CURRENT_SNAPSHOT", point_profile_sha256=hashlib.sha256(body).hexdigest(),
                    source_receipt=self.source_ref, feature_capture_receipt=self.context["feature_capture_receipt"],
                    query_projection_sha256=legacy.frame_digest(legacy.query_projection(self.frame, self.manifest["features"])),
                    information_cutoff_utc="2099-10-31T00:05:00+00:00")
                if request != expected:
                    raise ValueError("FICTIONAL_OWNER_SNAPSHOT_NOT_ADMITTED")
            else:
                raise ValueError("FICTIONAL_OWNER_UNKNOWN_PHASE")
        self.verify_owner = verify_owner
        self.profile = mae.bind_profile(self.session, self.doc, verify_owner_admission=verify_owner)

    def put_bytes(self, name, body):
        path = self.root / name
        self.storage.write_bytes(path, body)
        return legacy.binding(path)

    def put(self, name, value):
        return self.put_bytes(name, canonical(value))

    def rebind_features(self):
        self._counter += 1
        projection = legacy.query_projection(self.frame, self.manifest["features"])
        features = self.put_bytes("features-" + str(self._counter) + ".opaque", b"FICTIONAL_FEATURE_CAPTURE")
        raw = json.loads(Path(self.source_ref["path"]).read_bytes())["raw"]
        capture = dict(schema_version="weekly-feature-capture-v1", source_contract=self.contract,
            query_projection_sha256=legacy.frame_digest(projection), feature_binding=features,
            source_bindings=list(raw.values()), capture_started_at="2099-10-31T00:06:01Z",
            feature_persist_completed_at="2099-10-31T00:07:00Z")
        self.capture_ref = self.put("feature-capture-" + str(self._counter) + ".json", capture)
        self.context = dict(cutoff_utc="2099-10-31T01:00:00Z",
            weekly_decision_cutoff_utc="2099-10-30T23:59:00Z", slate_id="fictional-slate",
            source_contract=self.contract, evidence_lane="original_pregame", reference_stream="candidate",
            query_source_sha256=features["sha256"], feature_capture_receipt=self.capture_ref)

    def predict(self, **kwargs):
        chunks = mae.predict_point_chunks(self.session, self.profile, self.frame,
            context=self.context, source_receipt=self.source_ref, clock=kwargs.pop("clock", Clock()), **kwargs)
        return [row for chunk in chunks for row in chunk]

    def close(self):
        self.session.close()


@pytest.fixture
def point_packet(tmp_path,monkeypatch):
    """Independent fictional authority; no actual native admission is asserted."""
    policy=cp.strict_json((BASE/"config/operational-source-policy-v2.json").read_bytes())
    storage=OperationalStorage(tmp_path/"cache",policy,state=tmp_path/"state")
    storage.register_root(tmp_path)
    model=SyntheticPreparedLeaf(tmp_path/"model",target="pass_int",storage=storage)
    aliases={}
    def alias(name,ref): aliases[name]=deepcopy(ref);return ref
    def put(name,value,raw=False):
        destination=tmp_path/"capture"/name
        storage.write_bytes(destination,value if raw else canonical(value))
        return alias(name,cp.binding(destination))
    root=dict(schema_version=display.ROOT_V5,approved=True,publication=True,source_sha=SOURCE,jobs=dict(ROLES),
        issued_at_utc="2099-10-30T22:00:00Z",mae_registration=dict(path=display.metadata.REGISTRATION_PATH,bytes=1,sha256="2"*64),
        mae_helper_pins={"nfl_lab/weekly_mae_display_archive_v1.py":"3"*64,
            "nfl_lab/weekly_mae_point_inference_v2_1.py":mae.implementation_pins()["weekly_mae_point_inference_v2_1.py"],
            "nfl_lab/next_checkpoint_median_policy_v2_view.py":mae.implementation_pins()["next_checkpoint_median_policy_v2_view.py"]})
    cfg=dict(categories=[dict(target=t,features=model.manifest["features"],public_roles=["RB"],modeled_roles=["RB"],
        source_contract=model.contract,effective_model_sha256=model.manifest["model"]["sha256"],
        effective_base_procedure_version=model.manifest["procedure_version"],effective_transport_manifest_sha256="e"*64,
        effective_verified_reader_manifest_sha256="f"*64) for t in display.TARGETS])
    root_sha=display.digest(root)
    def fixture_profile(root_value,source_root):
        assert root_value==root,"fixture authority rejects changed Root bytes"
        return deepcopy(cfg)
    monkeypatch.setattr(display.metadata,"validate_root_extension",fixture_profile)
    profile=display.checked_profile(root,root_sha,BASE)
    model.doc.update(method_id="MAE_DISPLAY_LEAF_pass_int",registered_at=root["issued_at_utc"],owner_admission_receipt_sha256=root_sha)
    model.doc["procedure_version"]=mae.view_procedure(model.doc)
    model.profile=mae.bind_profile(model.session,model.doc,verify_owner_admission=model.verify_owner)
    prepared=put("context/prepared.json",dict(schema_version=archive.RUNTIME+"-prepared"))
    alias("context/source.json",model.source_ref)
    feature_capture=alias("runtime/features.capture.json",model.capture_ref)
    feature=json.loads(Path(feature_capture["path"]).read_bytes())
    alias("runtime/features.parquet",feature["feature_binding"])
    out=io.BytesIO();model.frame.to_parquet(out,index=False)
    queries=put("runtime/queries.parquet",out.getvalue(),True)
    projection=dict(feature,parent_shared_capture=feature_capture,projection_kind="AUTHENTICATED_SUBSET_OF_SAME_IMMUTABLE_SHARED_FEATURE_SNAPSHOT",
        projection_features=model.manifest["features"],projection_eligible_roles=sorted(set(model.frame.position)),projection_rows=len(model.frame),
        projection_descriptor_started_at="2099-10-31T00:07:55Z")
    projection_name="runtime/mae-display/views/0/projections/"+display.digest(["fictional-contract"])+".json"
    projection_ref=put(projection_name,projection)
    model.context["feature_capture_receipt"]=projection_ref
    candidates=model.predict()
    identities=[]
    for i,q in enumerate(model.frame.to_dict("records")):
        identity=dict(gsis_id=q["player_id"],gsis_game_id=q["game_id"],website_game_id="123456789",sleeper_id=str(101+i),website_player_id=str(101+i),
            team=q["team"],opponent=q["opponent"],kickoff_utc=q["kickoff_utc"],query_source_sha256=queries["sha256"],schedule_source_sha256="4"*64,
            identity_bridge_kind="EXACT_ORIGINAL_WEEKLY_ROSTER_AND_SCHEDULE_NOT_NAMES",actual_visible_board_compatibility="NOT_YET_CHECKED")
        identity["identity_binding_sha256"]=display.wire.digest(identity);identities.append(identity)
    bridge=put("runtime/IDENTITY_BRIDGE.json",dict(schema_version=archive.RUNTIME+"-identity",identities=identities,name_matching=False))
    put("runtime/WEEKLY_CHOICE.json",dict(slate=dict(season=2099,week=8,game_cutoffs={"fictional-game":"2099-10-31T01:00:00Z"})))
    put("prepared/relocated_replay.json",dict(slots=[dict(target="pass_int",method_id="LAB_CDF",manifest_sha256=model.artifact["sha256"],
        procedure_version=model.manifest["procedure_version"],model_sha256=model.manifest["model"]["sha256"],transport_manifest_sha256="e"*64)]))
    put("context/epoch.json",dict(replay_catalog=dict(slots=[dict(target="pass_int",method_id="LAB_CDF",manifest_sha256="f"*64,
        model_sha256=model.manifest["model"]["sha256"],procedure_version=model.manifest["procedure_version"])])))
    profiles={}
    for target in display.TARGETS:
        p=deepcopy(model.doc);p.update(target=target,scoring_target=target,method_id="MAE_DISPLAY_LEAF_"+target)
        p["procedure_version"]=mae.view_procedure(p);profiles[target]=p
    catalog=put("prepared/mae-display/PROFILE_CATALOG.json",dict(schema_version="weekly-mae-display-runtime-v1-prevalue-catalog",scope=display.SCOPE,
        root_go_sha256=root_sha,registration=root["mae_registration"],prepared=prepared,profiles=profiles,current_values_used=False,
        created_at="2099-10-30T23:57:00Z",public_export_authorized=False))
    catalog_completion=put("prepared/mae-display/CATALOG_COMPLETION.json",dict(schema_version="weekly-mae-display-runtime-v1-catalog-completion",
        catalog=catalog,completed_at="2099-10-30T23:58:00Z",current_values_used=False,root_go_sha256=root_sha))
    put("runtime/mae-display/CATALOG_BINDING.json",dict(catalog=catalog,completion=catalog_completion,root_go_sha256=root_sha))
    first=candidates[0]
    source={k:first[k] for k in display.wire.SOURCE_KEYS if k in first}
    source.update(source_contract_sha256=display.wire.digest(first["source_contract"]),source_receipt_sha256=first["source_receipt"]["sha256"],
        feature_capture_receipt_sha256=projection_ref["sha256"],feature_binding_sha256=first["feature_binding"]["sha256"],
        feature_capture_completed_at=feature["feature_persist_completed_at"],public_roles=["RB"],identity_bridge_sha256=bridge["sha256"])
    registry=put("runtime/mae-display/SOURCE_REGISTRY.json",dict(schema_version="weekly-mae-display-runtime-v1-source-registry",root_go_sha256=root_sha,
        created_before_point_values=True,registered_at="2099-10-31T00:07:57Z",records=[source]))
    rows=[]
    for c,identity in zip(candidates,identities):
        public_identity={k:identity[k] for k in ("website_game_id","sleeper_id","identity_binding_sha256")}
        public_identity["identity_bridge_sha256"]=bridge["sha256"]
        row=dict(schema_version="weekly-mae-display-runtime-v1-identity-envelope",candidate=c,public_identity=public_identity,
            candidate_sha256=c["candidate_sha256"],cutoff_utc=c["issue_deadline_utc"],operational_eligible=c["operational_eligible"],legacy_ranking_policy_unchanged=True)
        row["envelope_sha256"]=display.wire.digest(row);rows.append(row)
    point_body=put("runtime/mae-display/candidates/pass_int.jsonl.gz",gzip.compress(b"".join(canonical(r)+b"\n" for r in rows),mtime=0),True)
    completion=dict(schema_version=legacy.VERSION+"-persistence",state="PERSISTED",binding=point_body,rows=len(rows),
        persist_started_at="2099-10-31T00:08:30Z",completed_at="2099-10-31T00:09:00Z",private_only=True,
        remote_durability="NOT_ESTABLISHED",scientific_qualification=False)
    put("runtime/mae-display/candidates/pass_int.jsonl.completion.json",completion)
    statuses=[]
    for target in display.TARGETS:
        status=dict(target=target,state="CAPTURED" if target=="pass_int" else "FAILED_RETAINED",failure=None if target=="pass_int" else "FICTIONAL_TARGET_FAILURE",
            expected_rows=len(rows),issued_rows=len(rows) if target=="pass_int" else 0,persistence=completion if target=="pass_int" else None,
            traversal_rows_requested=2*len(rows),traversal_rows_reserved=2*len(rows) if target=="pass_int" else 0,artifact=model.artifact,
            profile_sha256=display.digest(profiles[target]))
        put(f"runtime/mae-display/status/{target}.json",status);statuses.append(status)
    # Retain a real failed partial body without pretending it is a full category.
    put("runtime/mae-display/candidates/pass_yd.jsonl.gz",b"FICTIONAL_PARTIAL_BYTES",True)
    selected=put("runtime/selected.jsonl.gz",gzip.compress(b"FICTIONAL_LEGACY_SELECTED\n",mtime=0),True)
    legacy_completion=dict(state="PERSISTED",binding=selected,rows=1,completed_at="2099-10-31T00:07:45Z")
    legacy_slots=[dict(target=t,method_id=m,expected_rows=4) for t,_,m in cp.JOBS]
    put("runtime/CANDIDATES.json",dict(slots=legacy_slots))
    put("runtime/FINISHED.json",dict(selected=legacy_completion,prediction_rows=72,actual_completed_at="2099-10-31T00:07:50Z"))
    terminal=put("runtime/mae-display/FINISHED.json",dict(schema_version="weekly-mae-display-runtime-v1-result",state="PARTIAL_DISPLAY_CAPTURE_RETAINED",
        root_go_sha256=root_sha,source=model.source_ref,feature_capture=feature_capture,identity_bridge=bridge,prevalue_catalog=catalog,source_registry=registry,
        statuses=statuses,legacy_selected=legacy_completion,legacy_statuses_sha256=display.wire.digest(legacy_slots),legacy_prediction_rows=72,
        extra_traversal_rows_reserved=8,actual_completed_at="2099-10-31T00:09:30Z",display_only=True,ranking_policy_change=False,
        probability_policy_change=False,public_export_authorized=False,independent_archive_restore="REQUIRED"))
    def snapshot():
        return dict(files=[cp.file_item(r,n,"forecast" if n.endswith(".jsonl.gz") else "control") for n,r in sorted(aliases.items())],
            census=dict(actual_collected_at="2099-10-31T00:10:45Z",mae_display_profile=dict(root_go_sha256=root_sha,registration_sha256=root["mae_registration"]["sha256"])))
    def inspect():return display.inspect_capture(snapshot(),lambda n:Path(aliases[n]["path"]),profile)
    q=SimpleNamespace(root=root,root_sha=root_sha,profile=profile,storage=storage,model=model,aliases=aliases,put=put,
        snapshot=snapshot,inspect=inspect,rows=rows,statuses=statuses,completion=completion,source=source)
    yield q
    model.close()


def native_packet(q):
    """Private class keys are used only by this independent fictional authority."""
    journal=Path(q.aliases["context/prepared.json"]["path"]).parents[2]/"fixture-journal"
    journal.mkdir(mode=0o700)
    job=dict(job_id=ROLES["consume"],api_job_id=779,workflow_ref=store.REPO+"/.github/workflows/lab.yml@refs/heads/fixture")
    def forbidden_transport(*args,**kwargs):raise AssertionError("NO_TRANSPORT_IN_POINT_EXPORT")
    client=archive.Client("ghs_FICTIONAL", "123", journal=journal,source_sha=q.root["source_sha"],job=job,
        operation="restore",readonly=True,transport=forbidden_transport)
    identity=cp.client_identity(client)
    producer=dict(identity,job_id=ROLES["produce"],api_job_id=777,process_identity="5"*64)
    restorer=dict(identity,job_id=ROLES["restore"],api_job_id=778,process_identity="6"*64)
    snapshot=q.snapshot();proof=dict(identity=producer,actual_started_at="2099-10-31T00:10:30Z")
    snapshot.update(schema_version=archive.VERSION+"-index",root_go_sha256=q.root_sha,producer_proof=proof,
        files_sha256=display.digest(snapshot["files"]))
    encoded=gzip.compress(canonical(snapshot),mtime=0)
    index=q.put("private/index.gz",encoded,True);aliases={n:r for n,r in q.aliases.items() if n!="private/index.gz"}
    record=dict(exporter=identity,producer=producer,restorer=restorer,accepted_at="2099-10-31T01:15:00Z",
        archive_index_sha256=index["sha256"],archive_files_sha256=snapshot["files_sha256"],workflow_sha256="7"*64,
        selected_body_sha256=aliases["runtime/selected.jsonl.gz"]["sha256"],producer_proof_sha256=display.digest(proof),
        restorer_proof_sha256="8"*64,exporter_proofs_sha256="9"*64,compatibility_catalog_sha256="a"*64,source_catalog_sha256="b"*64,
        durability_clocks=dict(archive_index_created_at="2099-10-31T00:11:00Z",producer_job_completed_at_upper_bound="2099-10-31T00:12:00Z",
            restorer_witness_completed_at="2099-10-31T01:10:00Z",exporter_restore_proof_created_at="2099-10-31T01:14:00Z"))
    class FixtureCatalog:
        sha256="a"*64;provenance=dict(source_catalog=dict(sha256="b"*64))
        def verify(self):return None
    policy=dict(source_sha=q.root["source_sha"],source_branch="fixture",source_policy_sha256=cp.POLICY_SHA,
        jobs=dict(produce=producer["job_id"],restore=restorer["job_id"],consume=identity["job_id"]))
    live=public.LiveAcceptance(record,dict(storage=q.storage,catalog=FixtureCatalog(),policy=policy,aliases=deepcopy(aliases)),public._LIVE)
    consumed=dict(current=identity,aliases=aliases,index_ref=index,index_sha256=index["sha256"],files_sha256=snapshot["files_sha256"],producer_proof=proof,
        archive=dict(run_id=client.run_id,source_sha=client.source_sha,root_go_sha256=q.root_sha,jobs=policy["jobs"]),
        validation=dict(qualified_selected=True,mae_display=q.inspect()["summary"]),witness_descriptor=dict(entry=dict(payload=dict(sha256="c"*64))))
    return live,client,consumed


def replace_alias(q,name,value,raw=False):
    number=getattr(q,"replacement_number",0)+1;q.replacement_number=number
    temporary=f"fixture-replacements/{number}"
    ref=q.put(temporary,value,raw);q.aliases.pop(temporary);q.aliases[name]=ref
    return ref


def replace_category_rows(q,rows):
    replacement=replace_alias(q,"runtime/mae-display/candidates/pass_int.jsonl.gz",
        gzip.compress(b"".join(canonical(r)+b"\n" for r in rows),mtime=0),True)
    q.completion=dict(q.completion,binding=replacement)
    replace_alias(q,"runtime/mae-display/candidates/pass_int.jsonl.completion.json",q.completion)
    q.statuses[1]=dict(q.statuses[1],persistence=q.completion)
    replace_alias(q,"runtime/mae-display/status/pass_int.json",q.statuses[1])
    terminal=json.loads(Path(q.aliases["runtime/mae-display/FINISHED.json"]["path"]).read_bytes())
    terminal["statuses"]=q.statuses
    replace_alias(q,"runtime/mae-display/FINISHED.json",terminal)


def test_complete_law_partial_targets_are_retained_and_independently_scoped(point_packet):
    q=point_packet;result=q.inspect();summary=result["summary"]
    assert summary["state"]=="POINT_CATEGORIES_RESTORED",summary
    assert summary["eligible_rows"]==2 and set(result["captures"])=={"pass_int"}
    assert [s["state"] for s in summary["targets"]]==["FAILED_RETAINED","RESTORED_COMPLETE_CATEGORY","FAILED_RETAINED"]
    assert "runtime/mae-display/candidates/pass_yd.jsonl.gz" in summary["observed"]
    assert q.rows[2]["candidate"]["forecast_value"]==2 and q.rows[2]["candidate"]["separate_expected_mean"]==3
    assert Path(q.aliases["runtime/mae-display/candidates/pass_yd.jsonl.gz"]["path"]).read_bytes()==b"FICTIONAL_PARTIAL_BYTES"


@pytest.mark.parametrize("mutation",["missing_completion","late_local","bridge","functional","drop_row","duplicate_row","source_hash"])
def test_invalid_complete_category_cannot_be_admitted_and_failed_bytes_remain(point_packet,mutation):
    q=point_packet
    if mutation=="missing_completion":del q.aliases["runtime/mae-display/candidates/pass_int.jsonl.completion.json"]
    elif mutation=="late_local":
        changed=dict(q.completion,completed_at="2099-10-31T01:00:00Z")
        q.aliases.pop("runtime/mae-display/candidates/pass_int.jsonl.completion.json")
        q.put("replacement/completion.json",changed);q.aliases["runtime/mae-display/candidates/pass_int.jsonl.completion.json"]=q.aliases.pop("replacement/completion.json")
    else:
        rows=deepcopy(q.rows)
        if mutation=="bridge":rows[0]["public_identity"]["sleeper_id"]="999"
        if mutation=="functional":
            rows[0]["candidate"]["functional_proof"]["cdf_below"]=.5
            rows[0]["candidate"].pop("candidate_sha256");rows[0]["candidate"]["candidate_sha256"]=display.digest(rows[0]["candidate"])
            rows[0]["candidate_sha256"]=rows[0]["candidate"]["candidate_sha256"]
        if mutation=="drop_row":rows.pop()
        if mutation=="duplicate_row":rows[-1]=deepcopy(rows[0])
        if mutation=="source_hash":rows[0]["candidate"]["source_receipt"]["sha256"]="f"*64
        for row in rows:
            row.pop("envelope_sha256");row["envelope_sha256"]=display.wire.digest(row)
        replace_category_rows(q,rows)
    result=q.inspect()
    assert not result["captures"] and result["summary"]["eligible_rows"]==0,result["summary"]
    assert "runtime/mae-display/candidates/pass_yd.jsonl.gz" in result["summary"]["observed"]


def test_v1_archive_remains_closed_and_v5_restored_validation_is_additive(point_packet,monkeypatch):
    q=point_packet
    with pytest.raises(store.StoreError,match="V1_ARCHIVE_HAS_NO_DISPLAY_PROFILE_OR_ALIASES"):
        archive.validate_capture(q.snapshot(),lambda n:Path(q.aliases[n]["path"]),complete=False)
    monkeypatch.setattr(archive,"_validate_legacy_capture",lambda *a,**k:dict(qualified_selected=True,candidate_rows=72))
    result=archive.validate_capture(q.snapshot(),lambda n:Path(q.aliases[n]["path"]),complete=True,display_profile=q.profile)
    assert result["qualified_selected"] is True and result["candidate_rows"]==72 and result["mae_display"]["eligible_rows"]==2
    assert not archive.allowed_runtime_name("mae-display/FINISHED.json")
    assert display.allowed_runtime_name("mae-display/FINISHED.json")
    assert not display.allowed_runtime_name("mae-display/model.joblib")


def test_same_process_native_export_preserves_actual_clocks_bridge_and_strict_wire(point_packet):
    q=point_packet;live,client,consumed=native_packet(q)
    exported=display.native_export(live,client,consumed,q.profile,legacy_feed_sha256="d"*64,created_at="2099-10-31T04:00:00Z")
    feed,receipt=display.validate_public_pair(display.wire.canonical(exported["document"]),gzip.compress(display.wire.canonical(exported["receipt"]),mtime=0))
    assert receipt["categories"]==["pass_int"] and receipt["rows"]==2 and client.calls==0
    assert [s["target"] for s in receipt["unavailable"]]==["pass_yd","rush_rec_yd"]
    row=next(r for r in feed["rows"] if r["player_id"]==q.rows[2]["candidate"]["player_id"])
    assert (row["selected_projection"],row["expected_mean"],row["website_game_id"],row["sleeper_id"])==(2,3,"123456789","103")
    assert row["retained_capture"] is True and row["issued_at"]==q.rows[2]["candidate"]["issued_at"]
    assert row["persistence_completed_at"]=="2099-10-31T00:12:00Z" and row["readback_completed_at"]=="2099-10-31T01:15:00Z"
    assert receipt["readback_sha256"]==display.wire.digest(exported["private_readback"])
    assert set(receipt)==display.RECEIPT_KEYS and "aliases" not in receipt and b"/tmp/" not in display.wire.canonical(feed)


def test_json_acceptance_changed_native_process_and_changed_live_inputs_rejected(point_packet):
    q=point_packet;live,client,consumed=native_packet(q)
    with pytest.raises(ValueError,match="ACTUAL_NATIVE_LIVE_POINT_ACCEPTANCE_REQUIRED"):
        display.native_export(dict(live.record),client,consumed,q.profile,legacy_feed_sha256="d"*64,created_at="2099-10-31T01:20:00Z")
    client.process="f"*64
    with pytest.raises(ValueError,match="SAME_NATIVE_EXPORTER"):
        display.native_export(live,client,consumed,q.profile,legacy_feed_sha256="d"*64,created_at="2099-10-31T01:20:00Z")
    live.inputs["policy"]["source_sha"]="e"*40
    with pytest.raises(public.PublicError,match="LIVE_ACCEPTANCE_OR_INPUTS_CHANGED"):
        display.native_export(live,client,consumed,q.profile,legacy_feed_sha256="d"*64,created_at="2099-10-31T01:20:00Z")


def test_actual_archive_durability_at_deadline_is_unavailable_readback_later_is_allowed(point_packet):
    q=point_packet;live,client,consumed=native_packet(q)
    live.record["durability_clocks"]["producer_job_completed_at_upper_bound"]="2099-10-31T01:00:00Z"
    # Re-mint only the explicit fictional authority; actual production records
    # cannot be changed after native verify_live seals them.
    live=public.LiveAcceptance(live.record,live.inputs,public._LIVE)
    exported=display.native_export(live,client,consumed,q.profile,legacy_feed_sha256="d"*64,created_at="2099-10-31T01:20:00Z")
    assert exported["document"] is None and exported["receipt"]["state"]=="MAE_UNAVAILABLE"
    assert next(s for s in exported["receipt"]["targets"] if s["target"]=="pass_int")["reason"]=="ARCHIVE_DURABILITY_NOT_PROVEN_BEFORE_ORIGINAL_DEADLINE"


def legacy_pair_fixture(q,live,consumed):
    legacy_body=canonical(dict(season=2099,week=8,created_at="2099-10-31T01:20:00Z",rows=[dict(fictional_legacy_unchanged=True)]))
    legacy_sha=display.sha(legacy_body)
    state=q.storage.register_root(Path(q.aliases["context/prepared.json"]["path"]).parents[2]/"public-state")
    legacy=f"public/weekly-adaptive-v1/2099-W08/20991031T012000.000000Z--{legacy_sha}.json"
    legacy_receipt=f"public/weekly-adaptive-v1/receipts/{legacy_sha}.json.gz"
    from nfl_lab import audit_weekly_delivery_v1 as legacy_delivery
    # Explicit fixture old receipt; actual old public_pair/verify_live executes
    # unchanged in the retained integrated legacy suite, not invented here.
    old_receipt={k:"0"*64 for k in legacy_delivery.RECEIPT_KEYS}
    jobs={role:dict(job_id=live.record[key]["job_id"],api_job_id=live.record[key]["api_job_id"])
        for role,key in (("produce","producer"),("restore","restorer"),("consume","exporter"))}
    old_receipt.update(source_sha=live.record["exporter"]["source_sha"],run_id=live.record["exporter"]["run_id"],root_go_sha256=q.root_sha,
        workflow_sha256=live.record["workflow_sha256"],jobs=jobs,archive_index_sha256=consumed["index_sha256"],
        archive_files_sha256=consumed["files_sha256"],reader_witness_sha256=consumed["witness_descriptor"]["entry"]["payload"]["sha256"],
        schema_version=legacy_delivery.VERSION+"-public-receipt",feed_sha256=legacy_sha,feed_bytes=len(legacy_body),rows=1,
        created_at="2099-10-31T01:20:00Z",categories=["pass_att"],fits=0,raw_or_models_public=False)
    files={}
    for n,b in ((legacy,legacy_body),(legacy_receipt,gzip.compress(canonical(old_receipt),mtime=0))):
        q.storage.write_bytes(state/n,b);files[n]=display.sha(b)
    return state,files,legacy_sha


def prepared_four(q):
    live,client,consumed=native_packet(q)
    state,files,legacy_sha=legacy_pair_fixture(q,live,consumed)
    exported=display.native_export(live,client,consumed,q.profile,legacy_feed_sha256=legacy_sha,created_at="2099-10-31T01:20:00Z")
    files.update(display.write_pair(q.storage,state,exported))
    return state,files


def test_actual_delivery_native_preparation_keeps_legacy_pair_and_builds_separate_point_pair(point_packet):
    from nfl_lab import audit_weekly_delivery_v1 as delivery
    q=point_packet;live,client,consumed=native_packet(q)
    state,legacy_files,legacy_sha=legacy_pair_fixture(q,live,consumed)
    before={n:Path(state/n).read_bytes() for n in legacy_files}
    output=q.storage.register_root(state.parent/"delivery-output")
    exported,point_files,unavailable=delivery._prepare_display_pair(q.storage,state,output,live,client,consumed,q.profile,legacy_files,
        clock=lambda:public.feed.utc("2099-10-31T01:20:00Z"))
    assert unavailable is None and exported["receipt"]["legacy_feed_sha256"]==legacy_sha and len(point_files)==2
    assert {n:Path(state/n).read_bytes() for n in legacy_files}==before
    assert cp.binding(output/"POINT_CAPTURE_READBACK.json")["sha256"]==exported["receipt"]["readback_sha256"]
    assert persist_state.validate_v5_public_export(state,dict(legacy_files,**point_files),cp.POLICY_SHA)
    assert client.calls==0


def test_actual_delivery_optional_failure_retains_legacy_and_explicit_sanitized_unavailability(point_packet,monkeypatch):
    from nfl_lab import audit_weekly_delivery_v1 as delivery
    q=point_packet;live,client,consumed=native_packet(q)
    state,legacy_files,_=legacy_pair_fixture(q,live,consumed)
    before={n:Path(state/n).read_bytes() for n in legacy_files}
    def failed(*args,**kwargs):raise ValueError("secret provider library text /private/raw/player")
    monkeypatch.setattr(display,"native_export",failed)
    output=q.storage.register_root(state.parent/"failed-delivery-output")
    exported,point_files,unavailable=delivery._prepare_display_pair(q.storage,state,output,live,client,consumed,q.profile,legacy_files,
        clock=lambda:public.feed.utc("2099-10-31T01:20:00Z"))
    assert not point_files and exported["document"] is None and exported["receipt"]["state"]=="MAE_UNAVAILABLE"
    assert exported["receipt"]["reason"]=="POINT_PREPARATION_FAILED_RETAINED"
    retained=archive.read_owned(q.storage,unavailable)
    assert retained==exported["receipt"] and b"secret" not in canonical(retained) and b"/private/" not in canonical(retained)
    assert {n:Path(state/n).read_bytes() for n in legacy_files}==before


def test_actual_delivery_zero_point_rows_keeps_exact_legacy_pair_and_owned_unavailable_receipt(point_packet):
    from nfl_lab import audit_weekly_delivery_v1 as delivery
    q=point_packet
    q.statuses[1]=dict(q.statuses[1],state="FAILED_RETAINED",failure="FICTIONAL_ADDITIONAL_TARGET_FAILURE")
    replace_alias(q,"runtime/mae-display/status/pass_int.json",q.statuses[1])
    terminal=json.loads(Path(q.aliases["runtime/mae-display/FINISHED.json"]["path"]).read_bytes());terminal["statuses"]=q.statuses
    replace_alias(q,"runtime/mae-display/FINISHED.json",terminal)
    live,client,consumed=native_packet(q)
    state,legacy_files,_=legacy_pair_fixture(q,live,consumed)
    output=q.storage.register_root(state.parent/"unavailable-delivery-output")
    exported,point_files,unavailable=delivery._prepare_display_pair(q.storage,state,output,live,client,consumed,q.profile,legacy_files,
        clock=lambda:public.feed.utc("2099-10-31T01:20:00Z"))
    assert not point_files and exported["document"] is None and exported["receipt"]["state"]=="MAE_UNAVAILABLE"
    assert archive.read_owned(q.storage,unavailable)==exported["receipt"]
    assert len(persist_state.public_export_names(legacy_files))==2


def test_archive_profile_policy_import_is_stdlib_only_under_original_address_space_limit():
    script=r'''
import sys,resource,importlib.abc,json,os
resource.setrlimit(resource.RLIMIT_AS,(512 << 20,512 << 20))
class BlockModels(importlib.abc.MetaPathFinder):
 def find_spec(self,name,path=None,target=None):
  if name.split('.')[0] in {'numpy','pandas','scipy','sklearn','catboost','joblib'}:
   raise AssertionError('MODEL_IMPORT_BLOCKED:'+name)
sys.meta_path.insert(0,BlockModels());sys.path.insert(0,sys.argv[1])
from nfl_lab import weekly_mae_display_archive_v1 as helper
assert helper.allowed_runtime_name('mae-display/FINISHED.json')
assert not helper.allowed_runtime_name('mae-display/trained.joblib')
assert helper.point_policy()['fits']==0
assert not any(n.split('.')[0] in {'numpy','pandas','scipy','sklearn','catboost','joblib'} for n in sys.modules)
pages=list(map(int,open('/proc/self/statm').read().split()));page_bytes=os.sysconf('SC_PAGE_SIZE')
print(json.dumps(dict(policy_sha256=helper.wire.digest(helper.point_policy()),address_space_bytes=pages[0]*page_bytes,
 resident_bytes=pages[1]*page_bytes,address_space_limit_bytes=resource.getrlimit(resource.RLIMIT_AS)[0])))
'''
    result=subprocess.run([sys.executable,"-I","-S","-B","-c",script,str(BASE)],text=True,capture_output=True,timeout=15)
    assert result.returncode==0,result.stderr
    report=json.loads(result.stdout)
    assert display.wire.h(report["policy_sha256"])
    assert report["address_space_limit_bytes"]==512 << 20
    assert report["resident_bytes"]<=report["address_space_bytes"]<=512 << 20


def test_closed_four_file_mode_rejects_extra_paths_and_validates_exact_bytes(point_packet):
    q=point_packet;state,files=prepared_four(q)
    assert persist_state.validate_v5_public_export(state,files,cp.POLICY_SHA)==files
    legacy,point=persist_state.v5_public_export_names(files)
    with pytest.raises(ValueError):persist_state.public_export_names(files)
    for changed in (dict(files,**{"private/raw.json":"f"*64}),{n:h for n,h in files.items() if n!=point[1]}):
        with pytest.raises(ValueError):persist_state.v5_public_export_names(changed)
    changed=dict(files);changed[point[0]]="f"*64
    with pytest.raises(ValueError):persist_state.validate_v5_public_export(state,changed,cp.POLICY_SHA)
    with pytest.raises(ValueError):persist_state.validate_v5_public_export(state,files,"f"*64)
    assert persist_state.public_export_names({n:files[n] for n in legacy})==legacy


def test_coherent_four_file_publisher_stages_and_pushes_once_without_reference_writes(point_packet,monkeypatch):
    q=point_packet;state,files=prepared_four(q);calls=[];staged=[];publication=[]
    def git(*args,cwd=None,capture=False):
        calls.append(args)
        if args[:2]==("worktree","add"):
            Path(args[-2]).mkdir(parents=True)
        if args[:2]==("rev-parse","HEAD"):return "e"*40
        if args[0]=="rev-parse":return "d"*40
        if args[0]=="ls-remote":return "e"*40+"\trefs/heads/lab-state"
        return ""
    def run(args,**kwargs):
        if args[0]=="git":return SimpleNamespace(returncode=1)
        assert args[1:4]==["-m","nfl_lab.cli","publication"] and "--frozen-public-policy" in args
        publication.append(json.loads(kwargs["input"]))
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(persist_state,"git",git);monkeypatch.setattr(persist_state.subprocess,"run",run)
    monkeypatch.setattr(persist_state,"copy_state",lambda *a,**k:staged.append(dict(k["files"])))
    monkeypatch.setattr(persist_state,"stage_reviewed",lambda target,fs:staged.append(dict(fs)))
    monkeypatch.setattr(persist_state,"validate_existing_public",lambda root,ref,fs:staged.append(dict(fs)))
    persist_state.persist(BASE,state,storage=q.storage,policy_path=BASE/"config/operational-source-policy-v2.json",files=files,v5_metadata_policy=True)
    assert len([a for a in calls if a[0]=="push"])==1 and len([a for a in calls if "commit" in a])==1
    assert staged and all(m==files for m in staged) and len(publication)==1 and publication[0]["files"]==files


@pytest.fixture
def declared_archive_service_clock(monkeypatch):
    """NEW fictional chronology; no host-clock or availability assertion."""
    from datetime import datetime
    import test_audit_weekly_archive_v1 as capture_fixture
    import test_owner_private_bootstrap as qualification_fixture
    from nfl_lab import owner_private_bootstrap as owner,weekly_durable_acceptance as acceptance
    clock=SimpleNamespace(value=public.feed.utc("2099-10-31T00:20:00Z"))
    class DeclaredDatetime(datetime):
        @classmethod
        def now(cls,tz=None):
            return clock.value if tz is not None else clock.value.replace(tzinfo=None)
    def advance():
        clock.value+=timedelta(seconds=1)
        return clock.value
    clock.advance=advance
    for module in (capture_fixture,qualification_fixture,store,archive,owner,acceptance):
        monkeypatch.setattr(module,"datetime",DeclaredDatetime)
    return clock


def test_actual_collector_producer_reader_consumer_preserve_optional_failed_bytes(point_packet,tmp_path_factory,declared_archive_service_clock):
    from test_audit_weekly_archive_v1 import capture_case,Service
    q=point_packet;p=capture_case(tmp_path_factory.mktemp("v5-actual-archive"))
    partial=p.root/"mae-display/candidates/pass_int.jsonl.gz"
    p.storage.write_bytes(partial,b"FICTIONAL_ORIGINAL_PARTIAL_POINT_BODY")
    status=archive.write(p.storage,p.root/"mae-display/status/pass_int.json",dict(state="FAILED_RETAINED",failure="FICTIONAL_FAILURE"))
    folder=Path(p.context["prepared"]["path"]).parent/"mae-display"
    catalog=archive.write(p.storage,folder/"PROFILE_CATALOG.json",dict(fictional_unavailable_catalog=True))
    completion=archive.write(p.storage,folder/"CATALOG_COMPLETION.json",dict(fictional_unavailable_completion=True))
    with pytest.raises(store.StoreError,match="UNDECLARED_RUNTIME_FILE_NO_SILENT_OMISSION"):
        archive.collect(p.root,p.context,storage=p.storage,output=p.base/"v1-rejected")
    snapshot=archive.collect(p.root,p.context,storage=p.storage,output=p.base/"v5-collection",display_profile=q.profile)
    assert snapshot["census"]["archive_state"]=="COMPLETE_CAPTURE"
    names={f["logical_path"] for f in snapshot["files"]}
    assert {"prepared/mae-display/PROFILE_CATALOG.json","prepared/mae-display/CATALOG_COMPLETION.json",
        "runtime/mae-display/candidates/pass_int.jsonl.gz","runtime/mae-display/status/pass_int.json"}<=names
    clock=declared_archive_service_clock
    service=Service(p.base,qualification_at=clock.value)
    handoff=archive.produce(snapshot,service.factory(p.base/"writer-journal","produce"),service.package,storage=p.storage,
        output=p.base/"writer",root_go_sha256=q.root_sha,jobs=ROLES,pending_census=service.census,display_profile=q.profile)
    service.writer_completed=clock.advance();service.active="restore"
    clock.advance()  # The NEW reader starts strictly after producer completion.
    reader=archive.restore(handoff,service.factory(p.base/"reader-journal","restore"),service.package,storage=p.storage,
        output=p.base/"reader",root_go_sha256=q.root_sha,pending_census=service.census,display_profile=q.profile)
    service.reader_completed=clock.advance();service.active="consume"
    clock.advance()  # The NEW consumer starts strictly after reader completion.
    reader_handoff=cp.strict_json((p.base/"reader/READER_HANDOFF.json").read_bytes())
    consumer=service.factory(p.base/"consumer-journal","consume")
    before_posts=len(service.posts())
    consumed=archive.consume(reader_handoff,consumer,service.package,storage=p.storage,output=p.base/"consumer",
        root_go_sha256=q.root_sha,pending_census=service.census,display_profile=q.profile)
    assert consumed["validation"]["qualified_selected"] is True
    assert consumed["validation"]["mae_display"]["state"]=="MAE_UNAVAILABLE"
    assert consumed["validation"]==reader["validation"]
    assert archive.read_owned(p.storage,consumed["aliases"]["runtime/mae-display/candidates/pass_int.jsonl.gz"],raw=True)==b"FICTIONAL_ORIGINAL_PARTIAL_POINT_BODY"
    assert consumed["aliases"]["prepared/mae-display/PROFILE_CATALOG.json"]["sha256"]==catalog["sha256"]
    assert consumed["aliases"]["prepared/mae-display/CATALOG_COMPLETION.json"]["sha256"]==completion["sha256"]
    assert len(service.posts())==before_posts and all(c.readonly and c.calls<=40 for c in consumer.clients)


@pytest.mark.parametrize("previous_role,next_role",[("produce","restore"),("restore","consume")])
def test_declared_archive_predecessor_completion_after_next_client_start_rejects(tmp_path,declared_archive_service_clock,previous_role,next_role):
    from test_audit_weekly_archive_v1 import Service
    clock=declared_archive_service_clock;service=Service(tmp_path,qualification_at=clock.value)
    service.active=previous_role
    previous=service.factory(tmp_path/"previous",previous_role)("append")
    previous.authenticate_actions_job();identity=cp.client_identity(previous)
    clock.advance();service.active=next_role
    completed=clock.value+timedelta(seconds=1)
    if previous_role=="produce":service.writer_completed=completed
    else:service.reader_completed=completed
    reader=service.factory(tmp_path/"next",next_role)("restore")
    reader.authenticate_actions_job();jobs=archive.jobs_for(reader)
    matched=[j for j in jobs if j["id"]==identity["api_job_id"]]
    assert len(matched)==1;job=matched[0]
    assert job["name"]==identity["job_id"] and job["status"]=="completed" and job["conclusion"]=="success"
    assert job["head_sha"]==reader.source_sha and job["run_id"]==int(reader.run_id)
    assert public.feed.utc(job["completed_at"])>public.feed.utc(reader.started_at)
    before_posts=len(service.posts())
    with pytest.raises(store.StoreError,match="COMPLETED_SUCCESSFUL_ARCHIVE_PREDECESSOR"):
        archive.predecessor(reader,identity,jobs)
    assert len(service.posts())==before_posts and all(c.get_method()=="GET" and c.data is None for c in service.calls)


def test_actual_hosted_archive_request_only_root_v5_opts_into_new_closed_wire(point_packet,tmp_path,monkeypatch):
    from nfl_lab import audit_weekly_hosted_v1 as hosted,audit_weekly_template_v1 as template
    from tools import audit_weekly_archive_v1 as cli
    monkeypatch.setattr(template,"pending_recovery",lambda root:dict(pending_reservations=[]))
    runner=object.__new__(hosted.Runner)
    runner.root=tmp_path;runner.storage=point_packet.storage;runner.package_ref=dict(fictional_qualified_metadata=True)
    runner.go=dict(point_packet.root,pending_census={})
    result=runner.archive_request("produce",context={})
    assert set(result)==cli.REQUEST_KEYS|{"mae_registration"} and result["schema_version"]==display.REQUEST_V2
    assert result["mae_registration"]==runner.go["mae_registration"]
    runner.go["schema_version"]="audit-weekly-hosted-v4-root-GO"
    result=runner.archive_request("produce",context={})
    assert set(result)==cli.REQUEST_KEYS and result["schema_version"]==archive.VERSION+"-request"


@pytest.mark.parametrize("wrong",[None,"legacy_root","missing_registration","extra_key"])
def test_actual_archive_cli_requires_matching_native_root_v5_request_before_private_body_read(point_packet,tmp_path,monkeypatch,wrong):
    from tools import audit_weekly_archive_v1 as cli
    from nfl_lab import audit_weekly_template_v1 as template
    q=point_packet;root=deepcopy(q.root)
    if wrong=="legacy_root":root["schema_version"]="audit-weekly-hosted-v4-root-GO"
    root_raw=canonical(root)
    authority=dict(owner_root_go_sha256=display.sha(root_raw))
    monkeypatch.setattr(cli,"guard",lambda args,env:(authority,dict(job_id=ROLES["consume"]),object(),root_raw))
    monkeypatch.setattr(display,"checked_profile",lambda root,root_sha,source_root:q.profile)
    monkeypatch.setattr(template,"pending_recovery",lambda root:dict(pending_reservations=[]))
    request=cli.template();request.update(approved=True,phase="consume",jobs=ROLES,schema_version=display.REQUEST_V2,
        mae_registration=q.root["mae_registration"],qualified_runtime=dict(path="/fictional/native-qualified-metadata"))
    if wrong=="missing_registration":request.pop("mae_registration")
    if wrong=="extra_key":request["arbitrary_private_path"]="/private/forbidden"
    body=canonical(request);path=tmp_path/"closed-request.json";path.write_bytes(body)
    class ReachedQualifiedMetadata(Exception):pass
    reads=[]
    def read_ref(ref,cap):
        reads.append(ref);raise ReachedQualifiedMetadata()
    monkeypatch.setattr(cp,"read_ref",read_ref)
    numerical=cp.strict_json((BASE/"config/weekly-owner-private-bootstrap-v1.json").read_bytes())["numerical_environment"]
    args=SimpleNamespace(request=path,request_sha256=display.sha(body),phase="consume")
    if wrong is None:
        with pytest.raises(ReachedQualifiedMetadata):cli.run(args,numerical)
        assert len(reads)==1
    else:
        with pytest.raises(store.StoreError):cli.run(args,numerical)
        assert not reads



@pytest.mark.parametrize("fault",["before_legacy","after_collection","missing_collection","after_proof","missing_native_proof","missing_proof_clock"])
def test_repaired_terminal_requires_real_legacy_collection_and_native_boundaries(point_packet,fault):
    q=point_packet;snapshot=q.snapshot()
    if fault in {"before_legacy","after_collection"}:
        terminal=json.loads(Path(q.aliases["runtime/mae-display/FINISHED.json"]["path"]).read_bytes())
        terminal["actual_completed_at"]="2099-10-31T00:07:49Z" if fault=="before_legacy" else "2099-10-31T00:10:46Z"
        replace_alias(q,"runtime/mae-display/FINISHED.json",terminal);snapshot=q.snapshot()
    elif fault=="missing_collection":snapshot["census"].pop("actual_collected_at")
    elif fault=="after_proof":snapshot["producer_proof"]=dict(actual_started_at="2099-10-31T00:09:29Z")
    elif fault=="missing_native_proof":snapshot["schema_version"]="audit-weekly-archive-v1-index"
    else:snapshot["producer_proof"]={}
    result=display.inspect_capture(snapshot,lambda n:Path(q.aliases[n]["path"]),q.profile)
    assert result["summary"]["state"]=="MAE_UNAVAILABLE" and not result["captures"]
    assert result["summary"]["reason"] in {"POINT_TERMINAL_MUST_FOLLOW_LEGACY_AND_PRECEDE_ARCHIVE",
        "POINT_TERMINAL_REQUIRES_ACTUAL_COLLECTION_CLOCK","POINT_TERMINAL_REQUIRES_NATIVE_PRODUCER_CLOCK"}
