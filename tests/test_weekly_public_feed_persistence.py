"""Fictional derived bodies/owned temp storage; every Git/network operation mocked."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from jsonschema.exceptions import ValidationError
from nfl_lab import weekly_public_feed as feed
from nfl_lab.frozen_source_policy import load_frozen_source_policy as load_source_policy
from nfl_lab.operational_storage import OperationalStorage
from tools.export_weekly_public_feed_v1 import publish_files

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("fictional_reviewed_public_persist",ROOT/"tools/persist_state.py")
publish=importlib.util.module_from_spec(spec);spec.loader.exec_module(publish)


def reference(path):
    body=Path(path).read_bytes();return dict(path=str(path),bytes=len(body),sha256=hashlib.sha256(body).hexdigest())


class PublicFeedPersistenceChecks(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name);self.root=self.base/"checkout";self.root.mkdir()
        self.state=self.base/"dedicated-derived-state";self.cache=self.base/"original-cache"
        self.source_path=ROOT/"config/operational-source-policy-v2.json";self.source=load_source_policy(self.source_path)
        self.storage=OperationalStorage(self.cache,self.source,state=self.state)
        self.metadata=self.base/"export-metadata";self.storage.register_root(self.metadata)
        self.policy=dict(source_policy_sha256=self.source["_policy_sha256"],public_fields=list(feed.overlay().ROW_FIELDS))
        self.policy_path=self.metadata/"policy.json";self.storage.write_bytes(self.policy_path,feed.canonical(self.policy),replace=False)
        self.document=dict(schema_version="weekly-derived-selected-feed-v1",state="DERIVED_SELECTED_ONLY",season=2030,week=7,
            created_at="2030-10-24T09:00:00.000000Z",expires_at="2030-10-25T17:00:00Z",
            producer_policy_sha256="a"*64,rights_authority_sha256="b"*64,rights_receipt_sha256="c"*64,
            durability_receipt_sha256="d"*64,r0_identity_sha256="e"*64,identity_scope_sha256="f"*64,
            rows=[dict(player_id="fictional-sleeper",game_id="fictional-espn",category="rush_att",method_id="COUNT_A",
                model_version="a"*64,procedure_version="b"*64,product="point_mean",prediction_functional="expected_mean",
                forecast_value=0,horizon="player_game",source_cutoff_utc="2030-10-24T15:00:00Z",issued_at="2030-10-24T08:00:00Z",
                persistence_completed_at="2030-10-24T08:30:00Z",kickoff_utc="2030-10-25T17:00:00Z",valid_until_utc="2030-10-25T17:00:00Z",
                selection_sha256="c"*64,source_policy_sha256=self.source["_policy_sha256"],query_source_sha256="d"*64)],
            coverage=dict(private_selected_rows=1,public_rows=1,fallback_counts={}))
        self.counter=0
        self.plan_path,self.plan,self.files=self.export(self.document)

    def tearDown(self):self.tmp.cleanup()

    def export(self,document):
        self.counter+=1
        files=publish_files(document,self.state,self.policy,write=lambda p,b:self.storage.write_bytes(p,b,replace=False))
        manifest=self.metadata/f"manifest-{self.counter}.json";self.storage.write_bytes(manifest,feed.canonical(files),replace=False)
        plan=dict(schema_version="weekly-public-feed-export-plan-v1",execution_authorized=True,authority_kind="AUTOMATED_REGISTERED_DERIVED_POLICY",
            registration_policy_sha256=reference(self.policy_path)["sha256"],policy=reference(self.policy_path),source_policy=reference(self.source_path),
            cache_root=str(self.cache),state_root=str(self.state),publication_manifest=str(manifest))
        path=self.metadata/f"plan-{self.counter}.json";self.storage.write_bytes(path,feed.canonical(plan),replace=False)
        return path,plan,files["files"]

    def invoke(self,path=None,storage=None):
        path=path or self.plan_path
        return publish.persist_public_export(self.root,path,reference(path)["sha256"],storage=storage or self.storage)

    def test_legacy_plain_json_gate_and_default_review_scope_are_unchanged(self):
        state=self.base/"legacy";state.mkdir();(state/"ordinary.json").write_text("{}")
        with patch.object(publish,"git",side_effect=AssertionError("no derived gzip")):
            self.assertIsNone(publish.persist(self.root,state))
        with patch.object(publish,"publication_files",wraps=publish.publication_files) as scan:
            self.assertEqual(publish.reviewed_publication(self.state,self.plan["publication_manifest"],self.source["_policy_sha256"]),self.files)
            scan.assert_called_once_with(self.state)

    def test_existing_owner_and_exact_map_are_forwarded_without_private_scan(self):
        with patch.object(publish,"publication_files",side_effect=AssertionError("broad state scan forbidden")),\
                patch("nfl_lab.operational_storage.OperationalStorage",side_effect=AssertionError("second owner forbidden")),\
                patch.object(publish,"persist",return_value="FICTIONAL_FORWARDED") as sink:
            self.assertEqual(self.invoke(),"FICTIONAL_FORWARDED")
        args,kw=sink.call_args;self.assertEqual(args,(self.root,self.state));self.assertIs(kw["storage"],self.storage)
        self.assertEqual(kw["files"],self.files);self.assertEqual(kw["policy_path"],self.source_path)
        self.assertIs(kw["metadata_policy"],True)
        self.assertEqual(self.storage.snapshot()["limit_bytes"],512<<20)

    def test_standalone_reopens_only_existing_export_owner_not_root_data(self):
        with patch("nfl_lab.operational_storage.OperationalStorage",return_value=self.storage) as factory,patch.object(publish,"persist"):
            publish.persist_public_export(self.root,self.plan_path,reference(self.plan_path)["sha256"])
        self.assertEqual(factory.call_args.args[0],self.cache);self.assertEqual(factory.call_args.kwargs,{})
        changed={**self.plan,"cache_root":str(self.base/"missing-cache")};p=self.metadata/"missing-cache-plan.json";p.write_bytes(feed.canonical(changed))
        with patch("nfl_lab.operational_storage.OperationalStorage",side_effect=AssertionError("must not initialize absent owner")):
            with self.assertRaises(FileNotFoundError):publish.persist_public_export(self.root,p,reference(p)["sha256"])
        self.assertFalse((self.root/"data").exists())

    def test_missing_manifest_wrong_plan_policy_and_owner_reject_before_publisher(self):
        for change in [dict(publication_manifest=None),dict(execution_authorized=False),dict(registration_policy_sha256="0"*64),dict(cache_root=str(self.base/"other-owner"))]:
            p=self.metadata/("bad-"+str(len(list(self.metadata.iterdir())))+".json");p.write_bytes(feed.canonical({**self.plan,**change}))
            with patch.object(publish,"persist",side_effect=AssertionError("publisher reached")),self.assertRaises(ValueError):self.invoke(p)
        with patch.object(publish,"persist",side_effect=AssertionError("publisher reached")),self.assertRaisesRegex(ValueError,"exact public export plan"):
            publish.persist_public_export(self.root,self.plan_path,"0"*64,storage=self.storage)

    def test_closed_paths_fail_before_any_candidate_private_payload_read(self):
        manifest=self.metadata/"private-path-manifest.json"
        doc=dict(schema_version=publish.PUBLICATION_SCHEMA,review_state="ACCEPTED",policy_sha256=self.source["_policy_sha256"],files={"private/models.bin":"a"*64,"private/labels.json":"b"*64})
        manifest.write_bytes(feed.canonical(doc))
        from nfl_lab.private_draft_store import read_local
        with patch("nfl_lab.private_draft_store.read_local",wraps=read_local) as reads,self.assertRaisesRegex(ValueError,"closed derived"):
            publish.reviewed_publication(self.state,manifest,self.source["_policy_sha256"],selected_only=True)
        self.assertEqual([Path(c.args[0]) for c in reads.call_args_list],[manifest])

    def test_closed_schema_support_bytes_filename_and_genuine_receipt(self):
        for mutation in [dict(raw_inputs=["FICTIONAL_RAW"]),dict(category="fantasy_ppr"),dict(product="point_blend"),dict(forecast_value=-1)]:
            doc=deepcopy(self.document);doc["rows"][0].update(mutation);path,plan,files=self.export(doc)
            with self.subTest(mutation=mutation),self.assertRaises(ValidationError):publish.validate_public_export(self.state,files,self.policy,self.source["_policy_sha256"])
        names=list(self.files);bad={"public/weekly-adaptive-v1/2030-W07/20301024T090000.000000Z--"+"0"*64+".json":self.files[names[0]],names[1]:self.files[names[1]]}
        p=self.state/next(iter(bad));p.write_bytes((self.state/names[0]).read_bytes())
        with self.assertRaisesRegex(ValueError,"filename"):publish.validate_public_export(self.state,bad,self.policy,self.source["_policy_sha256"])
        with self.assertRaisesRegex(ValueError,"receipt binding"):publish.validate_public_export(self.state,self.files,{**self.policy,"extra":"DIFFERENT_POLICY"},self.source["_policy_sha256"])

    def test_existing_append_only_guard_rejects_rewrite_and_accepts_same_bytes(self):
        name=next(n for n in self.files if n.endswith(".json"));body=(self.state/name).read_bytes()
        listing=f"100644 blob {'a'*40} {len(body)}\tstate/{name}".encode()+b"\0"
        for same in (True,False):
            data=body if same else b"x"*len(body)
            with patch.object(publish.subprocess,"run",side_effect=[SimpleNamespace(stdout=listing),SimpleNamespace(stdout=data)]):
                if same:publish.validate_existing_public(self.root,"a"*40,self.files)
                else:
                    with self.assertRaisesRegex(ValueError,"overwrite existing public evidence"):publish.validate_existing_public(self.root,"a"*40,self.files)

    def test_v2_publication_catalog_is_closed_and_uses_its_exact_schema_pin(self):
        document=deepcopy(self.document);document["schema_version"]="weekly-derived-selected-feed-v2"
        row=document["rows"][0]
        catalog=dict(schema_version="weekly-generic-future-producer-v1-selected-version-catalog",current_values_used=False,
            public_policy_registration="REQUIRED_SEPARATELY; not automatic approval",
            rows=[{k:row[k] for k in ("category","method_id","procedure_version","model_version")}])
        publication=dict(schema_version="weekly-derived-publication-v2",authority_sha256="a"*64,repository="NickNicky19/NFL-forecasting",
            source_sha="b"*40,run_id="123",run_attempt=1,workflow_path=".github/workflows/lab.yml",export_job="public-export",api_job_id=1,
            selected_body_sha256="c"*64,source_version_catalog_sha256="d"*64,version_catalog_sha256=feed.digest(catalog),version_catalog=catalog)
        document.update(publication=publication,publication_sha256=feed.digest(publication))
        _,_,files=self.export(document)
        self.assertEqual(publish.validate_public_export(self.state,files,self.policy,self.source["_policy_sha256"]),files)
        document["publication"]["version_catalog"]["rows"][0]["weights"]=["FICTIONAL_NEVER_PUBLIC"]
        _,_,files=self.export(document)
        with self.assertRaises(ValidationError):publish.validate_public_export(self.state,files,self.policy,self.source["_policy_sha256"])
        with patch.dict(publish.PUBLIC_FEED_SCHEMAS,{"weekly-derived-selected-feed-v2":"0"*64}):
            with self.assertRaisesRegex(ValueError,"schema code pin"):publish.validate_public_export(self.state,files,self.policy,self.source["_policy_sha256"])

    def test_real_persist_composition_stages_only_two_files_and_exact_remote_scope(self):
        calls=[];scopes=[];publication_commands=[];remote="a"*40;commit="b"*40
        def git(*args,**kw):
            calls.append(args)
            if args[:2]==("rev-parse","refs/remotes/origin/lab-state"):return remote+"\n"
            if args==("rev-parse","HEAD"):return commit+"\n"
            if args[0]=="ls-remote":return commit+"\trefs/heads/lab-state\n"
            return ""
        def run(command,**kw):
            if "nfl_lab.cli" in command:scopes.append(json.loads(kw["input"]));publication_commands.append(command)
            return SimpleNamespace(returncode=1 if "diff" in command else 0,stdout=b"")
        with patch.object(publish,"git",side_effect=git),patch.object(publish.subprocess,"run",side_effect=run):self.invoke()
        self.assertEqual(len(scopes),1);self.assertEqual(scopes[0]["files"],self.files)
        self.assertEqual(scopes[0]["verified_remote_commit"],commit);self.assertEqual(scopes[0]["policy_sha256"],self.source["_policy_sha256"])
        self.assertEqual(publication_commands[0][publication_commands[0].index("--cache")+1],str(self.cache))
        self.assertIn("--frozen-public-policy",publication_commands[0])
        self.assertIn(("push","origin","HEAD:refs/heads/lab-state"),calls)
        staged=next(c for c in calls if c[:3]==("--literal-pathspecs","add","--"))
        self.assertEqual(staged[3:],tuple("state/"+n for n in sorted(self.files)));self.assertFalse(any("--force" in c for c in calls))
        self.assertEqual(len(list((self.storage.live_root/"publication-worktrees").rglob("*.json"))),1)


if __name__=="__main__":unittest.main()
