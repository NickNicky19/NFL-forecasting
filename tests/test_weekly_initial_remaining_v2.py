"""Fictional metadata/clocks only; no NFL bodies, HTTP, models, fits or keys."""
from contextlib import contextmanager, redirect_stdout
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from nfl_lab import initial_horizon as horizons, weekly_initial_remaining_v1 as old
from nfl_lab import weekly_initial_remaining_v2 as initial, weekly_generic_producer as generic
from nfl_lab import gha_private_checkpoint as checkpoint, hosted_initial_plan_builder_v1 as builder
from nfl_lab import private_draft_store as core, public_release_plan_v1 as public
from nfl_lab.state import canonical, digest, utc
from tools import genuine_hosted_fixed_build_v1 as build_cli, gha_private_checkpoint_v1 as checkpoint_cli
from tools import selected_private_snapshot_v1 as snapshot_cli, hosted_initial_plan_builder_v1 as builder_cli
from tools import hosted_public_release_plan_v1 as public_cli
from test_weekly_initial_remaining_v1 import registration as old_registration, schedule

NOW = utc("2026-10-24T21:30:00Z")
SOURCE = "c" * 40
CONFIG_SHA = "a" * 64
ROOT = Path(__file__).resolve().parents[1]


class Clock(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW


def registration():
    return dict(old_registration(), schema_version=initial.REGISTRATION, registration_id=initial.REGISTRATION_ID,
        slate_id=initial.REGISTRATION_ID, slate_kind="INITIAL_REMAINING_RECOVERY_ONE_TIME",
        registered_at_utc="2026-10-24T19:00:00Z", input_cutoff_utc=initial.CUTOFF,
        predecessor=dict(initial.PREDECESSOR), operational_stream="weekly-adaptive-release-v1", scientific_qualification=False)


def build_registration():
    r = registration()
    return dict(schema_version=initial.BUILD_REGISTRATION, registration_id=initial.BUILD_REGISTRATION_ID,
        approved=True, repository=core.REPO, source_sha=SOURCE, config_sha256=CONFIG_SHA,
        registered_at_utc="2026-10-24T19:05:00Z", input_cutoff_utc=initial.CUTOFF,
        training_cutoff_utc="2026-09-01T00:00:00Z", scope="SOURCE_AND_TRAIN_FIXED18_ONLY", maximum_new_fits=18,
        old_artifact_reproduction=False, scientific_qualification=False, initial_registration=r, initial_registration_sha256=digest(r))


def validate_build(r):
    return initial.validate_build_registration(r, source_sha=SOURCE, config_sha256=CONFIG_SHA,
        initial_sha256=digest(registration()), now=NOW)


def shift(value):
    if isinstance(value, dict):
        return {k:shift(v) for k,v in value.items()}
    if isinstance(value, list):
        return [shift(v) for v in value]
    if isinstance(value, str) and value.startswith("2026-10-24T"):
        return (utc(value)+timedelta(hours=9)).isoformat()
    return value


class RecoveryChecks(unittest.TestCase):
    def test_closed_horizon_identity_preserves_original_default(self):
        self.assertIs(horizons.resolve(), horizons.ORIGINAL)
        self.assertIs(horizons.resolve(True), horizons.RECOVERY)
        self.assertIs(horizons.resolve(True).adapter(), initial)
        for invalid in (1, "true", None, horizons.RECOVERY):
            with self.assertRaises(ValueError):
                horizons.resolve(invalid)
        self.assertEqual(old.CUTOFF, "2026-10-24T15:00:00Z")
        with self.assertRaises(ValueError):
            old.validate_registration(old_registration(), now=NOW)
        with self.assertRaises(ValueError):
            old.validate_registration(registration(), now=NOW)

    def test_actual_new_registration_cannot_reuse_backdate_or_qualify_predecessor(self):
        self.assertIs(initial.validate_registration(registration(), now=NOW).__class__, dict)
        for field,value in (("registered_at_utc", None), ("registered_at_utc", "2026-10-24T14:59:59Z"),
                ("registered_at_utc", "2026-10-24T22:00:00Z"), ("maximum_uses", True), ("maximum_uses", 2),
                ("scientific_qualification", True), ("input_cutoff_utc", old.CUTOFF), ("state", "PREPARED"),
                ("registration_id", old.REGISTRATION_ID), ("predecessor", {}), ("operational_stream", "scientifically-qualified")):
            r=registration();r[field]=value
            with self.subTest(field=field,value=value), self.assertRaises(ValueError):
                initial.validate_registration(r, now=NOW)
        for clock in (utc(initial.CUTOFF), utc(initial.REMAINING_FIRST)):
            with self.assertRaises(ValueError):
                initial.validate_registration(registration(), now=clock)
        r=registration();r["unknown_override"]=True
        with self.assertRaises(ValueError):
            initial.validate_registration(r, now=NOW)

    def test_full14_schedule_and13_future_games_use_exact_midnight_horizon(self):
        ref={"sha256":"f"*64}
        slate=initial.prepare_initial_slate(schedule(), registration(), ref, now=NOW)
        self.assertEqual((slate["scheduled_games"],slate["elapsed_games"]),(14,1))
        self.assertEqual(set(slate["game_cutoffs"].values()),{initial.CUTOFF})
        self.assertEqual(slate["slate_contract"]["predecessor"],initial.PREDECESSOR)
        self.assertEqual(slate["scheduled_first_kickoff_utc"],initial.REMAINING_FIRST)
        self.assertLess(utc(slate["slate_contract"]["full_week_deadline_utc"]),NOW)
        for rows in (schedule()[:-1], schedule()+[schedule()[0]], schedule()[1:]):
            with self.assertRaises(ValueError):
                initial.prepare_initial_slate(rows,registration(),ref,now=NOW)
        rows=schedule();rows[1]["kickoff_utc"]="2026-10-24T20:00:00Z"
        with self.assertRaises(ValueError):
            initial.prepare_initial_slate(rows,registration(),ref,now=NOW)

    def test_separately_registered_fixed18_budget_has_no_old_scope_or_extra_fit(self):
        validate_build(build_registration())
        for field,value in (("maximum_new_fits",19),("maximum_new_fits",True),("approved",False),
                ("schema_version","genuine-hosted-fixed-build-registration-v1"),("input_cutoff_utc",old.CUTOFF),
                ("registered_at_utc","2026-10-24T18:59:00Z"),("old_artifact_reproduction",True),
                ("scientific_qualification",True),("config_sha256","b"*64)):
            r=build_registration();r[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):
                validate_build(r)
        r=build_registration();r["initial_registration"]=old_registration()
        with self.assertRaises(ValueError):
            validate_build(r)

    def test_code_hashes_and_registration_change_selected_procedure(self):
        slate=initial.prepare_initial_slate(schedule(),registration(),{"sha256":"f"*64},now=NOW)
        selection=dict(members=[],decision=dict(slate_contract=slate["slate_contract"]))
        pins={p:"a"*64 for p in ("nfl_lab/weekly_generic_producer.py","nfl_lab/weekly_adaptive.py",
            "nfl_lab/weekly_initial_remaining_v1.py","nfl_lab/weekly_initial_remaining_v2.py","nfl_lab/initial_horizon.py")}
        expected=generic.selected_procedure(selection,pins)
        for name in ("nfl_lab/weekly_initial_remaining_v2.py","nfl_lab/weekly_initial_remaining_v1.py","nfl_lab/initial_horizon.py"):
            changed=dict(pins);changed[name]="b"*64
            self.assertNotEqual(expected,generic.selected_procedure(selection,changed))
        selection["decision"]["slate_contract"]["registration"]["sha256"]="e"*64
        self.assertNotEqual(expected,generic.selected_procedure(selection,pins))

    def test_recovery_backend_is_explicit_and_uses_shared_run(self):
        self.assertIs(initial.InitialRemainingBackend.run,generic.ProductionBackend.run)
        plan=dict(initial_adapter=dict(schema_version=initial.VERSION))
        backend=object.__new__(initial.InitialRemainingBackend);backend.plan=plan
        with patch.object(generic,"validate_plan"), patch.object(initial.InitialRemainingBackend,"run",return_value={"fictional_only":True}):
            self.assertEqual(generic.execute(plan,backend=backend),{"fictional_only":True})
            with self.assertRaises(ValueError):
                generic.execute(dict(plan),backend=backend)
            plan["initial_adapter"]["schema_version"]=old.VERSION
            with self.assertRaises(ValueError):
                generic.execute(plan,backend=backend)

    def test_distinct_consumption_journal_never_retries_under_new_output(self):
        class Store:
            @contextmanager
            def transaction(self):yield
            def register_root(self,path):Path(path).mkdir(parents=True,exist_ok=True)
            def atomic_json(self,path,value):
                with Path(path).open("x") as stream:json.dump(value,stream)
        with tempfile.TemporaryDirectory() as tmp:
            old_journal=Path(tmp)/old.VERSION/"registrations"/(old.REGISTRATION_ID+".json")
            old_journal.parent.mkdir(parents=True);old_journal.write_text("FICTIONAL OLD EVIDENCE")
            backend=object.__new__(initial.InitialRemainingBackend);backend.plan=dict(cache=tmp,output_root="/fictional/first")
            backend.clock=lambda:NOW;backend.store=Store();backend.consume_registration(registration(),{"sha256":"a"*64})
            backend.plan["output_root"]="/fictional/second"
            with self.assertRaisesRegex(ValueError,"already consumed"):
                backend.consume_registration(registration(),{"sha256":"b"*64})
            self.assertEqual(old_journal.read_text(),"FICTIONAL OLD EVIDENCE")

    def test_fresh_metadata_rejects_prior_claim_sources_and_fits(self):
        models=[dict(category=dict(target=t),method_id=m,artifact_created_at="2026-10-24T20:04:00Z",
            fit_receipt=dict(training_source_capture_completed_at="2026-10-24T20:01:00Z",
                training_started_at="2026-10-24T20:02:00Z",training_completed_at="2026-10-24T20:03:00Z")) for t,m in sorted(initial.EXPECTED)]
        receipts={name:dict(status="acquired",retrieved_utc="2026-10-24T20:00:00Z") for name in
            ("schedules.csv.receipt.json","roster_weekly_2026.parquet.receipt.json","stats_player_week_2026.parquet.receipt.json")}
        initial.validate_fresh_initial_metadata(registration(),models,receipts,now=NOW)
        models[0]["fit_receipt"]["training_source_capture_completed_at"]="2026-10-24T14:45:06Z"
        with self.assertRaises(ValueError):
            initial.validate_fresh_initial_metadata(registration(),models,receipts,now=NOW)

    def test_new_build_preflight_needs_explicit_recovery_and_exact_new_source_registration(self):
        r=build_registration();text=canonical(r).decode();config=dict(_recovery_config_sha256=CONFIG_SHA,
            initial_registration_canonical_sha256=digest(registration()),numerical_environment={},environment_versions={})
        with tempfile.TemporaryDirectory() as tmp:
            event=Path(tmp)/"event.json";event.write_bytes(canonical(dict(inputs=dict(mode=build_cli.MODE,
                build_registration_json=text,build_registration_sha256=digest(r)),repository=dict(full_name=core.REPO),ref="fictional")))
            env=dict(GITHUB_ACTIONS="true",CI="true",RUNNER_ENVIRONMENT="github-hosted",GITHUB_REPOSITORY=core.REPO,
                GITHUB_EVENT_NAME="workflow_dispatch",GITHUB_RUN_ATTEMPT="1",GITHUB_JOB=build_cli.MODE,BUILD_MODE=build_cli.MODE,
                STORE_PERMISSION="write",GITHUB_ACTOR="NickNicky19",GITHUB_ACTOR_ID="208912933",GITHUB_RUN_ID="40000000005",
                GITHUB_SHA=SOURCE,GITHUB_WORKFLOW_SHA=SOURCE,GITHUB_WORKSPACE=str(ROOT),GITHUB_REF="refs/heads/fictional",
                GITHUB_WORKFLOW_REF=core.REPO+"/.github/workflows/lab.yml@refs/heads/fictional",GITHUB_EVENT_PATH=str(event),
                BUILD_REGISTRATION_JSON=text,BUILD_REGISTRATION_SHA256=digest(r))
            original=build_cli.read
            def read(path,cap):
                if Path(path)==ROOT/".git/HEAD":return (SOURCE+"\n").encode()
                if Path(path)==ROOT/horizons.RECOVERY.registration_path:return canonical(registration())
                return original(path,cap)
            with patch.object(build_cli,"read",side_effect=read),patch.object(build_cli,"now",return_value=NOW):
                self.assertEqual(build_cli.preflight(env,config,recovery_v2=True),r)
                with self.assertRaises(build_cli.GuardStop):build_cli.preflight(env,config)

    def test_claim_accepts_only_explicit_new_registration_before_remote_write(self):
        calls=[];body=canonical(registration())
        client=SimpleNamespace(job=dict(execution_lane="github_actions",run_authenticated=True,job_id=build_cli.MODE,api_job_id=17),
            source_sha=SOURCE,run_id="40000000005",process="b"*64,binding={},upload=lambda name,data,**kw:(calls.append(kw) or {"id":41}),
            read_asset=lambda *args:body,draft=lambda:None)
        with patch.object(checkpoint,"datetime",Clock),patch.object(core,"check_proof"):
            with self.assertRaises(core.StoreError):checkpoint.claim_once(client,body,{},expected_sha256=digest(registration()),procedure_sha256="d"*64)
            self.assertEqual(calls,[])
            receipt=checkpoint.claim_once(client,body,{},expected_sha256=digest(registration()),procedure_sha256="d"*64,recovery_v2=True)
            self.assertEqual(receipt["registration_sha256"],digest(registration()))
            self.assertNotEqual(receipt["registration_sha256"],initial.PREDECESSOR["registration_sha256"])
            self.assertEqual(calls,[dict(reuse_completed=False)])

    def test_new_build_checkpoint_and_snapshot_configs_require_separate_opt_in(self):
        code=b"FICTIONAL CODE SOURCE";last=b"FICTIONAL LAST SOURCE PIN"
        config=dict(schema_version="genuine-hosted-fixed-build-plan-v2",mode=build_cli.MODE,maximum_new_fits=18,
            source_sha256={"nfl_lab/fictional_a.py":core.sha(code),"nfl_lab/fictional_last.py":core.sha(last)})
        body=canonical(config);sha=core.sha(body)
        bodies={horizons.RECOVERY.build_config_path:body,"nfl_lab/fictional_a.py":code,"nfl_lab/fictional_last.py":last}
        with patch.object(build_cli,"read",side_effect=lambda path,cap:bodies[Path(path).relative_to(ROOT).as_posix()]):
            result=build_cli.verify_sources(recovery_v2=True,config_sha256=sha)
            self.assertEqual(result["_recovery_config_sha256"],sha)
            self.assertNotEqual(result["_recovery_config_sha256"],core.sha(last))
            with self.assertRaises(build_cli.GuardStop):build_cli.verify_sources(recovery_v2=True)
        config=dict(schema_version="weekly-selected-private-snapshot-procedure-v2",state="ROOT_APPROVED_FOR_GENUINE_GHA",
            authority_kind="ROOT_APPROVED_PROCEDURE",input_cutoff_utc=initial.CUTOFF,source_sha256={})
        body=canonical(config);sha=core.sha(body)
        with patch.object(snapshot_cli,"read",return_value=body):
            self.assertEqual(snapshot_cli.verify_sources(sha,recovery_v2=True)["input_cutoff_utc"],initial.CUTOFF)
            with self.assertRaises(ValueError):snapshot_cli.verify_sources(sha)
        config=json.loads((ROOT/"config/gha-private-checkpoint-v1.json").read_text())
        config.update(schema_version="weekly-gha-private-checkpoint-procedure-v2",initial_registration_path=initial.REGISTRATION_PATH,
            initial_registration_canonical_sha256=digest(registration()))
        bodies={name:b"FICTIONAL PINNED CODE" for name in ("nfl_lab/hosted_fixed_build_v1.py","tools/genuine_hosted_fixed_build_v1.py",
            horizons.RECOVERY.build_config_path)}
        bodies[initial.REGISTRATION_PATH]=canonical(registration())
        config["source_sha256"]={name:core.sha(body) for name,body in bodies.items()}
        bodies[horizons.RECOVERY.checkpoint_config_path]=canonical(config)
        with patch.object(checkpoint_cli,"read",side_effect=lambda path,cap:bodies[Path(path).relative_to(ROOT).as_posix()]),patch('datetime.datetime',Clock):
            result=checkpoint_cli.verified(core.sha(bodies[horizons.RECOVERY.checkpoint_config_path]),recovery_v2=True)
            self.assertEqual(result["initial_registration_canonical_sha256"],digest(registration()))

    def test_actual_build_preflight_failure_stops_claim_before_API_or_POST(self):
        r=build_registration();env=dict(BUILD_REGISTRATION_JSON=canonical(r).decode(),GITHUB_ACTIONS="true",
            GITHUB_REPOSITORY=core.REPO,GITHUB_EVENT_NAME="workflow_dispatch",GITHUB_RUN_ATTEMPT="1",STORE_PERMISSION="write",
            CHECKPOINT_MODE=build_cli.MODE,GITHUB_JOB=build_cli.MODE)
        config=dict(build_mode=build_cli.MODE,claim_job=build_cli.MODE)
        with patch.object(checkpoint_cli,"verified",return_value=config),patch.object(checkpoint_cli.resource,"setrlimit"),\
                patch.object(checkpoint_cli.signal,"alarm"),patch.object(build_cli,"verify_sources",return_value={}) as sources,\
                patch.object(build_cli,"preflight",side_effect=ValueError("FICTIONAL_BUILD_PREFLIGHT_STOP")) as preflight,\
                patch.object(core.Client,"authenticate_actions_job",side_effect=AssertionError("remote authentication before preflight")) as auth,\
                patch.object(checkpoint,"claim_once",side_effect=AssertionError("claim before preflight")) as claim,redirect_stdout(io.StringIO()):
            self.assertEqual(checkpoint_cli.main(["claim","--execute","--recovery-v2"],environ=env),1)
        sources.assert_called_once_with(recovery_v2=True,config_sha256=CONFIG_SHA)
        preflight.assert_called_once_with(env,{},recovery_v2=True)
        auth.assert_not_called();claim.assert_not_called()

    def test_metadata_builder_GO_requires_new_schema_digest_and_scope(self):
        from test_hosted_initial_plan_builder_v1 import go
        approval=go();approval.update(schema_version=horizons.RECOVERY.builder_version+"-GO",scope=horizons.RECOVERY.builder_scope,
            initial_registration_sha256=digest(registration()),approved_at_utc="2026-10-24T19:00:00Z")
        builder.verify_go(approval,procedure_sha256="1"*64,source_sha=SOURCE,now=NOW,recovery_v2=True,registration_sha256=digest(registration()))
        with self.assertRaises(ValueError):builder.verify_go(approval,procedure_sha256="1"*64,source_sha=SOURCE,now=NOW)
        with self.assertRaises(ValueError):builder.verify_go(approval,procedure_sha256="1"*64,source_sha=SOURCE,now=NOW,
            recovery_v2=True,registration_sha256=builder.REGISTRATION_SHA)

    def test_restored_strict18_chain_reuses_shared_metadata_validator(self):
        from test_hosted_initial_plan_builder_v1 import fixture
        restored,kwargs,docs=fixture();restored=shift(restored);docs=shift(docs)
        kwargs.update(registration=registration(),now=NOW,recovery_v2=True,read=lambda ref:deepcopy(docs[ref["path"]]))
        kwargs["config"]["_build_config_sha256"]=CONFIG_SHA
        build_path=str(kwargs["root"] / "private-checkpoint-restore/files/control/BUILD_REGISTRATION.json")
        docs[build_path]=build_registration()
        with patch.object(core,"datetime",Clock):
            result=builder.validate_restore(restored,**kwargs)
        self.assertEqual((len(result["artifacts"]),len(result["source_bindings"])),(18,38))
        docs[build_path]["initial_registration"]=old_registration()
        with patch.object(core,"datetime",Clock),self.assertRaises(ValueError):builder.validate_restore(restored,**kwargs)

    def test_public_GO_has_recovery_cutoff_and_new_build_authority(self):
        import test_public_release_plan_v1 as fixtures
        fixture=fixtures.ReleasePlanChecks()
        with patch.object(fixtures,"datetime",Clock):fixture.setUp()
        try:
            go=fixture.go;go.update(schema_version=horizons.RECOVERY.public_version+"-GO",input_cutoff_utc=initial.CUTOFF,source_sha=SOURCE,
                registered_at_utc="2026-10-24T19:00:00Z")
            go["policy"]["publication_authority"]["source_sha"]=SOURCE
            # The archived board and R0 freeze precede this fictional GO.
            go["board"]["captured_at"]="2026-10-24T18:00:00Z";go["r0"]["frozen_at"]="2026-10-24T18:00:00Z"
            go["policy"]["r0_identities"]=[public.a.digest(go["r0"])]
            text=core.canonical(go).decode();sha=core.sha(text.encode());event=deepcopy(fixture.event)
            event["inputs"].update(public_release_go_json=text,public_release_go_sha256=sha,
                build_registration_json=canonical(build_registration()).decode(),build_registration_sha256=digest(build_registration()))
            result=public.validate_go(go,procedure_sha256="d"*64,source_sha=SOURCE,event=event,go_text=text,go_sha=sha,
                at=NOW.isoformat(),recovery_v2=True,build_config_sha256=CONFIG_SHA)
            self.assertEqual(result["schema_version"],initial.BUILD_REGISTRATION)
            with self.assertRaises(core.StoreError):public.validate_go(go,procedure_sha256="d"*64,source_sha=SOURCE,event=event,
                go_text=text,go_sha=sha,at=NOW.isoformat())
        finally:fixture.tearDown()

    def test_new_CLI_preparation_never_reads_registration_or_credentials(self):
        class NoEnvironment:
            def get(self,*args):raise AssertionError("environment read")
        for cli,args,kwargs in ((build_cli,["--recovery-v2"],{}),(checkpoint_cli,["claim","--recovery-v2"],dict(environ=NoEnvironment())),
                (builder_cli,["--recovery-v2"],{}),(snapshot_cli,["produce","--recovery-v2"],dict(environ=NoEnvironment())),
                (public_cli,["--recovery-v2"],dict(environ=NoEnvironment()))):
            with self.subTest(cli=cli.__name__),patch.object(cli,"read",side_effect=AssertionError("file read"),create=True),redirect_stdout(io.StringIO()):
                self.assertEqual(cli.main(args,**kwargs),2)


if __name__ == "__main__":
    unittest.main()
