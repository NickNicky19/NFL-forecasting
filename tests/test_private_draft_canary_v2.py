"""Fictional hosted-role handoff; no real Actions/HTTP/token/NFL access."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools import private_draft_canary_v2 as driver
from tools import private_draft_store_v2 as cli
from nfl_lab import private_draft_store as store
from test_private_draft_store_v2 import Server,Response,RUN,SOURCE
from retained_source_fixture import retained_procedure, registered_bytes, workflow_job, REPOSITORY


class CanaryDriverTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.directory=Path(self.temp.name);self.server=Server();self.invocations=[]
        retained = retained_procedure(driver, 'config/private-draft-canary-v2.json')
        retained.__enter__(); self.addCleanup(retained.__exit__, None, None, None)
        self.config=driver.verify_sources()
    def tearDown(self):self.temp.cleanup()
    def environment(self,phase):
        output=self.directory/(phase+"-output");output.touch()
        event=self.directory/(phase+"-event");event.write_text(json.dumps(dict(inputs=dict(mode=driver.MODE),repository=dict(full_name=store.REPO),ref="refs/heads/fictional")))
        return dict(GITHUB_ACTIONS="true",CI="true",RUNNER_ENVIRONMENT="github-hosted",GITHUB_REPOSITORY=store.REPO,GITHUB_EVENT_NAME="workflow_dispatch",
            GITHUB_RUN_ATTEMPT="1",CANARY_MODE=driver.MODE,GITHUB_JOB=driver.JOBS[phase],STORE_PERMISSION="read" if phase=="read" else "write",GITHUB_RUN_ID=RUN,
            GITHUB_SHA=SOURCE,GITHUB_WORKFLOW_SHA=SOURCE,GITHUB_WORKSPACE=str(driver.ROOT),GITHUB_REF="refs/heads/fictional",GITHUB_WORKFLOW_REF=store.REPO+"/.github/workflows/lab.yml@refs/heads/fictional",
            RUNNER_TEMP=str(self.directory),GITHUB_OUTPUT=str(output),GITHUB_EVENT_PATH=str(event))
    def preflight(self,phase,env):
        original=driver.safe_read
        def read(path,cap):return SOURCE.encode() if Path(path)==driver.ROOT/".git/HEAD" else original(path,cap)
        with patch.object(driver,"safe_read",side_effect=read):return driver.preflight(phase,env)
    def runner(self,env):
        def invoke(argv,timeout):
            self.assertGreater(timeout,0);self.assertLessEqual(timeout,180)
            self.invocations.append(argv[4]);role=env["GITHUB_JOB"];ids={driver.JOBS["write"]:51,driver.JOBS["read"]:52,driver.JOBS["qualify"]:53}
            def transport(request,limit):
                if request.full_url==store.API+"/actions/runs/"+RUN+"/jobs?per_page=100&page=1":
                    self.server.calls.append(request)
                    return Response(dict(total_count=1,jobs=[dict(id=ids[role],name=role,status="in_progress",run_id=int(RUN),head_sha=SOURCE)]))
                return self.server(request,limit)
            child_env=dict(env,GITHUB_TOKEN="ghs_READ" if env["STORE_PERMISSION"]=="read" else "ghs_WRITE")
            # The actual production runner launches fresh CLI processes. Here
            # identities/roles and transport are explicitly fictional mocks.
            identity=store.sha((role+argv[4]).encode())
            with patch.object(cli,"limits"),patch.object(cli,"checkout_identity",return_value=True),patch.object(store,"process_identity",return_value=identity),contextlib.redirect_stdout(io.StringIO()) as out:
                code=cli.main(argv[4:],environ=child_env,transport=transport)
            self.assertEqual(code,0,out.getvalue());return json.loads(out.getvalue())
        return invoke
    def attach(self,env,label,document):
        text=driver.canonical(document).decode();env["CANARY_"+label.upper()+"_JSON"]=text;env["CANARY_"+label.upper()+"_SHA256"]=driver.digest(text.encode())
    def test_source_config_schema_pins_precede_target_import(self):
        self.assertEqual(self.config["runtime_id"],hashlib.sha256(b"NFLweeklyruntime20261024v2").hexdigest()[:32])
        source=(ROOT/"tools/private_draft_canary_v2.py").read_text()
        self.assertLess(source.index('config!=verify_sources()'),source.index('from nfl_lab import private_draft_store'))
        with patch.object(driver,"CONFIG_SHA256", "0"*64),self.assertRaises(driver.CanaryError):driver.verify_sources()
    def test_no_execute_is_preparation_only(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:self.assertEqual(driver.main(["write"]),2)
        self.assertEqual(json.loads(out.getvalue())["state"],"CANARY_PREPARATION_ONLY_NO_IO")
    def test_preflight_accepts_only_exact_dispatch_source_role_attempt(self):
        env=self.environment("write");self.preflight("write",env)
        for key,value in [("CANARY_MODE","daily"),("GITHUB_RUN_ATTEMPT","2"),("GITHUB_JOB",driver.JOBS["read"]),("STORE_PERMISSION","read"),("GITHUB_WORKFLOW_SHA","0"*40)]:
            with self.subTest(key=key),self.assertRaises(driver.CanaryError):self.preflight("write",dict(env,**{key:value}))
    def test_only_four_registered_operations_get_GO(self):
        env=self.environment("write")
        for operation in ["append","restore","delete","publish"]:
            with self.assertRaises(driver.CanaryError):driver.make_go(operation,{},env,self.config,store)
        self.assertEqual(set(sum(self.config["operations"].values(),[])),{"initialize","pin","boundary","qualify"})
    def test_canonical_handoff_digest_and_safe_metadata_only(self):
        env={};self.attach(env,"binding",{"id":1});self.assertEqual(driver.handoff(env,"binding"),{"id":1})
        env["CANARY_BINDING_JSON"]+=' '
        with self.assertRaises(driver.CanaryError):driver.handoff(env,"binding")
        for value in ["https://example.invalid/secret","ghs_FICTIONAL","/tmp/private"]:
            with self.assertRaises(driver.CanaryError):driver.public_safe({"value":value})
    def test_three_roles_four_CLI_operations_and_exact_safe_proof_handoff(self):
        write_env=self.environment("write");self.preflight("write",write_env)
        with contextlib.redirect_stdout(io.StringIO()):written=driver.run_phase("write",write_env,self.config,runner=self.runner(write_env))
        read_env=self.environment("read")
        for label,document in written.items():self.attach(read_env,label,document)
        self.preflight("read",read_env)
        with contextlib.redirect_stdout(io.StringIO()):read=driver.run_phase("read",read_env,self.config,runner=self.runner(read_env))
        env=self.environment("qualify")
        for label,document in {**written,**read}.items():self.attach(env,label,document)
        with contextlib.redirect_stdout(io.StringIO()) as output:driver.run_phase("qualify",env,self.config,runner=self.runner(env))
        lines=output.getvalue().splitlines();self.assertEqual(len([v for v in lines if v.startswith("PRIVATE_DRAFT_CANARY_")]),2)
        proof=json.loads(next(v.split(' ',1)[1] for v in lines if v.startswith("PRIVATE_DRAFT_CANARY_QUALIFICATION_V2 ")))
        self.assertTrue(proof["engineering_boundary_v2"]);self.assertFalse(proof["restricted_upload_authorized"])
        self.assertEqual(self.invocations,["initialize","pin","boundary","qualify"])
        self.assertEqual(len([r for r in self.server.calls if r.method=="POST"]),2);self.assertEqual(len(self.server.assets),1);self.assertEqual(self.server.assets[0]["size"],117)
        self.assertNotIn("https://",output.getvalue());self.assertNotIn("ghs_",output.getvalue());self.assertNotIn(str(self.directory),output.getvalue());self.assertLessEqual(len(self.server.calls),160)
    def test_bad_handoff_never_starts_read_CLI(self):
        env=self.environment("read");self.attach(env,"binding",{"extra":"FICTIONAL_RAW_NOT_ALLOWED"})
        with self.assertRaises(store.StoreError):driver.run_phase("read",env,self.config,runner=lambda *args:(_ for _ in ()).throw(AssertionError()))
    def test_existing_workflow_and_old_probe_modes_preserved(self):
        old=registered_bytes('.github/workflows/lab.yml','dd6492ebb83d22a65fdf3a7173d55ee042798ac7fbdab7a4deac4cf146870dfd')
        self.assertEqual(driver.digest(old),'dd6492ebb83d22a65fdf3a7173d55ee042798ac7fbdab7a4deac4cf146870dfd')
        retained=(driver.ROOT/'.github/workflows/lab.yml').read_text();prefix=retained.split('  private-draft-v2-write:\n',1)[0]
        prefix=prefix.replace(', private-draft-canary-v2]',']').replace(" && inputs.mode != 'private-draft-canary-v2'",'')
        self.assertEqual(prefix,old.decode());self.assertEqual(retained.count('- cron:'),1);self.assertEqual(retained.count('group: nfl-lab-single-writer'),1)
        new=retained.split('  private-draft-v2-write:\n',1)[1]
        self.assertEqual(new.count('ref: ${{ github.sha }}'),3);self.assertEqual(new.count('persist-credentials: false'),3)
        self.assertEqual(new.count('actions: read'),3);self.assertEqual(new.count('contents: write'),2);self.assertEqual(new.count('contents: read'),1)
        self.assertIn("needs.private-draft-v2-read.result == 'success'",new);self.assertIn("!cancelled()",new)
        self.assertNotIn('upload-artifact',new);self.assertNotIn('pip install',new);self.assertNotIn('private_storage_probe.py',new)
        self.assertEqual(new.count('private_draft_canary_v2.py'),3);self.assertIn('timeout-minutes: 8',new);self.assertEqual(new.count('timeout-minutes: 4'),2)
        current=(REPOSITORY/'.github/workflows/lab.yml').read_text()
        for job in driver.JOBS.values():
            self.assertEqual(workflow_job(current,job),workflow_job(retained,job))
        with patch.object(driver,'ROOT',REPOSITORY),self.assertRaisesRegex(driver.CanaryError,'PINNED_SOURCE_CHANGED'):
            driver.verify_sources()
    def test_child_failure_logs_only_strict_safe_reason_and_counts(self):
        class Child:
            returncode=1
            def communicate(self,timeout):return json.dumps(dict(state="FAILED",reason="HTTP_OR_RATE_AMBIGUITY",HTTP_calls=3,private_durability_qualified=False)),"DO_NOT_ECHO_STDERR"
            def poll(self):return 1
            def wait(self):return 1
        with patch.object(driver.subprocess,"Popen",return_value=Child()),contextlib.redirect_stdout(io.StringIO()) as output:
            with self.assertRaises(driver.CanaryError):driver.run_cli(["python","-I","-B","pinned","initialize"],1)
        self.assertNotIn("DO_NOT_ECHO",output.getvalue());self.assertIn("HTTP_OR_RATE_AMBIGUITY",output.getvalue());self.assertNotIn("https://",output.getvalue())


if __name__=='__main__':unittest.main()
