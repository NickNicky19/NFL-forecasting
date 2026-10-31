"""Synthetic failure protocol records and explicit transports/mocks only.

No test claims a real hosted identity, executes the deployed workflow, reads a
private remote asset, or falls back to network. All temporary writes are below
this draft. Run with python -B test_failed_admission_reader.py -v.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import base64
import gzip
import importlib.util
import json
import resource
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

sys.dont_write_bytecode = True
DRAFT = Path(__file__).resolve().parent
SOURCE = DRAFT.parent if DRAFT.name == "tests" else DRAFT.parents[1]/"producer-source"
sys.path[:0] = [str(SOURCE),str(SOURCE/"tests")]
HELPER = SOURCE/"tools/audit_weekly_failed_admission_read_v1.py" if DRAFT.name == "tests" else DRAFT/"audit_weekly_failed_admission_read_v1.py"
spec = importlib.util.spec_from_file_location("draft_reader",HELPER)
d = importlib.util.module_from_spec(spec); spec.loader.exec_module(d)
from nfl_lab import private_draft_store as s, gha_private_checkpoint as cp
from nfl_lab import audit_weekly_hosted_v1 as hosted, audit_private_rotation_v1 as rotation
from nfl_lab import operational_failure_v1 as failure, audit_weekly_template_v1 as template
from test_owner_private_bootstrap import qualification


class Response:
    def __init__(self, value, status=200):
        self.body = value if type(value) is bytes else s.canonical(value)
        self.status = status; self.headers = {"X-RateLimit-Remaining":"999","Content-Length":str(len(self.body))}
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def read(self,n): return self.body[:n]


class SyntheticFailure:
    """Construct real closed failure/envelope/manifest schemas with invented bytes."""
    def __init__(self, root):
        self.root=root; self.calls=[]; self.bad_digest=False; self.draft=True; self.bad_failed_source=False
        self.bad_qualification_source=False; self.current_owner="NickNicky19"; self.corrupt_payload=False
        self.current_run="40088888888"; self.current_source="b"*40
        self.current_started=datetime.now(timezone.utc)-timedelta(seconds=1)
        self.cut=(datetime.now(timezone.utc)-timedelta(minutes=10)).replace(microsecond=0)
        self.before=(datetime.now(timezone.utc)-timedelta(minutes=2)).isoformat()
        canary=s.probe.fixture("40000000001"); digest=s.sha(canary)
        self.binding=dict(schema_version="weekly-private-draft-binding-v2",repository=s.REPO,runtime_id="d"*32,
            origin_run_id="40000000001",release_id=91,tag_name="weekly-private-runtime-v2-"+"d"*32,
            canary_asset_id=80,canary_name="canary-"+digest+".txt",canary_sha256=digest,canary_bytes=117,
            browser_tag="untagged-"+"c"*20,config_sha256=s.config_sha())
        q=qualification(self.binding)
        for proof,phase in zip((q["before_proof"],q["read_proof"],q),("write","read","qualify")):
            proof["job"]["job_id"]=rotation.JOBS[phase]
        q["read_proof"]["before_sha256"]=s.sha(s.canonical(q["before_proof"]))
        q["before_sha256"]=q["read_proof"]["before_sha256"]
        q["read_sha256"]=s.sha(s.canonical(q["read_proof"]))
        census=dict(schema_version=rotation.VERSION+"-pending-census",complete=True,
            as_of_utc=(s.utc(q["before_proof"]["started_at_utc"])-timedelta(seconds=1)).isoformat(),
            owner_evidence_sha256="1"*64,reservations=[dict(reservation_sha256="2"*64,
                runtime_id="e"*32,release_id=90,pending_bytes=3,pending_assets=1)])
        quota=dict(schema_version=rotation.VERSION+"-quota-reservation",global_cap_bytes=512 << 20,
            reserved_before_bytes=32 << 20,new_runtime_reserved_bytes=32 << 20,reserved_after_bytes=64 << 20,
            existing_draft_runtimes=1,pending_unlocated_runtimes=0,pending_records=1,charged_existing_bytes=120,
            charged_existing_assets=2,inventory_sha256="3"*64,pending_census_sha256=s.sha(s.canonical(census)),
            new_runtime_id=self.binding["runtime_id"],old_assets_deleted=0,metadata_only=True)
        self.package=dict(schema_version=rotation.VERSION+"-qualified-runtime",root_go_sha256="4"*64,
            run_id=q["run_id"],source_sha=q["source_sha"],runtime_id=self.binding["runtime_id"],binding=self.binding,
            qualification=q,quota_reservation=quota,runtime_reserved_bytes=s.TOTAL_CAP,private_payload_bytes=0,
            private_durability_qualified=False,strict_v1_unchanged="INCONCLUSIVE")
        self.pending=cp.reservation_metadata("asset:blob-"+s.sha(b"missing")+".bin",b"missing",name="blob-"+s.sha(b"missing")+".bin")
        claim=b"synthetic claim"
        self.claim_record=cp.reservation_metadata("asset:blob-"+s.sha(claim)+".bin",claim,name="blob-"+s.sha(claim)+".bin")
        old_entry=dict(schema_version="weekly-private-restore-manifest-v2",payload=cp.payload(b"synthetic prior"),
            payload_asset_id=71,payload_name="blob-"+s.sha(b"synthetic prior")+".bin",producer_process="7"*64,
            binding_sha256=s.sha(s.canonical(self.binding)),writer_run_id="40000000011")
        old_desc=dict(entry=old_entry,manifest_asset_id=72,manifest_sha256=s.sha(s.canonical(old_entry)),manifest_bytes=len(s.canonical(old_entry)))
        old_handoff=dict(schema_version=hosted.VERSION+"-failure-handoff",root_go_sha256="8"*64,binding=self.binding,descriptor=old_desc)
        self.old=dict(schema_version=template.ROOT_V3,approved=True,repository=s.REPO,mode=hosted.MODE,
            owner_authorization="OWNER_NFL_AUDIT_CONTINUATION_20261025",jobs=hosted.JOBS,source_sha="a"*40,
            workflow_ref=d.ORIGINAL_WORKFLOW,issued_at_utc=(self.cut-timedelta(minutes=3)).isoformat(),qualified_runtime=self.package,
            pending_census=census,effective_epoch=dict(schema_version=template.RECURRING_V5,
                pending_post_recovery=dict(schema_version=template.PENDING_RECOVERY,handoffs=[old_handoff],pending_reservations=[self.pending])))
        self.original_records=[self.pending,self.claim_record];self.phase_shape="actual_both";self.child_offset=.4;self.parent_offset=.5
        self.graph=dict(schema_version=hosted.VERSION+"-failed-file-graph",files=[dict(relative_path="runtime/FINISHED.json",
            reference=dict(path="/synthetic/PRIVATE_ROOT/runtime/FINISHED.json",bytes=999,sha256="9"*64))],
            raw_HTTP_corpus_archived=False,successful_forecast=False,public_release=False)
        self.historical=[self.asset(80,self.binding["canary_name"],canary,self.cut-timedelta(minutes=15)),
            self.asset(81,self.claim_record["name"],claim,self.cut-timedelta(seconds=60))]
        self.rebuild()

    def asset(self, aid, name, body, at):
        return dict(id=aid,name=name,body=body,size=len(body),state="uploaded",digest="sha256:"+s.sha(body),
            url=s.API+"/releases/assets/"+str(aid),created_at=at.isoformat())

    def rebuild(self, *, bad_request_source=False):
        wrappers=[]
        for record in self.original_records:
            raw=s.canonical(record); name="journal/"+s.sha(record["key"].encode())+".reservation.json"
            wrappers.append(dict(relative_path=name,bytes=len(raw),sha256=s.sha(raw),body_base64=base64.b64encode(raw).decode()))
        docs={"owner-root":self.old,"original-post-reservations":dict(schema_version=hosted.VERSION+"-original-post-journals",records=wrappers),
            "file-graph":self.graph,"complete-auxiliary-controls":dict(schema_version=hosted.VERSION+"-complete-auxiliary-controls",files=[])}
        docs["phase-99"]=dict(exit_code=0,status=dict(state="FICTIONAL_PRIOR_PHASE_COMPLETE"),
            actual_completed_at=(self.cut-timedelta(seconds=2)).isoformat())
        if self.phase_shape in {"actual_both","nested_only"}:
            docs["phase-00"]=dict(exit_code=1,status=dict(state="FAILED_RETAINED",reason=d.QUOTA_REASON,fits=0,public_release=False),
                actual_completed_at=(self.cut+timedelta(seconds=self.child_offset)).isoformat())
        if self.phase_shape in {"actual_both","parent_only"}:
            docs["phase-01"]=dict(reason=d.QUOTA_REASON,state="FAILED_RETAINED",phase="produce",
                actual_observed_at=(self.cut+timedelta(seconds=self.parent_offset)).isoformat(),public_release=False,successful_forecast=False)
        root_sha=s.sha(s.canonical(self.old)); attachments=[]; values=[]
        for label,value in docs.items():
            raw=s.canonical(value)
            attachments.append(dict(label=label,kind="post_reservation" if label=="original-post-reservations" else "control",
                reference=dict(path="/synthetic/PRIVATE_ROOT/"+label+".json",bytes=len(raw),sha256=s.sha(raw))))
            values.append(dict(label=label,base64=base64.b64encode(raw).decode()))
        request=dict(schema_version=failure.VERSION+"-request",attempt=dict(repository=s.REPO,run_id=d.TARGET["run_id"],run_attempt=1,
            source_sha="f"*40 if bad_request_source else self.old["source_sha"],job_id=hosted.JOBS["produce"],workflow_ref=d.ORIGINAL_WORKFLOW),
            operation="producer",state="FAILED",failure=dict(kind="EXCEPTION",code="WEEKLY_PHASE_FAILED_RETAINED",exit_code=1),
            clocks=dict(started_at_utc=(self.cut-timedelta(seconds=110)).isoformat(),observed_at_utc=(self.cut+timedelta(seconds=5)).isoformat(),original={}),
            input_contract_sha256=root_sha,attachments=attachments)
        body=gzip.compress(s.canonical(dict(schema_version=failure.VERSION+"-envelope",classification="FAILURE_EVIDENCE_ONLY",
            request=request,attachments=values,gates=failure.NEGATIVE_GATES)),mtime=0)
        failure.unpack(body)  # Actual closed parser, not a fabricated PASS flag.
        entry=dict(schema_version="weekly-private-restore-manifest-v2",payload=failure.payload_manifest(body),
            payload_asset_id=d.TARGET["payload_id"],payload_name="blob-"+s.sha(body)+".bin",producer_process="6"*64,
            binding_sha256=s.sha(s.canonical(self.binding)),writer_run_id=d.TARGET["run_id"])
        manifest=s.canonical(entry)
        self.assets=self.historical+[
            self.asset(d.TARGET["payload_id"],entry["payload_name"],body,self.cut+timedelta(seconds=6)),
            self.asset(d.TARGET["manifest_id"],"manifest-"+s.sha(manifest)+".json",manifest,self.cut+timedelta(seconds=7))]
        self.target=dict(d.TARGET,source_sha=self.old["source_sha"],root_go_sha256=root_sha,release_id=91,runtime_id=self.binding["runtime_id"],
            package_sha256=s.sha(s.canonical(self.package)),binding_sha256=s.sha(s.canonical(self.binding)),manifest_bytes=len(manifest),
            manifest_sha256=s.sha(manifest),payload_bytes=len(body),payload_sha256=s.sha(body),admission_second=self.cut.isoformat(),
            historical_assets=len(self.historical),historical_bytes=sum(a["size"] for a in self.historical),
            historical_inventory_sha256=s.sha(s.canonical(d.projection(self.historical))))

    def transport(self, request, timeout):
        self.calls.append(request)
        assert request.method == "GET", "synthetic transport rejects any mutation"
        url=request.full_url; path=urlsplit(url).path
        if "/actions/runs/" in path:
            run=path.split("/runs/")[1].split("/")[0]; jobs=path.endswith("/jobs")
            if run==self.target["run_id"]:
                source="0"*40 if self.bad_failed_source else self.old["source_sha"]
                value=dict(id=311,name=hosted.JOBS["produce"],run_id=int(run),head_sha=source,status="completed",conclusion="failure",
                    started_at=(self.cut-timedelta(seconds=120)).isoformat(),completed_at=(self.cut+timedelta(seconds=10)).isoformat())
                values=[value]; branch=d.ORIGINAL_BRANCH; status="completed"; conclusion="failure"
            elif run==self.package["run_id"]:
                source="0"*40 if self.bad_qualification_source else self.package["source_sha"]
                q=self.package["qualification"]
                values=[dict(id=p["job"]["api_job_id"],name=p["job"]["job_id"],head_sha=source,run_id=int(run),status="completed",conclusion="success",
                    started_at=p["started_at_utc"],completed_at=p["created_at_utc"]) for p in (q["before_proof"],q["read_proof"],q)]
                branch="fictional"; status="completed"; conclusion="success"
            elif run==self.current_run:
                source=self.current_source; branch=d.BRANCH; status="in_progress"; conclusion=None
                values=[dict(id=999,name=d.JOB,run_id=int(run),head_sha=source,status="in_progress",started_at=self.current_started.isoformat())]
            else: raise AssertionError("unexpected synthetic Actions route")
            if jobs:return Response(dict(total_count=len(values),jobs=values))
            return Response(dict(id=int(run),head_sha=source,head_branch=branch,status=status,conclusion=conclusion,event="workflow_dispatch",
                run_attempt=1,path=".github/workflows/lab.yml",repository=dict(full_name=s.REPO),head_repository=dict(full_name=s.REPO),
                actor=dict(login=self.current_owner,id=208912933),triggering_actor=dict(login=self.current_owner,id=208912933)))
        if path.endswith("/releases/91"):
            return Response(dict(id=91,draft=self.draft,published_at=None if self.draft else self.cut.isoformat(),
                tag_name=self.binding["tag_name"],url=s.API+"/releases/91"))
        if path.endswith("/releases/91/assets"):
            rows=[{k:v for k,v in a.items() if k!="body"} for a in self.assets]
            if self.bad_digest:rows[-1]["digest"]="sha256:"+"0"*64
            return Response(rows)
        if "/releases/assets/" in path:
            aid=int(path.rsplit("/",1)[1]); a=next(a for a in self.assets if a["id"]==aid)
            if request.get_header("Accept")=="application/octet-stream":
                if self.corrupt_payload and aid==self.target["payload_id"]:return Response(b"synthetic corrupt")
                return Response(a["body"])
            return Response({k:v for k,v in a.items() if k!="body"})
        raise AssertionError("No real network fallback: unexpected synthetic route")

    def client(self):
        journal=self.root/"journal"; journal.mkdir(mode=0o700)
        job=dict(execution_lane="github_actions",workflow_ref=d.WORKFLOW,workflow_sha=self.current_source,job_id=d.JOB,
            permission="write",event_name="workflow_dispatch",api_job_id=0,run_authenticated=False)
        return d.client_type()("ghs_SYNTHETIC_TEST_ONLY",self.current_run,journal=journal,source_sha=self.current_source,
            job=job,operation="metadata",target=self.target,package=self.package,transport=self.transport,process="5"*64)

    def read(self):
        return d.read_diagnostic(self.client(),self.package,before=self.before,target=self.target)


class ReaderTests(unittest.TestCase):
    def setUp(self):
        (DRAFT/"test-tmp").mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=DRAFT/"test-tmp");self.addCleanup(self.temp.cleanup)
        self.f=SyntheticFailure(Path(self.temp.name))

    def test_actual_closed_failure_parser_pending_authenticator_and_native_proofs(self):
        value=self.f.read(); raw=d.safe_summary(value)
        self.assertEqual(value["pending"]["unmatched_at_admission_records"],1)
        self.assertEqual(value["pending"]["unmatched_at_admission_bytes"],len(b"missing"))
        self.assertEqual(value["pending"]["existing_admission_slots"],3)
        self.assertIsNone(value["archive"]["encoded_group_bytes"])
        self.assertIsNone(value["archive"]["exact_requested_bytes"])
        self.assertIn(b"UNKNOWN_PREENCODED_AND_ADMISSION_NOT_RETAINED",raw)
        self.assertNotIn(b"PRIVATE_ROOT",raw)
        self.assertTrue(all(c.method=="GET" for c in self.f.calls))
        octets=[c.full_url for c in self.f.calls if c.get_header("Accept")=="application/octet-stream"]
        self.assertEqual(len(octets),4)  # Actual helper authenticates both already pinned bodies again.
        self.assertEqual(set(octets),{s.API+"/releases/assets/"+str(self.f.target[k]) for k in ("manifest_id","payload_id")})
        self.assertEqual(value["original_census"]["reservations"],self.f.old["pending_census"]["reservations"])
        self.assertEqual(set(value["original_census"]["reservations"][0]),
            {"reservation_sha256","runtime_id","release_id","pending_bytes","pending_assets"})

    def test_current_unknown_pending_still_charges_its_bytes_and_slot(self):
        value=self.f.read();pending=value["pending"]
        self.assertEqual(pending["current_unmatched_records"],1)
        self.assertEqual(pending["current_unmatched_slots"],1)
        self.assertEqual(pending["current_unmatched_bytes"],len(b"missing"))
        self.assertEqual(value["HTTP_calls"],22)  # Existing read path, no new HTTP.

    def test_after_cutoff_upload_is_historically_pending_but_currently_matched(self):
        late=self.f.asset(82,self.f.pending["name"],b"missing",self.f.cut+timedelta(seconds=8))
        self.f.assets.append(late)
        value=self.f.read();pending=value["pending"]
        self.assertEqual(pending["unmatched_at_admission_records"],1)
        self.assertEqual(pending["unmatched_at_admission_bytes"],len(b"missing"))
        self.assertEqual(pending["current_unmatched_records"],0)
        self.assertEqual(pending["current_unmatched_slots"],0)
        self.assertEqual(pending["current_unmatched_bytes"],0)
        rows=[]
        for record in sorted(self.f.original_records,key=lambda r:r["key"]):
            match=next(a for a in self.f.assets if a["name"]==record["name"] and a["size"]==record["bytes"]
                and a.get("digest")=="sha256:"+record["sha256"])
            rows.append(dict(record_sha256=s.sha(s.canonical(record)),matched_asset_id=match["id"]))
        expected=s.sha(s.canonical(dict(schema_version=d.VERSION+"-authenticated-current-reservation-matches",records=rows)))
        self.assertEqual(pending["current_record_matches_sha256"],expected)
        self.assertEqual(value["HTTP_calls"],22)

    def test_qualification_runs_only_after_authenticated_original_root_and_records(self):
        events=[]; auth=hosted.authenticated_pending_records; verify=d.verify_qualification
        def records(*args,**kwargs):
            result=auth(*args,**kwargs); self.assertIn("root",kwargs["_evidence"]); events.append("original-authenticated"); return result
        def qualify(*args,**kwargs):
            self.assertEqual(events,["original-authenticated"]);events.append("qualification");return verify(*args,**kwargs)
        with patch.object(hosted,"authenticated_pending_records",side_effect=records),patch.object(d,"verify_qualification",side_effect=qualify):
            self.f.read()
        self.assertEqual(events,["original-authenticated","qualification"])

    def test_changed_server_digest_stops_before_body_read(self):
        self.f.bad_digest=True
        with self.assertRaisesRegex(s.StoreError,"ASSET_IDENTITY"):self.f.read()
        self.assertFalse(any(c.get_header("Accept")=="application/octet-stream" for c in self.f.calls))

    def test_changed_original_job_source_stops_before_qualification(self):
        self.f.bad_failed_source=True
        with self.assertRaises(Exception):self.f.read()
        self.assertFalse(any("/runs/"+self.f.package["run_id"] in c.full_url for c in self.f.calls))

    def test_census_commitment_is_not_replaced_by_caller_numbers(self):
        self.f.old["pending_census"]["reservations"][0]["pending_bytes"]+=1;self.f.rebuild()
        with self.assertRaises(Exception):self.f.read()
        self.assertFalse(any("/runs/"+self.f.package["run_id"] in c.full_url for c in self.f.calls))

    def test_missing_original_seed_record_stops_before_qualification(self):
        self.f.original_records=[self.f.claim_record];self.f.rebuild()
        with self.assertRaisesRegex(d.DiagnosticError,"COMPLETE_ORIGINAL_ARCHIVE_SEEDED_PENDING"):self.f.read()
        self.assertFalse(any("/runs/"+self.f.package["run_id"] in c.full_url for c in self.f.calls))

    def test_unmatched_nonseeded_intent_cannot_gain_an_invented_issue_clock(self):
        body=b"synthetic unclocked intent"; name="blob-"+s.sha(body)+".bin"
        self.f.original_records.append(cp.reservation_metadata("asset:"+name,body,name));self.f.rebuild()
        with self.assertRaisesRegex(d.DiagnosticError,"UNMATCHED_NONSEEDED_PRE_ADMISSION_ELIGIBILITY_REQUIRED"):self.f.read()

    def test_corrupt_failure_body_is_not_decoded(self):
        self.f.corrupt_payload=True
        with self.assertRaisesRegex(s.StoreError,"READBACK_MISMATCH"):self.f.read()

    def test_changed_original_request_source_is_rejected(self):
        self.f.rebuild(bad_request_source=True)
        with self.assertRaisesRegex(d.DiagnosticError,"EXACT_ORIGINAL_FAILURE_REQUEST"):self.f.read()

    def test_changed_qualification_job_source_is_rejected(self):
        self.f.bad_qualification_source=True
        with self.assertRaises(Exception):self.f.read()

    def test_published_release_stops_before_private_body(self):
        self.f.draft=False
        with self.assertRaisesRegex(s.StoreError,"DRAFT_CHANGED_STOP"):self.f.read()
        self.assertFalse(any(c.get_header("Accept")=="application/octet-stream" for c in self.f.calls))

    def test_no_caller_handoff_or_pass_parameter(self):
        with self.assertRaises(TypeError):d.read_diagnostic(None,self.f.package,before=self.f.before,handoff={"PASS":True})

    def test_wrong_registered_package_rejected_before_any_request(self):
        package=deepcopy(self.f.package);package["private_payload_bytes"]=999
        with self.assertRaisesRegex(d.DiagnosticError,"EXACT_REGISTERED_QUALIFIED_PACKAGE"):
            d.read_diagnostic(self.f.client(),package,before=self.f.before,target=self.f.target)
        self.assertFalse(self.f.calls)

    def test_all_mutation_and_extra_body_routes_rejected_without_transport(self):
        client=self.f.client();client.bind(self.f.binding);before=len(self.f.calls)
        attempts=[lambda:client.reserve("x",b"x"),lambda:client.reserve_post("x","x",b"x"),lambda:client.upload("x",b"x"),
            lambda:client.request(s.API+"/releases/91",method="POST",data=b"x"),
            lambda:client.request(s.API+"/releases/91",method="DELETE"),
            lambda:client.request("https://provider.invalid/feed"),
            lambda:client.read_asset(80,self.f.binding["canary_name"],117,self.f.binding["canary_sha256"]),
            lambda:client.request(s.API+"/releases/assets/80",octet=True,download=True),
            lambda:client.request(client.browser())]
        for action in attempts:
            with self.subTest(action=action),self.assertRaises(d.DiagnosticError):action()
        self.assertEqual(len(self.f.calls),before)

    def test_current_actor_checked_by_actual_authenticator_with_explicit_synthetic_transport(self):
        client=self.f.client();self.f.current_owner="somebody-else"
        go=dict(issued_at_utc=self.f.before,expires_at_utc=(datetime.now(timezone.utc)+timedelta(minutes=10)).isoformat())
        with self.assertRaisesRegex(d.DiagnosticError,"ACTUAL_DIAGNOSTIC_RUN_OWNER_AND_BRANCH"):
            d.verify_current(client,go,d.modules())
        self.assertTrue(all("/actions/runs/" in c.full_url for c in self.f.calls))

    def test_output_rejects_raw_attachments_and_private_paths(self):
        for value in [dict(attachments=[]),dict(x="/synthetic/PRIVATE_ROOT",qualified_runtime={}),dict(x="https://provider.invalid")]:
            with self.subTest(value=value),self.assertRaises(d.DiagnosticError):d.safe_summary(value)

    def test_unexpected_encoded_evidence_does_not_turn_into_a_claimed_exact_total(self):
        self.f.graph["files"].append(dict(relative_path="archive-produce/transport/preencoded/0.gz",
            reference=dict(path="/synthetic/PRIVATE_ROOT/archive/0.gz",bytes=111,sha256="a"*64)))
        self.f.rebuild()
        with self.assertRaisesRegex(d.DiagnosticError,"UNEXPECTED_ENCODED_ADMISSION_EVIDENCE_REQUIRES_REVIEW"):self.f.read()

    def test_permission_reason_is_supported_by_archived_denials(self):
        value=self.f.read();contract=value["permission_contract"]
        self.assertEqual(contract["contents"],"write");self.assertTrue(contract["GET_only"])
        self.assertGreater(contract["archived_contents_read_denied_routes"],0)
        self.assertEqual(contract["POSTs"],0)

    def test_inherited_pending_does_not_gain_a_false_new_issuer(self):
        value=self.f.read()
        inherited=next(x for x in value["pending"]["owner_purpose"] if x["origin"]=="INHERITED_SEEDED_RESERVATION")
        issued=next(x for x in value["pending"]["owner_purpose"] if x["origin"]=="ORIGINAL_ATTEMPT_INTENT")
        self.assertIsNone(inherited["original_issuer_run_id"])
        self.assertEqual(issued["original_issuer_run_id"],self.f.target["run_id"])

    def test_production_target_is_literal_and_not_fixture_values(self):
        self.assertEqual(d.TARGET["run_id"],"41231404531")
        self.assertEqual(d.TARGET["source_sha"],"0409a253d6a365c31a2d421941b8ee5f40d6fd02")
        self.assertEqual((d.TARGET["manifest_id"],d.TARGET["manifest_bytes"]),(696245074,662))
        self.assertEqual((d.TARGET["payload_id"],d.TARGET["payload_bytes"]),(696245027,91261))

    def test_current_branch_is_separate_from_original_failed_workflow(self):
        self.assertEqual(d.BRANCH,"production/archive-admission-read-20261031")
        self.assertEqual(d.ORIGINAL_WORKFLOW,s.REPO+"/.github/workflows/lab.yml@refs/heads/research/weekly-storage-probe-v1")
        self.assertNotEqual(d.WORKFLOW,d.ORIGINAL_WORKFLOW)

    def test_real_source_child_status_and_parent_failure_shapes_are_both_supported(self):
        value=self.f.read()
        self.assertEqual(value["archive"]["status_reason_match_count"],2)
        self.assertEqual(value["archive"]["status_reason_shapes"],["CHILD_STATUS_REASON","PARENT_REASON"])

    def test_child_rejection_can_precede_the_next_second_parent_disclosure(self):
        self.f.child_offset=-.466863;self.f.parent_offset=.011367;self.f.rebuild()
        value=self.f.read();window=value["archive"]["admission_window"]
        self.assertEqual(window["child_rejection_completed_at"],[(self.f.cut+timedelta(seconds=self.f.child_offset)).isoformat()])
        self.assertFalse(window["exact_guard_time_available"])
        self.assertEqual(value["pending"]["existing_admission_bytes"],sum(a["size"] for a in self.f.historical)+len(b"missing"))

    def test_reversed_parent_or_prior_success_clocks_fail(self):
        for child,parent in [(.6,.5),(-3,.5)]:
            with self.subTest(child=child,parent=parent), tempfile.TemporaryDirectory(dir=self.f.root) as temporary:
                case=SyntheticFailure(Path(temporary))
                case.child_offset=child;case.parent_offset=parent;case.rebuild()
                with self.assertRaises(d.DiagnosticError):case.read()

    def test_asset_in_uncertain_admission_window_is_not_silently_assigned(self):
        item=self.f.asset(83,"fictional-racing-asset",b"x",self.f.cut-timedelta(seconds=1))
        self.f.assets.append(item)
        with self.assertRaisesRegex(d.DiagnosticError,"ADMISSION_INVENTORY_CHANGED"):
            self.f.read()

    def test_nested_only_status_has_no_assumed_parent_shape(self):
        self.f.phase_shape="nested_only";self.f.rebuild()
        self.assertEqual(self.f.read()["archive"]["status_reason_shapes"],["CHILD_STATUS_REASON"])

    def test_missing_phase_shape_keeps_verified_request_and_unknown_reason(self):
        self.f.phase_shape="none";self.f.rebuild()
        value=self.f.read()
        self.assertIsNone(value["archive"]["original_reason"])
        self.assertEqual(value["archive"]["original_reason_state"],"CORE_REASON_UNKNOWN")

    def test_pin_inventory_is_complete_hosted_closure_plus_reader_and_installed_test(self):
        self.assertEqual(set(d.dependency_paths()),set(hosted.PINS)|{d.TOOL,"tests/test_failed_admission_reader.py","nfl_lab/__init__.py"})

    def test_metadata_imports_do_not_load_numerical_models(self):
        # Other repository tests may already have imported numerical libraries.
        # Check this helper's cold import in a fresh isolated process instead.
        program="""import importlib.util,sys
sys.path.insert(0,sys.argv[1])
spec=importlib.util.spec_from_file_location('isolated_reader',sys.argv[2])
reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
reader.modules()
assert not set(sys.modules)&{'numpy','pandas','pyarrow','sklearn','catboost','ngboost'}
print('METADATA_IMPORTS_ONLY')
"""
        result=subprocess.run([sys.executable,"-I","-B","-c",program,str(SOURCE),str(HELPER)],
            text=True,capture_output=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stdout.strip(),"METADATA_IMPORTS_ONLY")


class PreflightTests(unittest.TestCase):
    def setUp(self):
        (DRAFT/"test-tmp").mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=DRAFT/"test-tmp");self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.f=SyntheticFailure(self.root)
        self.workflow=("on:\n  workflow_dispatch:\n    inputs:\n      mode:\n        options: ["+d.VERSION+"]\n"
            "concurrency:\n  group: nfl-lab-single-writer\n  cancel-in-progress: false\njobs:\n"
            "  lab:\n    if: inputs.mode != '"+d.VERSION+"'\n  "+d.JOB+":\n"
            "    if: ${{ github.event_name == 'workflow_dispatch' && inputs.mode == '"+d.VERSION+"' && github.run_attempt == 1 }}\n"
            "    runs-on: ubuntu-latest\n    timeout-minutes: 4\n    permissions:\n      contents: write\n      actions: read\n").encode()
        for path in d.dependency_paths():
            dest=self.root/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(self.workflow if path==".github/workflows/lab.yml" else b"synthetic pinned source\n")
        self.go=d.template();self.go.update(approved=True,source_sha=self.f.current_source,issued_at_utc=self.f.before,
            expires_at_utc=(datetime.now(timezone.utc)+timedelta(minutes=10)).isoformat(),qualified_runtime=self.f.package,target=self.f.target,
            helper_sha256={p:s.sha((self.root/p).read_bytes()) for p in d.dependency_paths()})
        self.env=dict(GITHUB_ACTIONS="true",CI="true",RUNNER_ENVIRONMENT="github-hosted",GITHUB_REPOSITORY=d.REPO,
            GITHUB_EVENT_NAME="workflow_dispatch",GITHUB_RUN_ATTEMPT="1",GITHUB_JOB=d.JOB,STORE_PERMISSION="write",
            GITHUB_WORKFLOW_REF=d.WORKFLOW,GITHUB_REF="refs/heads/"+d.BRANCH,GITHUB_ACTOR="NickNicky19",GITHUB_ACTOR_ID="208912933",
            GITHUB_SHA=self.f.current_source,GITHUB_WORKFLOW_SHA=self.f.current_source,GITHUB_WORKSPACE=str(self.root),GITHUB_RUN_ID=self.f.current_run,
            GITHUB_EVENT_PATH=str(self.root/"event.json"))
        self.refresh()
    def refresh(self):
        raw=s.canonical(self.go);self.env.update(AUDIT_FAILED_ADMISSION_GO_JSON=raw.decode(),AUDIT_FAILED_ADMISSION_GO_SHA256=s.sha(raw))
        event=dict(inputs=dict(mode=d.VERSION,inference_builder_go_json=raw.decode(),inference_builder_go_sha256=s.sha(raw)),
            repository=dict(full_name=d.REPO),ref=d.BRANCH)
        (self.root/"event.json").write_bytes(s.canonical(event))
    def run_preflight(self):
        # Explicit git metadata mock; this never asserts a real deployed checkout.
        def git(args):return self.f.current_source+"\n" if args[:3]==["git","rev-parse","HEAD"] else ""
        with patch.object(d,"TARGET",self.f.target):return d.preflight(self.env,self.root,read_head=git)
    def test_explicit_synthetic_owner_event_source_pins_and_permissions(self):
        self.assertEqual(self.run_preflight()["source_sha"],self.f.current_source)
    def test_second_attempt_rejected(self):
        self.env["GITHUB_RUN_ATTEMPT"]="2"
        with self.assertRaisesRegex(d.DiagnosticError,"ACTUAL_OWNER_DIAGNOSTIC_CONTEXT_REQUIRED"):self.run_preflight()
    def test_caller_pass_flag_rejected(self):
        self.go["PASS"]=True;self.refresh()
        with self.assertRaisesRegex(d.DiagnosticError,"CLOSED_OWNER_DIAGNOSTIC_GO"):self.run_preflight()
    def test_contents_read_is_not_proposed_as_a_working_contract(self):
        with self.assertRaisesRegex(d.DiagnosticError,"EXACT_DIAGNOSTIC_PERMISSION_CONTRACT"):
            d.verify_workflow(self.workflow.replace(b"contents: write",b"contents: read"))
    def test_source_pin_edit_rejected(self):
        (self.root/d.TOOL).write_bytes(b"changed\n")
        with self.assertRaisesRegex(d.DiagnosticError,"EXACT_DIAGNOSTIC_SOURCE_PINS"):self.run_preflight()
    def test_package_initializer_pin_edit_rejected(self):
        (self.root/"nfl_lab/__init__.py").write_bytes(b"changed initializer\n")
        with self.assertRaisesRegex(d.DiagnosticError,"EXACT_DIAGNOSTIC_SOURCE_PINS"):self.run_preflight()
    def test_generic_lab_must_exclude_this_diagnostic(self):
        raw=self.workflow.replace(("inputs.mode != '"+d.VERSION+"'").encode(),b"true")
        with self.assertRaisesRegex(d.DiagnosticError,"GENERIC_LAB_MUST_EXCLUDE_DIAGNOSTIC_MODE"):d.verify_workflow(raw)

    def native_result(self):
        runner=self.root/"runner-temp";runner.mkdir()
        self.env.update(RUNNER_TEMP=str(runner),GITHUB_TOKEN="ghs_SYNTHETIC_TEST_ONLY")
        reader=d.client_type()
        def injected(*args,**kwargs):
            kwargs.update(transport=self.f.transport,process="5"*64)
            return reader(*args,**kwargs)
        def git(args,**kwargs):
            return self.f.current_source+"\n" if args[:3]==["git","rev-parse","HEAD"] else ""
        with patch.object(d,"TARGET",self.f.target),patch.object(d,"client_type",return_value=injected),\
                patch.object(d.subprocess,"check_output",side_effect=git):
            result=json.loads(d.execute(self.env,self.root))
        return result

    def test_complete_native_orchestration_includes_both_current_job_checks_under_http_cap(self):
        result=self.native_result()
        self.assertEqual(result["HTTP_calls"],len(self.f.calls))
        self.assertLessEqual(result["HTTP_calls"],40)
        self.assertEqual(sum(c.full_url==s.API+"/actions/runs/"+self.f.current_run for c in self.f.calls),2)
        self.assertEqual(sum(c.full_url==s.API+"/actions/runs/"+self.f.current_run+"/jobs?per_page=100&page=1" for c in self.f.calls),2)


class ActualWorkflowIntegrationTests(unittest.TestCase):
    def test_actual_installed_workflow_is_nested_and_preserves_existing_jobs(self):
        import yaml
        raw=(SOURCE/".github/workflows/lab.yml").read_bytes()
        d.verify_workflow(raw)
        workflow=yaml.load(raw,Loader=yaml.BaseLoader)
        self.assertNotIn(d.JOB,workflow)
        self.assertIn(d.JOB,workflow["jobs"])
        self.assertEqual(workflow["jobs"][d.JOB]["permissions"],{"contents":"write","actions":"read"})
        self.assertFalse(any("upload-artifact@" in step.get("uses","") for step in workflow["jobs"][d.JOB]["steps"]))
        self.assertEqual(workflow["concurrency"],{"group":d.GROUP,"cancel-in-progress":"false"})

    def test_actual_job_moved_to_top_level_is_rejected(self):
        raw=(SOURCE/".github/workflows/lab.yml").read_text()
        before,job=raw.rsplit("\n  "+d.JOB+":\n",1)
        broken=before+"\n"+d.JOB+":\n"+"".join(line[2:] if line.startswith("  ") else line for line in job.splitlines(True))
        with self.assertRaisesRegex(d.DiagnosticError,"EXACT_DIAGNOSTIC_PERMISSION_CONTRACT"):
            d.verify_workflow(broken.encode())


if __name__=="__main__":
    if sys.argv[1:]==["--native-budget-probe"]:
        resource.setrlimit(resource.RLIMIT_AS,(512 << 20,512 << 20))
        resource.setrlimit(resource.RLIMIT_CPU,(120,120));signal.alarm(180)
        case=PreflightTests("test_complete_native_orchestration_includes_both_current_job_checks_under_http_cap")
        case.setUp()
        try:
            result=case.native_result()
            print(json.dumps(dict(synthetic_only=True,HTTP_calls=result["HTTP_calls"],transfer_bytes=result["transfer_bytes"],
                output_bytes=len(s.canonical(result)),AS_hard_bytes=resource.getrlimit(resource.RLIMIT_AS)[1],
                RSS_peak_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,remote_writes=0)))
        finally:case.doCleanups()
    else:unittest.main()
