"""Fictional in-memory service only; no NFL, credentials or real HTTP."""
import base64
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from urllib.error import URLError
from urllib.parse import parse_qs,urlsplit
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from nfl_lab import private_draft_store as s
from tools import private_draft_store_v2 as cli

RUN="40088888888";SOURCE="a"*40


class Response:
    def __init__(self,body=b"",status=200,headers=None):
        self.body=body if isinstance(body,bytes) else s.canonical(body)
        self.status=status;self.headers=headers or {"X-RateLimit-Remaining":"100"}
    def read(self,n):return self.body[:n]
    def __enter__(self):return self
    def __exit__(self,*args):return False


class Server:
    def __init__(self):
        self.tag=None;self.assets=[];self.calls=[];self.draft=True;self.ambiguous=False;self.redirect=False
    def metadata(self,a):return {k:v for k,v in a.items() if k!="body"}
    def release(self):return dict(id=91,draft=self.draft,published_at=None if self.draft else "fictional",tag_name=self.tag,url=s.API+"/releases/91",assets=[self.metadata(a) for a in self.assets])
    def add(self,name,body=b"fictional",size=None):
        a=dict(id=100+len(self.assets),name=name,size=len(body) if size is None else size,state="uploaded",digest="sha256:"+s.sha(body),url=s.API+"/releases/assets/"+str(100+len(self.assets)),browser_download_url="https://github.com/"+s.REPO+"/releases/download/untagged-"+"b"*20+"/"+name,body=body)
        self.assets.append(a);return a
    def __call__(self,request,timeout):
        self.calls.append(request);url=request.full_url;p=urlsplit(url);auth=request.get_header("Authorization","")
        if p.hostname in s.probe.CDN_HOSTS:
            assert not auth and not request.get_header("Cookie")
            return Response(self.assets[-1]["body"])
        if url==s.API:return Response(dict(full_name=s.REPO,url=s.API,private=False))
        if url==s.API+"/actions/runs/"+RUN:
            return Response(dict(id=int(RUN),head_sha=SOURCE,event="workflow_dispatch",run_attempt=1,status="in_progress",path=".github/workflows/lab.yml",repository=dict(full_name=s.REPO),head_repository=dict(full_name=s.REPO)))
        if url==s.API+"/actions/runs/"+RUN+"/jobs?per_page=100&page=1":
            return Response(dict(total_count=1,jobs=[dict(id=55,name="store_create",status="in_progress",run_id=int(RUN),head_sha=SOURCE)]))
        public="https://api.github.com/repos/cli/cli"
        control_name=s.probe.CONTROL_NAME;control_body=("c"*64+"  fictional\n").encode()
        meta=dict(id=7,url=public+"/releases/assets/7",name=control_name,size=len(control_body),state="uploaded",browser_download_url="https://github.com/cli/cli/releases/download/v2.0.0/"+control_name)
        if url==public+"/releases/tags/v2.0.0":
            assert not auth;return Response(dict(id=8,url=public+"/releases/8",tag_name="v2.0.0",draft=False,published_at="fictional",assets=[meta]))
        if url==meta["url"]:
            assert not auth;return Response(control_body if request.get_header("Accept")=="application/octet-stream" else meta)
        if url==meta["browser_download_url"]:
            assert not auth;return Response(control_body)
        if p.hostname=="github.com":
            assert not auth;return Response(status=404)
        if request.method=="GET" and p.path.startswith("/repos/"+s.REPO+"/releases/") and (not auth or auth=="Bearer ghs_READ"):
            return Response({"message":s.probe.RESOURCE_PERMISSION_MESSAGE},403) if auth else Response(status=404)
        if request.method=="GET" and "/releases/tags/" in url:
            return Response(self.release()) if self.tag else Response(status=404)
        if request.method=="POST" and url==s.API+"/releases":
            self.tag=json.loads(request.data)["tag_name"];return Response(self.release(),201)
        if request.method=="POST" and p.hostname=="uploads.github.com":
            name=parse_qs(p.query)["name"][0];a=self.add(name,request.data)
            if self.ambiguous:self.ambiguous=False;raise URLError("secret URL/token NEVER PRINT")
            return Response(self.metadata(a),201)
        if p.path.endswith("/releases/91"):return Response(self.release())
        if p.path.endswith("/releases/91/assets"):
            page=int(parse_qs(p.query).get("page",["1"])[0]);return Response([self.metadata(a) for a in self.assets[(page-1)*100:page*100]])
        if "/releases/assets/" in url:
            aid=int(p.path.rsplit("/",1)[-1]);a=next(a for a in self.assets if a["id"]==aid)
            if request.get_header("Accept")=="application/octet-stream":
                if self.redirect:return Response(status=302,headers={"Location":"https://objects.githubusercontent.com/fictional?signed=NEVER_PRINT"})
                return Response(a["body"])
            return Response(self.metadata(a))
        raise AssertionError("unhandled fictional route")


class DraftStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.journal=self.root/"journal";self.journal.mkdir(mode=0o700)
        self.server=Server();self.binding=s.initialize(self.client("init"),"d"*32)
    def tearDown(self):self.temp.cleanup()
    def client(self,label,read=False,actual_process=False,run_id=RUN):
        return s.Client("ghs_READ" if read else "ghs_WRITE",run_id,journal=self.journal,source_sha=SOURCE,transport=self.server,process=None if actual_process else s.sha(label.encode()))
    def bound(self,label,**kw):
        c=self.client(label,**kw);c.bind(self.binding);return c
    def qualified(self):
        before=s.pin_canary(self.bound("before"));read=s.boundary(self.bound("read",read=True),before)
        return s.qualify(self.bound("after"),before,read)
    def payload(self):
        body=b'{"fictional_runtime_only":true}'
        return body,dict(schema_version="weekly-private-payload-v2",payload_kind="forecast_batch",format="json",bytes=len(body),sha256=s.sha(body),source_policy_sha256="e"*64)
    def test_initialization_only_one_new_draft_and117byte_canary(self):
        self.assertNotEqual(self.binding["release_id"],422575680);self.assertEqual(len(self.server.assets),1);self.assertEqual(len(self.server.assets[0]["body"]),117)
        self.assertEqual(self.binding["browser_tag"],"untagged-"+"b"*20)
        posts=[r for r in self.server.calls if r.method=="POST"];self.assertEqual(len(posts),2)
        self.assertFalse(any(r.method in {"PATCH","DELETE"} for r in self.server.calls))
    def test_specific403_and_all_anonymous404_newcriterion_only(self):
        q=self.qualified();self.assertTrue(q["engineering_boundary_v2"]);self.assertEqual(q["strict_v1_unchanged"],"INCONCLUSIVE");self.assertFalse(q["restricted_upload_authorized"])
    def test_arbitrary403_rate429_redirect_and_missing_control_fail(self):
        before=s.pin_canary(self.bound("before"))
        for status,headers,message in [(403,{"X-RateLimit-Remaining":"9"},"different"),(403,{"X-RateLimit-Remaining":"0"},s.probe.RESOURCE_PERMISSION_MESSAGE),(429,{},s.probe.RESOURCE_PERMISSION_MESSAGE),(302,{},""),(200,{},"")]:
            c=self.bound("read",read=True);real=self.server
            def transport(req,timeout):
                if req.full_url==s.API+"/releases/91":return Response({"message":message},status,headers)
                return real(req,timeout)
            c.transport=transport
            with self.subTest(status=status,message=message),self.assertRaises(s.StoreError):s.boundary(c,before)
    def test_no_qualification_on_partial_or_sameprocess_proof(self):
        before=s.pin_canary(self.bound("before"))
        with self.assertRaises(s.StoreError):s.boundary(self.bound("before",read=True),before)
        with self.assertRaises(s.StoreError):s.qualify(self.bound("after"),before,{})
    def test_append_remote_manifest_and_separateprocess_restore(self):
        q=self.qualified();body,m=self.payload();c=self.bound("writer",actual_process=True)
        descriptor=s.append(c,body,m,q)
        with self.assertRaises(s.StoreError):s.restore(c,descriptor,self.root/"sameprocess")
        # Actual fresh Python process, all transport answers reconstructed from
        # this FICTIONAL service; no network fallback or model execution.
        state=dict(tag=self.server.tag,assets=[dict(a,body=base64.b64encode(a["body"]).decode()) for a in self.server.assets])
        fixture=self.root/"fictional-state.json";fixture.write_text(json.dumps(dict(state=state,binding=self.binding,descriptor=descriptor)))
        program='''import sys,json,base64,importlib.util
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from nfl_lab import private_draft_store as s
spec=importlib.util.spec_from_file_location("fictional",Path(sys.argv[1])/"tests/test_private_draft_store_v2.py");t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)
d=json.loads(Path(sys.argv[2]).read_text());server=t.Server();server.tag=d["state"]["tag"];server.assets=[dict(a,body=base64.b64decode(a["body"])) for a in d["state"]["assets"]]
c=s.Client("ghs_WRITE",t.RUN,journal=sys.argv[3],source_sha=t.SOURCE,transport=server);c.bind(d["binding"])
r=s.restore(c,d["descriptor"],sys.argv[4]);print(json.dumps({"exact_readback":r["exact_readback"],"separate_process":r["separate_process"]}))
'''
        p=subprocess.run([sys.executable,"-I","-B","-c",program,str(ROOT),str(fixture),str(self.journal),str(self.root/"restored")],capture_output=True,text=True,timeout=10,check=True)
        self.assertTrue(json.loads(p.stdout)["exact_readback"]);self.assertEqual((self.root/"restored").read_bytes(),body);self.assertEqual((self.root/"restored").stat().st_mode&0o777,0o600)
    def test_append_can_reuse_qualified_runtime_in_later_run(self):
        q=self.qualified();body,m=self.payload();s.append(self.bound("later",run_id="40099999999"),body,m,q)
    def test_ambiguous_completed_blob_reused_without_retrying_its_POST(self):
        q=self.qualified();body,m=self.payload();self.server.ambiguous=True
        with self.assertRaises(s.StoreError):s.append(self.bound("writer"),body,m,q)
        blob_posts=lambda:len([r for r in self.server.calls if r.method=="POST" and "name=blob-" in r.full_url])
        posts=blob_posts();descriptor=s.append(self.bound("newwriter"),body,m,q)
        self.assertEqual(blob_posts(),posts);self.assertEqual(descriptor["entry"]["payload"]["sha256"],s.sha(body))
    def test_failedpost_reservation_before_transport(self):
        c=self.bound("writer");seen=[];original=c.transport
        def fail(req,timeout):
            if req.method=="POST":
                seen.extend(self.journal.glob("*.reservation.json"));raise URLError("NO LOG")
            return original(req,timeout)
        c.transport=fail
        with self.assertRaises(s.StoreError):c.upload("blob-"+s.sha(b"fictional")+".bin",b"fictional")
        self.assertGreaterEqual(len(seen),3)
        with self.assertRaises(s.StoreError):self.bound("again").upload("blob-"+s.sha(b"fictional")+".bin",b"fictional")
    def test_draft_mutation_stops_before_any_payload(self):
        q=self.qualified();body,m=self.payload();self.server.draft=False;posts=len(self.server.assets)
        with self.assertRaises(s.StoreError):s.append(self.bound("writer"),body,m,q)
        self.assertEqual(len(self.server.assets),posts)
    def test_inventory_unknown_orphans_count_toward_total(self):
        for i in range(4):self.server.add("unknown-orphan-"+str(i),size=s.ASSET_CAP)
        with self.assertRaisesRegex(s.StoreError,"RUNTIME_BYTES_CAP"):self.bound("inventory").inventory()
    def test_inventory_bounded_pagination_counts_all_assets(self):
        for i in range(100):self.server.add("unknown-"+str(i))
        assets,total=self.bound("inventory").inventory();self.assertEqual(len(assets),101);self.assertGreater(total,117)
        for i in range(28):self.server.add("more-"+str(i))
        with self.assertRaisesRegex(s.StoreError,"ASSET_COUNT_CAP"):self.bound("inventory2").inventory()
    def test_pending_reservations_charge_even_without_remote_asset(self):
        c=self.bound("pending");c.reserve("fictional-reserved",b"abc",name="missing")
        _,total=c.inventory();self.assertEqual(total,120)
    def test_payload_scope_and_size_hash_contract(self):
        body,m=self.payload()
        for update in [dict(payload_kind="ledger"),dict(payload_kind="raw_feed"),dict(sha256="0"*64),dict(bytes=True),dict(extra="private")]:
            with self.subTest(update=update),self.assertRaises(s.StoreError):s.payload_manifest(dict(m,**update),body)
        with self.assertRaises(s.StoreError):s.payload_manifest(dict(m,bytes=s.ASSET_CAP+1),b"x"*(s.ASSET_CAP+1))
    def test_restore_corruption_existing_destination_and_symlinks(self):
        q=self.qualified();body,m=self.payload();d=s.append(self.bound("writer"),body,m,q);c=self.bound("reader")
        destination=self.root/"restore";destination.write_bytes(b"keep")
        with self.assertRaises(FileExistsError):s.restore(c,d,destination)
        self.assertEqual(destination.read_bytes(),b"keep")
        link=self.root/"link";link.symlink_to(destination)
        with self.assertRaises(s.StoreError):s.restore(self.bound("reader2"),d,link)
        self.server.assets[-2]["body"]=b"corrupt"
        with self.assertRaises(s.StoreError):s.restore(self.bound("reader3"),d,self.root/"new")
    def test_wrong_original_fixture_and_runtime_config_rejected(self):
        for patching in [dict(release_id=422575680),dict(config_sha256="0"*64),dict(browser_tag="bad/path")]:
            with self.subTest(patching=patching),self.assertRaises(s.StoreError):self.client("bad").bind(dict(self.binding,**patching))
    def test_crossrepo_and_nonhttps_routes_refused(self):
        c=self.bound("routes")
        for url in ["https://api.github.com/repos/other/private/releases/1","http://api.github.com/repos/"+s.REPO,"https://api.github.com.evil.invalid/"]:
            with self.assertRaises(s.StoreError):c.request(url)
    def test_cdn_redirect_strips_authorization_and_cookies(self):
        c=self.bound("redirect");self.server.redirect=True
        b=self.binding;c.read_asset(b["canary_asset_id"],b["canary_name"],117,b["canary_sha256"])
        self.assertFalse(self.server.calls[-1].get_header("Authorization"));self.assertFalse(self.server.calls[-1].get_header("Cookie"))
    def test_real_network_preserves_default_proxy_handler(self):
        source=Path(s.__file__).read_text();self.assertNotIn("ProxyHandler({})",source)
        self.assertIn("build_opener(probe.NoRedirect())",source)
    def test_finite_call_and_wall_caps(self):
        c=self.bound("limits");c.calls=40
        with self.assertRaises(s.StoreError):c.draft()
        c=self.bound("wall");c.started=c.clock()-181
        with self.assertRaises(s.StoreError):c.draft()
    def test_cli_preparation_does_not_read_env_or_start_transport(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(cli.main(["initialize"],environ={},transport=lambda *a:(_ for _ in ()).throw(AssertionError())),2)
        self.assertEqual(json.loads(output.getvalue())["state"],"PREPARATION_ONLY_NO_IO")
    def test_cli_failure_output_contains_no_private_material(self):
        authorization=self.root/"authorization";authorization.write_text('{}')
        with patch.object(cli,"limits"),contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(cli.main(["initialize","--execute","--authorization",str(authorization),"--authorization-sha256","0"*64],environ={"GITHUB_TOKEN":"ghs_SECRET"}),1)
        text=output.getvalue();self.assertNotIn(str(self.root),text);self.assertNotIn("ghs_SECRET",text);self.assertNotIn("https://",text)
    def test_cli_initialize_exact_GO_is_functional_with_mock_transport(self):
        journal=self.root/"new-journal";journal.mkdir(mode=0o700);server=Server()
        go=dict(schema_version="weekly-private-operation-GO-v2.1",approved=True,operation="initialize",repository=s.REPO,run_id=RUN,source_sha=SOURCE,config_sha256=s.config_sha(),scope_manifest_sha256=None,qualification_sha256=None,single_writer_group="nfl-lab-single-writer",runtime_id="e"*32,input_sha256={},job_id="store_create",workflow_ref=s.REPO+"/.github/workflows/lab.yml@refs/heads/fictional")
        path=self.root/"GO";path.write_bytes(s.canonical(go));output_path=self.root/"private-binding"
        env=dict(GITHUB_ACTIONS="true",GITHUB_REPOSITORY=s.REPO,GITHUB_EVENT_NAME="workflow_dispatch",GITHUB_RUN_ATTEMPT="1",STORE_PERMISSION="write",GITHUB_RUN_ID=RUN,GITHUB_SHA=SOURCE,GITHUB_TOKEN="ghs_FICTIONAL",CI="true",RUNNER_ENVIRONMENT="github-hosted",GITHUB_WORKFLOW_SHA=SOURCE,GITHUB_WORKFLOW_REF=s.REPO+"/.github/workflows/lab.yml@refs/heads/fictional",GITHUB_REF="refs/heads/fictional",GITHUB_JOB="store_create")
        args=["initialize","--execute","--authorization",str(path),"--authorization-sha256",s.sha(path.read_bytes()),"--journal",str(journal),"--runtime-id","e"*32,"--receipt",str(output_path)]
        with patch.object(cli,"limits"),patch.object(cli,"checkout_identity",return_value=True),contextlib.redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(cli.main(args,environ=env,transport=server),0)
        self.assertEqual(json.loads(stdout.getvalue())["state"],"COMPLETE");self.assertEqual(json.loads(output_path.read_bytes())["runtime_id"],"e"*32)
        self.assertNotIn("ghs_FICTIONAL",stdout.getvalue());self.assertNotIn("https://",stdout.getvalue());self.assertNotIn(str(output_path),stdout.getvalue())
    def test_restore_parent_descriptor_walk_rejects_symlink_ancestor(self):
        real=self.root/"real";real.mkdir();link=self.root/"parent-link";link.symlink_to(real,target_is_directory=True)
        # Even a replacement after the advisory parents check is caught by
        # the O_NOFOLLOW directory-descriptor walk.
        with patch.object(s,"parents_safe",side_effect=lambda p:Path(p).absolute()):
            with self.assertRaises(OSError):s.create_local(link/"new",b"fictional")
        self.assertFalse((real/"new").exists())
    def test_proof_missing_process_unknown_fields_and_empty_route_summary_rejected(self):
        before=s.pin_canary(self.bound("before"));read=s.boundary(self.bound("read",read=True),before)
        for mutation in [lambda b,r:b.pop("process_identity"),lambda b,r:r.update(routes=[]),lambda b,r:r.update(routes=r["routes"][:-1]),lambda b,r:b.update(extra=True)]:
            b,r=copy.deepcopy(before),copy.deepcopy(read);mutation(b,r)
            with self.assertRaises(s.StoreError):s.qualify(self.bound("after"),b,r)
    def test_every_exact_route_and403_predicate_is_required(self):
        before=s.pin_canary(self.bound("before"));read=s.boundary(self.bound("read",read=True),before)
        for update in [dict(route="browser"),dict(principal="anonymous"),dict(status=200),dict(status=302),dict(resource_permission_message_exact_match=False),dict(rate_remaining_nonzero=False),dict(retry_after_present=True),dict(request_failed=True)]:
            bad=copy.deepcopy(read);bad["routes"][0].update(update)
            with self.subTest(update=update),self.assertRaises(s.StoreError):s.qualify(self.bound("after"),before,bad)
    def test_pairwise_process_job_permissions_and_clock_provenance(self):
        before=s.pin_canary(self.bound("before"));read=s.boundary(self.bound("read",read=True),before)
        for field,value in [("process_identity",before["process_identity"]),("process_identity","bad"),("created_at_utc","2099-01-01T00:00:00Z"),("operation","pin"),("source_sha","b"*40)]:
            bad=copy.deepcopy(read);bad[field]=value
            with self.subTest(field=field),self.assertRaises(s.StoreError):s.qualify(self.bound("after"),before,bad)
        bad=copy.deepcopy(read);bad["job"]["permission"]="write"
        with self.assertRaises(s.StoreError):s.qualify(self.bound("after"),before,bad)
    def test_pending_POSTs_reserve_slots_not_only_bytes(self):
        c=self.bound("pending")
        for i in range(127):c.reserve("pending-"+str(i),b"x",name="pending-"+str(i))
        assets,total=c.inventory();self.assertEqual(c.inventory_slots,128);self.assertLess(total,s.TOTAL_CAP)
        posts=len([r for r in self.server.calls if r.method=="POST"])
        with self.assertRaisesRegex(s.StoreError,"ASSET_COUNT_CAP"):c.upload("blob-"+s.sha(b"new")+".bin",b"new")
        self.assertEqual(len([r for r in self.server.calls if r.method=="POST"]),posts)
    def test_existing_digest_blob_reuse_is_exact_fullreadback_not_overwrite(self):
        q=self.qualified();body,m=self.payload();s.append(self.bound("writer1"),body,m,q)
        posts=len([r for r in self.server.calls if r.method=="POST" and "name=blob-" in r.full_url])
        s.append(self.bound("writer2"),body,m,q)
        self.assertEqual(len([r for r in self.server.calls if r.method=="POST" and "name=blob-" in r.full_url]),posts)
        blob=next(a for a in self.server.assets if a["name"].startswith("blob-"));blob["body"]=b"corrupted"
        allposts=len([r for r in self.server.calls if r.method=="POST"])
        with self.assertRaises(s.StoreError):s.append(self.bound("writer3"),body,m,q)
        self.assertEqual(len([r for r in self.server.calls if r.method=="POST"]),allposts)
    def test_pinned_phase_inputs_reject_changed_binding_before_read_descriptor(self):
        for operation in ["pin","boundary","qualify","restore"]:
            go=dict(schema_version="weekly-private-operation-GO-v2.1",approved=True,operation=operation,repository=s.REPO,run_id=RUN,source_sha=SOURCE,config_sha256=s.config_sha(),scope_manifest_sha256=None,qualification_sha256=None,single_writer_group="nfl-lab-single-writer",runtime_id=self.binding["runtime_id"],input_sha256={k:"0"*64 for k in cli.INPUTS[operation]},job_id="store_create",workflow_ref=s.REPO+"/.github/workflows/lab.yml@refs/heads/fictional")
            args=[operation,"--execute","--journal",str(self.journal)]
            for field in cli.INPUTS[operation]:
                path=self.root/(operation+"-"+field);path.write_bytes(s.canonical(self.binding if field=="binding" else {}));args +=["--"+field.replace("_","-"),str(path)]
            path=self.root/(operation+"-GO");path.write_bytes(s.canonical(go));args +=["--authorization",str(path),"--authorization-sha256",s.sha(path.read_bytes())]
            env=dict(GITHUB_ACTIONS="true",GITHUB_REPOSITORY=s.REPO,GITHUB_EVENT_NAME="workflow_dispatch",GITHUB_RUN_ATTEMPT="1",STORE_PERMISSION="read" if operation=="boundary" else "write",GITHUB_RUN_ID=RUN,GITHUB_SHA=SOURCE,GITHUB_JOB="store_create",GITHUB_WORKFLOW_REF=s.REPO+"/.github/workflows/lab.yml@refs/heads/fictional")
            with patch.object(cli,"limits"),contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(cli.main(args,environ=env,transport=lambda *a:(_ for _ in ()).throw(AssertionError())),1)
            self.assertEqual(json.loads(output.getvalue())["reason"],"PHASE_INPUT_HASH")
    def test_no_local_forged_Actions_bootstrap_context(self):
        with self.assertRaises(s.StoreError):cli.actions_context({"GITHUB_ACTIONS":"true","GITHUB_SHA":SOURCE},"write")
    def test_qualified_proof_embeds_and_revalidates_complete_chain(self):
        q=self.qualified();q["read_proof"]["routes"]=[]
        q["read_sha256"]=s.sha(s.canonical(q["read_proof"]))
        body,m=self.payload()
        with self.assertRaises(s.StoreError):s.append(self.bound("writer"),body,m,q)
    def test_authenticated_Actions_metadata_must_match_source_run_and_job(self):
        c=self.client("metadata");c.job.update(execution_lane="github_actions",job_id="store_create",run_authenticated=False)
        real=c.transport
        def wrong(req,timeout):
            result=real(req,timeout)
            if req.full_url==s.API+"/actions/runs/"+RUN:
                body=json.loads(result.body);body["head_sha"]="0"*40;return Response(body)
            return result
        c.transport=wrong
        with self.assertRaisesRegex(s.StoreError,"ACTIONS_API_IDENTITY"):c.authenticate_actions_job()
        self.assertFalse(c.job["run_authenticated"])
    def test_new_snapshot_kinds_require_v21_catalog_and_exact_manifest(self):
        body,m=self.payload()
        for kind in ["feature_snapshot","source_snapshot","identity_snapshot"]:
            self.assertEqual(s.payload_manifest(dict(m,payload_kind=kind),body)["payload_kind"],kind)
        self.assertEqual(json.loads(s.CONFIG.read_bytes())["payload_kind_catalog_version"],"private-runtime-kinds-v2.1")
    def test_closed_formal_phase_schema_agrees_with_runtime(self):
        import jsonschema
        schema=json.loads((ROOT/"schemas/private-draft-store-v2.json").read_bytes())
        validator=jsonschema.Draft202012Validator(dict(schema,**{"$ref":"#/$defs/proof_qualified"}),format_checker=jsonschema.FormatChecker())
        proof=self.qualified();validator.validate(proof)
        proof["read_proof"]["routes"]=[]
        with self.assertRaises(jsonschema.ValidationError):validator.validate(proof)
    def test_restore_cannot_omit_producer_process_identity(self):
        q=self.qualified();body,m=self.payload();descriptor=s.append(self.bound("writer"),body,m,q)
        descriptor["entry"].pop("producer_process")
        with self.assertRaises(s.StoreError):s.restore(self.bound("reader"),descriptor,self.root/"invalid")
    def test_restore_proof_flags_must_all_be_true(self):
        q=self.qualified();body,m=self.payload();descriptor=s.append(self.bound("writer"),body,m,q)
        proof=s.restore(self.bound("reader"),descriptor,self.root/"valid-restore")
        for flag in ["exact_readback","separate_process","draft_before_after"]:
            bad=copy.deepcopy(proof);bad[flag]=False
            with self.subTest(flag=flag),self.assertRaises(s.StoreError):s.check_proof(self.bound("consumer"),bad,"restore")
    def test_restore_proof_requires_valid_payload_digest_and_bytes(self):
        q=self.qualified();body,m=self.payload();descriptor=s.append(self.bound("writer"),body,m,q)
        proof=s.restore(self.bound("reader"),descriptor,self.root/"valid-restore")
        for update in [dict(payload_sha256="bad"),dict(bytes=0),dict(bytes=True),dict(bytes=s.ASSET_CAP+1)]:
            with self.subTest(update=update),self.assertRaises(s.StoreError):s.check_proof(self.bound("consumer"),dict(proof,**update),"restore")


if __name__=="__main__":unittest.main()
