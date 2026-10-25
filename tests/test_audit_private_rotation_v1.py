"""Fictional service/Actions identities only; no real token, GitHub or NFL I/O."""
import contextlib
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from nfl_lab import audit_private_rotation_v1 as rotation, private_draft_store as store
from tools import audit_private_rotation_v1 as entry, private_draft_store_v2 as cli
from test_private_draft_store_v2 import Server, Response, RUN, SOURCE


class RotationServer(Server):
    def __init__(self):
        super().__init__(); self.phase = "write"; self.completed = {}; self.started = {}; self.extra = []
        self.now = datetime.now(timezone.utc)
        self.old_runtime = "d" * 32
        nonce = store.probe.fixture(RUN); digest = store.sha(nonce)
        self.old = dict(schema_version="weekly-private-draft-binding-v2", repository=store.REPO, runtime_id=self.old_runtime,
            origin_run_id=RUN, release_id=90, tag_name="weekly-private-runtime-v2-" + self.old_runtime, canary_asset_id=80,
            canary_name="canary-" + digest + ".txt", canary_sha256=digest, canary_bytes=117, browser_tag="untagged-" + "c" * 20,
            config_sha256=store.config_sha())
        total = 29605302 - 117; each, remainder = divmod(total, 38)
        self.old_assets = [dict(id=80, name=self.old["canary_name"], size=117, state="uploaded")]
        self.old_assets += [dict(id=200+i, name="unknown-retained-"+str(i), size=each+(i < remainder), state="uploaded") for i in range(38)]

    def enter(self, phase):
        at = datetime.now(timezone.utc).isoformat()
        if phase != self.phase:
            self.completed[self.phase] = at
        self.phase = phase; self.started[phase] = at

    def __call__(self, request, timeout):
        url = request.full_url; parts = urlsplit(url); query = parse_qs(parts.query)
        if "/actions/runs/" in url:
            self.calls.append(request)
            if "/jobs?" in url:
                jobs = [dict(id=51+i, name=rotation.JOBS[p], run_id=int(RUN), head_sha=SOURCE,
                    status="completed" if p in self.completed else "in_progress", conclusion="success" if p in self.completed else None,
                    completed_at=self.completed.get(p), started_at=self.started.get(p, datetime.now(timezone.utc).isoformat()))
                    for i, p in enumerate(rotation.JOBS) if p in self.completed or p == self.phase]
                return Response(dict(total_count=len(jobs), jobs=jobs))
            owner = dict(login="NickNicky19", id=208912933)
            return Response(dict(id=int(RUN), head_sha=SOURCE, event="workflow_dispatch", run_attempt=1, status="in_progress",
                path=".github/workflows/lab.yml", repository=dict(full_name=store.REPO), head_repository=dict(full_name=store.REPO),
                actor=owner, triggering_actor=owner, created_at=(self.now-timedelta(seconds=30)).isoformat()))
        if request.method == "GET" and parts.path == "/repos/"+store.REPO+"/releases":
            self.calls.append(request)
            old = dict(id=90, tag_name=self.old["tag_name"], draft=True, published_at=None, url=store.API+"/releases/90")
            releases = [old, *self.extra] + ([self.release()] if self.tag else [])
            page = int(query["page"][0]); return Response(releases[(page-1)*5:page*5])
        if request.method == "GET" and "/releases/90" in url:
            self.calls.append(request)
            return Response(self.old_assets if "/assets?" in url else dict(id=90, draft=True, published_at=None, tag_name=self.old["tag_name"], url=store.API+"/releases/90"))
        if request.method == "GET" and any(parts.path.endswith("/releases/"+str(r["id"])+"/assets") for r in self.extra):
            self.calls.append(request); return Response([])
        if "/releases/assets/80" in url or request.method != "GET" and "/releases/90" in url:
            raise AssertionError("Old canary/model bodies and mutations are forbidden")
        return super().__call__(request, timeout)


class RotationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name); self.server = RotationServer(); self.invoked = []
        now = self.server.now
        census = dict(schema_version=rotation.VERSION+"-pending-census", complete=True, as_of_utc=(now-timedelta(seconds=61)).isoformat(),
            owner_evidence_sha256=store.sha(b"fictional complete unresolved-journal census"), reservations=[])
        self.root = rotation.root_template(source_sha=SOURCE, workflow_ref=store.REPO+"/.github/workflows/lab.yml@refs/heads/fictional",
            runtime_id="e"*32, issued_at_utc=(now-timedelta(seconds=60)).isoformat(), expires_at_utc=(now+timedelta(minutes=45)).isoformat(),
            preserved_bindings=[self.server.old], pending_census=census)
        self.root["approved"] = True

    def env(self, phase):
        out = self.base/(phase+"-output"); out.touch()
        root_text = rotation.canonical(self.root).decode()
        event = self.base/(phase+"-event.json")
        event.write_text(json.dumps(dict(inputs=dict(mode=rotation.VERSION, inference_builder_go_json=root_text,
            inference_builder_go_sha256=rotation.sha(root_text.encode())), repository=dict(full_name=store.REPO), ref="refs/heads/fictional")))
        return dict(GITHUB_ACTIONS="true", CI="true", RUNNER_ENVIRONMENT="github-hosted", GITHUB_REPOSITORY=store.REPO,
            GITHUB_EVENT_NAME="workflow_dispatch", GITHUB_RUN_ATTEMPT="1", GITHUB_RUN_ID=RUN, GITHUB_SHA=SOURCE,
            GITHUB_WORKFLOW_SHA=SOURCE, GITHUB_WORKSPACE=str(rotation.ROOT), GITHUB_REF="refs/heads/fictional",
            GITHUB_WORKFLOW_REF=self.root["workflow_ref"], GITHUB_JOB=rotation.JOBS[phase], STORE_PERMISSION="read" if phase=="read" else "write",
            GITHUB_ACTOR="NickNicky19", GITHUB_ACTOR_ID="208912933", RUNNER_TEMP=str(self.base), GITHUB_OUTPUT=str(out), GITHUB_EVENT_PATH=str(event),
            AUDIT_PRIVATE_ROTATION_GO_JSON=root_text, AUDIT_PRIVATE_ROTATION_GO_SHA256=rotation.sha(root_text.encode()))

    def factory(self, env, journal):
        self.server.enter(next(p for p in rotation.JOBS if rotation.JOBS[p] == env["GITHUB_JOB"]))
        job = dict(execution_lane="github_actions", workflow_ref=env["GITHUB_WORKFLOW_REF"], workflow_sha=SOURCE,
            job_id=env["GITHUB_JOB"], permission=env["STORE_PERMISSION"], event_name="workflow_dispatch", api_job_id=0, run_authenticated=False)
        client = store.Client("ghs_READ" if env["STORE_PERMISSION"]=="read" else "ghs_WRITE", RUN, journal=journal,
            source_sha=SOURCE, transport=self.server, process=store.sha(("metadata-"+env["GITHUB_JOB"]).encode()), job=job)
        client.identity_metadata = {}; original = client.json
        def json_call(url, **kwargs):
            value = original(url, **kwargs)
            if "/actions/runs/" in url: client.identity_metadata[url] = value
            return value
        client.json = json_call
        allow = client.allow
        def routes(url):
            if "/releases?per_page=5&page=" in url:
                client.allowed.add(url); return url
            return allow(url)
        client.allow = routes; client.authenticate_actions_job()
        return client

    def runner(self, env):
        def invoke(argv, timeout):
            self.assertGreater(timeout, 0); self.assertLessEqual(timeout,180)
            self.invoked.append(argv[4]); directory=Path(argv[argv.index("--authorization")+1]).parent
            if argv[4]=="initialize": self.assertTrue((directory/"GLOBAL_RESERVATION.json").is_file())
            child_env=dict(env,GITHUB_TOKEN="ghs_READ" if env["STORE_PERMISSION"]=="read" else "ghs_WRITE")
            process=store.sha((env["GITHUB_JOB"]+argv[4]).encode())
            with patch.object(cli,"limits"), patch.object(cli,"checkout_identity",return_value=True), patch.object(store,"process_identity",return_value=process), contextlib.redirect_stdout(io.StringIO()) as out:
                code=cli.main(argv[4:],environ=child_env,transport=self.server)
            result=json.loads(out.getvalue())
            if code: raise rotation.RotationError(result["reason"])
            return result
        return invoke

    def run_phase(self, phase, previous=None):
        env=self.env(phase)
        if previous is not None:
            text=rotation.canonical(previous).decode()
            env.update(AUDIT_PRIVATE_ROTATION_HANDOFF_JSON=text,AUDIT_PRIVATE_ROTATION_HANDOFF_SHA256=rotation.sha(text.encode()))
        return rotation.run_phase(phase,env,self.root,runner=self.runner(env),client_factory=self.factory),env

    def test_preparation_never_reads_credentials_or_transport(self):
        with patch.object(entry.os,"environ",{}), contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(entry.main(["write"]),2)
        self.assertIn("PREPARATION_ONLY_NO_IO",out.getvalue());self.assertEqual(self.server.calls,[])

    def test_preflight_binds_only_real_event_inference_builder_fields_source_and_role(self):
        env=self.env("write")
        with patch.object(rotation.subprocess,"check_output",side_effect=[SOURCE+"\n",""]):
            self.assertEqual(rotation.preflight("write",env),self.root)
        for key,value in (("GITHUB_RUN_ATTEMPT","2"),("GITHUB_JOB",rotation.JOBS["read"]),("STORE_PERMISSION","read"),("GITHUB_ACTOR_ID","1")):
            with self.subTest(key=key), self.assertRaises(rotation.RotationError): rotation.preflight("write",dict(env,**{key:value}))
        doc=json.loads(Path(env["GITHUB_EVENT_PATH"]).read_text());doc["inputs"].pop("inference_builder_go_json")
        doc["inputs"]["bootstrap_locators_json"]=env["AUDIT_PRIVATE_ROTATION_GO_JSON"];Path(env["GITHUB_EVENT_PATH"]).write_text(json.dumps(doc))
        with patch.object(rotation.subprocess,"check_output",side_effect=[SOURCE+"\n",""]), self.assertRaises(rotation.RotationError):rotation.preflight("write",env)

    def test_three_real_store_cli_operations_roles_and_117_byte_only_qualification(self):
        before,write_env=self.run_phase("write");read,read_env=self.run_phase("read",before);qualified,qual_env=self.run_phase("qualify",read)
        self.assertEqual(self.invoked,["initialize","pin","boundary","qualify"])
        self.assertEqual(len([r for r in self.server.calls if r.method=="POST"]),2)
        self.assertEqual(len(self.server.assets),1);self.assertEqual(self.server.assets[0]["size"],117)
        self.assertTrue(qualified["qualification"]["engineering_boundary_v2"])
        self.assertFalse(qualified["qualification"]["restricted_upload_authorized"])
        self.assertFalse(qualified["private_durability_qualified"])
        self.assertEqual(qualified["binding"]["runtime_id"],"e"*32)
        self.assertEqual(before["quota_reservation"]["charged_existing_bytes"],29605302)
        self.assertEqual(before["quota_reservation"]["reserved_after_bytes"],2*rotation.RUNTIME_CAP)
        self.assertTrue(read["read"]["all10_denied"])
        for env in (write_env,read_env,qual_env):
            raw=Path(env["GITHUB_OUTPUT"]).read_bytes();self.assertLessEqual(len(raw),rotation.OUTPUT_CAP)
            self.assertNotIn(b"https://",raw);self.assertNotIn(b"ghs_",raw);self.assertNotIn(str(self.base).encode(),raw)
        self.assertTrue(all(r.method in {"GET","POST"} for r in self.server.calls))
        self.assertFalse(any(r.get_header("Accept")=="application/octet-stream" and "/releases/assets/80" in r.full_url for r in self.server.calls))

    def test_expired_unapproved_changed_pins_and_old_runtime_target_fail_before_calls(self):
        for field,value in (("approved",False),("expires_at_utc",(self.server.now-timedelta(seconds=1)).isoformat()),("runtime_id",self.server.old_runtime),
                            ("new_fits",1),("private_payload_bytes",117),("helper_sha256",{})):
            root=deepcopy(self.root);root[field]=value
            with self.subTest(field=field),self.assertRaises((rotation.RotationError,store.StoreError)):
                rotation.validate_root(root,now=datetime.now(timezone.utc))
        self.assertEqual(self.server.calls,[])

    def test_only_closed_four_canary_operations_and_new_binding_can_get_phase_go(self):
        env=self.env("write")
        for operation in ("append","restore","delete","qualify"):
            with self.subTest(operation=operation),self.assertRaises(rotation.RotationError):rotation.phase_go(operation,{},self.root,env)
        with self.assertRaises(rotation.RotationError):rotation.phase_go("pin",dict(binding=self.server.old),self.root,env)

    def test_pending_original_assets_unknown_reservations_and_global_capacity_fail_before_post(self):
        pending=dict(reservation_sha256="1"*64,runtime_id=self.server.old_runtime,release_id=90,pending_bytes=4<<20,pending_assets=1)
        self.root["pending_census"]["reservations"]=[pending]
        with self.assertRaisesRegex(rotation.RotationError,"PENDING_EXISTING_RUNTIME_CAP"):self.run_phase("write")
        self.assertEqual(self.invoked,[]);self.assertFalse(any(r.method=="POST" for r in self.server.calls))

    def test_unknown_pending_counts_full_runtime_and_cannot_be_silently_dropped(self):
        self.root["pending_census"]["reservations"]=[dict(reservation_sha256="1"*64,runtime_id=None,release_id=None,pending_bytes=117,pending_assets=1)]
        written,_=self.run_phase("write")
        self.assertEqual(written["quota_reservation"]["pending_unlocated_runtimes"],1)
        self.assertEqual(written["quota_reservation"]["reserved_after_bytes"],3*rotation.RUNTIME_CAP)
        for complete in (False,None):
            bad=deepcopy(self.root);bad["pending_census"]["complete"]=complete
            with self.assertRaises(rotation.RotationError):rotation.validate_root(bad,now=datetime.now(timezone.utc))

    def test_exact_512mib_global_reservation_boundary(self):
        for i in range(14):self.server.extra.append(dict(id=300+i,tag_name="unknown-owned-draft-"+str(i),draft=True,published_at=None,url=store.API+"/releases/"+str(300+i)))
        written,_=self.run_phase("write")
        self.assertEqual(written["quota_reservation"]["reserved_after_bytes"],512<<20)
        self.assertEqual(written["quota_reservation"]["existing_draft_runtimes"],15)

    def test_starter_orphans_are_charged_at_full_asset_cap_before_post(self):
        self.server.old_assets.append(dict(id=999,name="unknown-incomplete-upload",size=0,state="starter"))
        with self.assertRaisesRegex(rotation.RotationError,"EXISTING_RUNTIME_BYTES_CAP"):self.run_phase("write")
        self.assertEqual(self.invoked,[])

    def test_real_metadata_client_subclass_rejects_post_and_any_asset_body_read(self):
        env=dict(self.env("write"),GITHUB_TOKEN="ghs_WRITE")
        journal=self.base/"metadata-test-journal";journal.mkdir(mode=0o700)
        with patch.object(cli,"checkout_identity",return_value=True):
            client=rotation.metadata_client(env,journal,transport=self.server)
        count=len(self.server.calls)
        for kwargs in (dict(method="POST",data=b"fictional"),dict(data=b"fictional"),dict(octet=True),dict(download=True)):
            with self.subTest(kwargs=kwargs),self.assertRaisesRegex(rotation.RotationError,"METADATA_GET_ONLY"):
                client.request(store.API,**kwargs)
        self.assertEqual(len(self.server.calls),count)

    def test_pending_unlocated_runtime_aggregate_cannot_exceed_its_32mib(self):
        self.root["pending_census"]["reservations"]=[dict(reservation_sha256=str(i)*64,runtime_id="f"*32,release_id=None,
            pending_bytes=20<<20,pending_assets=1)for i in (1,2)]
        with self.assertRaisesRegex(rotation.RotationError,"PENDING_UNLOCATED_RUNTIME_CAP"):self.run_phase("write")
        self.assertEqual(self.invoked,[])

    def test_16_existing_runtimes_or_pending_target_prevent_creation(self):
        for i in range(15):self.server.extra.append(dict(id=300+i,tag_name="unknown-owned-draft-"+str(i),draft=True,published_at=None,url=store.API+"/releases/"+str(300+i)))
        with self.assertRaisesRegex(rotation.RotationError,"GLOBAL_RUNTIME_RESERVATION_CAP"):self.run_phase("write")
        self.assertEqual(self.invoked,[])
        bad=deepcopy(self.root);bad["pending_census"]["reservations"]=[dict(reservation_sha256="1"*64,runtime_id=bad["runtime_id"],release_id=None,pending_bytes=0,pending_assets=0)]
        with self.assertRaisesRegex(rotation.RotationError,"ALREADY_RESERVED"):rotation.validate_root(bad,now=datetime.now(timezone.utc))

    def test_bad_or_wrong_run_handoff_cannot_start_boundary(self):
        written,_=self.run_phase("write")
        bad=deepcopy(written);bad["run_id"]="40099999999"
        with self.assertRaises(rotation.RotationError):self.run_phase("read",bad)
        self.assertEqual(self.invoked,["initialize","pin"])

    def test_incomplete_predecessor_api_job_is_rejected_before_boundary(self):
        written,_=self.run_phase("write")
        original=self.factory
        def factory(env,journal):
            client=original(env,journal)
            for value in client.identity_metadata.values():
                if isinstance(value,dict) and "jobs" in value:
                    for job in value["jobs"]:
                        if job["name"]==rotation.JOBS["write"]:job["conclusion"]="failure"
            return client
        env=self.env("read");text=rotation.canonical(written).decode()
        env.update(AUDIT_PRIVATE_ROTATION_HANDOFF_JSON=text,AUDIT_PRIVATE_ROTATION_HANDOFF_SHA256=rotation.sha(text.encode()))
        with self.assertRaisesRegex(rotation.RotationError,"COMPLETED_PREDECESSOR"):
            rotation.run_phase("read",env,self.root,runner=self.runner(env),client_factory=factory)
        self.assertEqual(self.invoked,["initialize","pin"])

    def test_ambiguous_post_retains_reservation_and_never_retries_or_claims_qualification(self):
        self.server.ambiguous=True
        with self.assertRaises(rotation.RotationError):self.run_phase("write")
        posts=len([r for r in self.server.calls if r.method=="POST"])
        with self.assertRaisesRegex(rotation.RotationError,"NO_RETRY"):self.run_phase("write")
        self.assertEqual(len([r for r in self.server.calls if r.method=="POST"]),posts)
        self.assertTrue(list((self.base/(rotation.VERSION+"-"+RUN+"-write")/"journal").glob("*.reservation.json")))
        self.assertEqual((self.base/"write-output").read_bytes(),b"")

    def test_safe_output_refuses_private_paths_or_tokens(self):
        for value in ("ghs_FICTIONAL","/tmp/fictional","https://fictional.invalid"):
            with self.assertRaises(rotation.RotationError):rotation.safe_output(dict(value=value))

    def test_native_failure_diagnostic_accepts_only_explicit_closed_store_failure(self):
        class Child:
            returncode=1
            def communicate(self,timeout):return self.body,"FICTIONAL_PRIVATE_LIBRARY_STDERR"
            def poll(self):return 1
            def wait(self):return 1
        child=Child()
        for body,expected in ((dict(state="FAILED",reason="HTTP_OR_RATE_AMBIGUITY",HTTP_calls=3,private_durability_qualified=False),"HTTP_OR_RATE_AMBIGUITY"),
                              (dict(reason="FICTIONAL_PRIVATE_LIBRARY_VALUE"),"ROTATION_NATIVE_CLI_FAILED")):
            child.body=json.dumps(body)
            with patch.object(rotation.subprocess,"Popen",return_value=child),self.assertRaisesRegex(rotation.RotationError,expected):
                rotation.run_cli(["python","-I","-B","native","initialize"],1)


if __name__=="__main__":unittest.main()
