"""Synthetic exact-byte owner authority; actual installed Python/Node wire.

No native owner admission/capture is claimed. Fictional LeafCDF artifacts and
all authority callbacks are explicit local fixtures. No network is used.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from nfl_lab import weekly_mae_point_inference_v2_1 as adapter
from nfl_lab import stat_point_mae_public_v2_2 as public
import test_weekly_mae_point_inference_v2 as fixtures

SOURCE=Path(public.__file__).resolve().parents[1]
JS_CONSUMER=SOURCE/'nfl_lab/stat-point-mae-public-v2-2.js'
JS_CONSUMER_SHA256='89d3e649d8e22bb1a7b11fc28dabd42aae8d175617bdd3fbadcb6709345dd066'


def sha(body):
    return hashlib.sha256(body).hexdigest()


class SyntheticOwnerPipeline:
    """Independent fixture authority whitelists exact bytes, not PASS flags."""
    def __init__(self, model, *, mean_fallback=False):
        self.model = model
        self.candidate = model.predict()[2]  # Original cold RB law: median2, mean3.
        if mean_fallback:
            c = self.candidate
            c.update(method_id="LEGACY_LAW_MEAN_FALLBACK", procedure_version=c["base_procedure_version"],
                point_profile_sha256=sha(b"FICTIONAL_SEPARATELY_ADMITTED_MEAN_FALLBACK_PROFILE"),
                forecast_product="point_mean", prediction_functional="expected_mean",
                forecast_value=c["separate_expected_mean"], functional_proof=None)
            c.pop("candidate_sha256")
            c["candidate_sha256"] = adapter._digest(c)
        c = self.candidate
        entry = {k: c[k] for k in public.ENTRY_KEYS if k in c}
        entry.update(artifact_sha256=c["model_version"], source_contract_sha256=public.digest(c["source_contract"]),
            public_roles=["RB"])
        self.catalog_doc = dict(schema_version=public.CATALOG, selection_product=public.PRODUCT,
            selection_metric="MAE", registered_at="2099-10-30T00:00:00Z",
            owner_admission_receipt_sha256=sha(b"fictional-admitted-public-catalog"), entries=[entry])
        source = {k: c[k] for k in public.SOURCE_KEYS if k in c}
        source.update(source_contract_sha256=public.digest(c["source_contract"]),
            source_receipt_sha256=c["source_receipt"]["sha256"],
            feature_capture_receipt_sha256=c["feature_capture_receipt"]["sha256"],
            feature_binding_sha256=c["feature_binding"]["sha256"],
            feature_capture_completed_at=c["original_forecast"]["source_capture_completed_at"], public_roles=["RB"],
            identity_bridge_sha256=sha(b"fictional-actual-bridge-body"))
        self.registry_doc = dict(schema_version=public.REGISTRY, registered_at="2099-10-31T00:07:30Z",
            owner_admission_receipt_sha256=sha(b"fictional-admitted-current-snapshot"), records=[source])
        self.expected_registry = public.canonical(self.registry_doc)
        self.expected_catalog = public.canonical(self.catalog_doc)
        self.registry = public.admit_registry(self.registry_doc, verify_owner_registry=self.verify_registry)
        self.catalog = public.admit_catalog(self.catalog_doc, self.registry, verify_owner_catalog=self.verify_catalog)
        # This is a synthetic frozen fixture body. It is not a real NFL capture.
        self.frozen_body = public.canonical(c)
        self.receipt = dict(schema_version=public.CAPTURE, state="FROZEN_AND_READ_BACK", horizon="player_game",
            candidate_sha256=c["candidate_sha256"], capture_body_sha256=sha(self.frozen_body),
            selection_sha256=sha(b"fictional-frozen-MAE-choice"),
            identity={k: c[k] for k in ("season", "week", "game_id", "player_id", "target")},
            source_registry_sha256=self.registry.sha256,
            persistence_completed_at="2099-10-31T00:09:00Z", readback_completed_at="2099-10-31T01:15:00Z",
            **{k: c[k] for k in ("model_version", "procedure_version", "point_profile_sha256", "source_policy_sha256",
                "query_projection_sha256", "information_cutoff_utc", "issued_at", "issue_deadline_utc", "kickoff_utc")})
        # Enrich an independently hashed receipt body with its own reference hash.
        self.receipt.update(website_game_id="123456789", sleeper_id="101",
            identity_bridge_sha256=sha(b"fictional-actual-bridge-body"),
            identity_binding_sha256=sha(b"fictional-exact-canonical-website-record"),
            team=c["team"], opponent=c["opponent"])
        self.receipt["capture_receipt_sha256"] = sha(public.canonical(self.receipt))
        self.expected_receipt = public.canonical(self.receipt)
        self.capture_calls = 0
        self.capture = self.finalize(c, self.receipt)
        self.feed = public.export_feed([self.capture], self.catalog, self.registry,
            created_at="2099-10-31T01:16:00Z", owner_export_receipt_sha256=sha(b"fictional-owner-public-export"),
            verify_owner_export=self.verify_export)

    def verify_registry(self, kind, body):
        if kind != "SOURCE_REGISTRY" or body != self.expected_registry:
            raise ValueError("FICTIONAL_OWNER_SOURCE_REGISTRY_NOT_REGISTERED")

    def verify_catalog(self, kind, body):
        if kind != "CATALOG" or body != self.expected_catalog:
            raise ValueError("FICTIONAL_OWNER_CATALOG_NOT_REGISTERED")

    def verify_capture(self, body, candidate_sha256, catalog_sha256, registry_sha256):
        self.capture_calls += 1
        if (body != self.expected_receipt or candidate_sha256 != self.candidate["candidate_sha256"]
                or catalog_sha256 != self.catalog.sha256 or registry_sha256 != self.registry.sha256
                or json.loads(body)["capture_body_sha256"] != sha(self.frozen_body)):
            raise ValueError("FICTIONAL_INDEPENDENT_CAPTURE_READBACK_REJECTED")

    def finalize(self, candidate, receipt):
        return public.finalize_capture(candidate, receipt, self.catalog, self.registry,
            verify_owner_capture=self.verify_capture)

    def verify_export(self, body, catalog_sha256, registry_sha256):
        feed = public.strict_json(body)
        if (catalog_sha256 != self.catalog.sha256 or registry_sha256 != self.registry.sha256
                or feed["rows"] != [self.capture.document]
                or feed["owner_export_receipt_sha256"] != sha(b"fictional-owner-public-export")):
            raise ValueError("FICTIONAL_OWNER_EXPORT_REJECTED")


NODE='\nconst api=require(process.argv[1]),fs=require("fs"),x=JSON.parse(fs.readFileSync(0,"utf8")),feed=x.feed;\nif(x.mutate){const r=feed.rows[0];if(x.mutate==="nanMean")r.expected_mean=NaN;if(x.mutate==="boolPoint")r.selected_projection=true;}\ntry{const v=api.validate(feed),r=feed.rows[0],p=x.player||{game_id:r.website_game_id,id:r.sleeper_id,team:r.team,opp:r.opponent,pos:r.position},b=x.board||{season:r.season,week:r.week,games:[{id:r.website_game_id,kickoff:r.kickoff_utc,home:r.team,away:r.opponent}]},now=x.now||"2099-10-31T01:17:00Z",point=api.forPlayer(v,p,r.target,b,now),frozen=api.forPlayer(v,p,r.target,b,"2099-10-31T04:00:00Z");\nprocess.stdout.write(JSON.stringify({ok:true,point:point&&{value:point.value,mean:point.expectedMean,frozen:point.frozen},value:point&&point.value,expectedMean:point&&point.expectedMean,label:point&&point.label,card:api.cardPoint(v,p,r.target,b,now),rows:v.rows.length,frozen:frozen&&frozen.frozen,sourceSha:r.source_policy_sha256}));}catch(e){process.stdout.write(JSON.stringify({ok:false,error:e.message}));}\n'


class _SyntheticPublicFixture(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.model=fixtures.SyntheticPreparedLeaf(self.temp.name)
        self.pipeline=SyntheticOwnerPipeline(self.model)

    def tearDown(self):
        self.model.close()
        self.temp.cleanup()

    def node(self,feed=None,mutate=None,**kwargs):
        self.assertTrue(JS_CONSUMER.is_file(),"MATCHING_JS_CONSUMER_FIXTURE_REQUIRED: "+str(JS_CONSUMER))
        self.assertEqual(sha(JS_CONSUMER.read_bytes()),JS_CONSUMER_SHA256)
        self.assertIsNotNone(shutil.which("node"),"NODE_EXECUTABLE_REQUIRED_FOR_CROSS_LANGUAGE_CHECKS")
        result=subprocess.run([shutil.which("node"),"-e",NODE,str(JS_CONSUMER)],
            input=json.dumps(dict(feed=self.pipeline.feed if feed is None else feed,mutate=mutate,**kwargs),allow_nan=False),
            text=True,capture_output=True,check=True,timeout=10)
        return json.loads(result.stdout)

    def both_reject(self,feed):
        with self.assertRaises((ValueError,KeyError,TypeError)):
            public.validate_feed(feed)
        self.assertFalse(self.node(feed)["ok"])


class PublicMaeWireTests(_SyntheticPublicFixture):
    def test_one_numeric_category_real_candidate_to_owner_capture_to_js_values(self):
        p = self.pipeline
        public.validate_feed(p.feed)
        result = self.node()
        self.assertTrue(result["ok"], result)
        self.assertEqual((result["value"], result["expectedMean"], result["label"]), (2., 3., "Median fallback"))
        self.assertEqual(result["rows"], 1)
        self.assertTrue(result["frozen"])
        self.assertIn("Expected mean: 3.00", result["card"])
        self.assertGreater(p.capture_calls, 1)
        self.assertEqual(len(p.feed["catalog"]["entries"]), 1)
        self.assertGreater(public.clock(p.feed["rows"][0]["readback_completed_at"]),
                           public.clock(p.feed["rows"][0]["issue_deadline_utc"]))

    def test_honest_mean_fallback_stays_mean_without_mse_champion_claim(self):
        p = SyntheticOwnerPipeline(self.model, mean_fallback=True)
        result = self.node(p.feed)
        self.assertTrue(result["ok"], result)
        self.assertEqual((result["value"], result["expectedMean"], result["label"]), (3., 3., "Mean fallback"))
        self.assertNotIn("MSE", result["card"])
        wrong = deepcopy(p.feed); wrong["rows"][0]["selected_projection"] = 2.
        self.both_reject(wrong)

    def test_catalog_registry_and_owner_capabilities_are_required_not_pass_flags(self):
        p = self.pipeline
        with self.assertRaisesRegex(ValueError, "CAPABILITIES_REQUIRED"):
            public.finalize_capture(p.candidate, p.receipt, p.catalog_doc, p.registry_doc,
                verify_owner_capture=lambda *_: None)
        with self.assertRaisesRegex(ValueError, "OWNER_REGISTRY_VERIFIER"):
            public.admit_registry(p.registry_doc, verify_owner_registry=True)
        with self.assertRaisesRegex(ValueError, "INDEPENDENT_OWNER_VERIFICATION"):
            public.admit_registry(p.registry_doc, verify_owner_registry=lambda *_: True)
        changed = deepcopy(p.registry_doc); changed["records"][0]["query_source_sha256"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "NOT_REGISTERED"):
            public.admit_registry(changed, verify_owner_registry=p.verify_registry)

    def test_owner_rejects_rehashed_changed_candidate_and_fake_capture_state(self):
        p = self.pipeline
        candidate = deepcopy(p.candidate); candidate["forecast_value"] = 0.
        candidate.pop("candidate_sha256"); candidate["candidate_sha256"] = adapter._digest(candidate)
        receipt = deepcopy(p.receipt); receipt["candidate_sha256"] = candidate["candidate_sha256"]
        with self.assertRaisesRegex(ValueError, "INDEPENDENT_CAPTURE_READBACK_REJECTED"):
            p.finalize(candidate, receipt)
        receipt["state"] = "PASS"
        with self.assertRaisesRegex(ValueError, "FROZEN_READBACK_RECEIPT"):
            p.finalize(candidate, receipt)

    def test_owner_capability_bytes_cannot_change_after_verification(self):
        p = self.pipeline
        p.capture._body = public.canonical(dict(p.capture.document, expected_mean=400.))
        with self.assertRaisesRegex(ValueError, "CAPABILITY_BYTES_CHANGED"):
            public.export_feed([p.capture], p.catalog, p.registry, created_at=p.feed["created_at"],
                owner_export_receipt_sha256=p.feed["owner_export_receipt_sha256"], verify_owner_export=p.verify_export)

    def test_public_wire_rejects_raw_paths_receipt_bodies_probabilities_and_v1(self):
        for field, value in [("raw_source_path", "/private/source"), ("receipt_body", {"PASS": True})]:
            feed = deepcopy(self.pipeline.feed); feed["rows"][0][field] = value
            self.both_reject(feed)
        feed = deepcopy(self.pipeline.feed); feed["rows"][0]["target"] = "anytime_td"
        self.both_reject(feed)
        feed = deepcopy(self.pipeline.feed); feed["schema_version"] = "weekly-derived-selected-feed-v1"
        self.both_reject(feed)

    def test_median_lattice_bracket_role_and_unique_identity_checks(self):
        for field, value in [("selected_projection", 2.1), ("selected_projection", -1),
                             ("position", "WR"), ("mean_eligible", 1), ("conditional_on", "unconditional")]:
            feed = deepcopy(self.pipeline.feed); feed["rows"][0][field] = value
            self.both_reject(feed)
        feed = deepcopy(self.pipeline.feed); feed["rows"][0]["functional_proof"]["cdf_below"] = .5
        self.both_reject(feed)
        feed = deepcopy(self.pipeline.feed); feed["rows"].append(deepcopy(feed["rows"][0]))
        self.both_reject(feed)

    def test_exact_microsecond_persistence_deadline_and_readback_clocks(self):
        for field, value in [("persistence_completed_at", "2099-10-31T01:00:00Z"),
                             ("readback_completed_at", "2099-10-31T00:08:00Z"),
                             ("issued_at", "2099-10-31T00:04:59Z"),
                             ("kickoff_utc", "2099-02-30T03:00:00Z"),
                             ("issued_at", "2099-10-31T00:08:00")]:
            feed = deepcopy(self.pipeline.feed); feed["rows"][0][field] = value
            self.both_reject(feed)
        feed = deepcopy(self.pipeline.feed)
        feed["rows"][0]["persistence_completed_at"] = "2099-10-31T00:59:59.999999Z"
        public.validate_feed(feed)
        self.assertTrue(self.node(feed)["ok"])

    def test_js_finite_boolean_and_unavailable_mean_rejection(self):
        self.assertFalse(self.node(mutate="nanMean")["ok"])
        self.assertFalse(self.node(mutate="boolPoint")["ok"])
        feed = deepcopy(self.pipeline.feed); feed["rows"][0]["expected_mean"] = None
        self.both_reject(feed)

    def test_catalog_and_registry_hashes_cannot_be_substituted(self):
        for name in ("catalog_sha256", "source_registry_sha256"):
            feed = deepcopy(self.pipeline.feed); feed[name] = "f" * 64
            self.both_reject(feed)

    def test_adapter_metadata_and_public_json_reject_duplicate_keys_at_any_depth(self):
        for raw in (b'{"x":1,"x":2}', b'{"nested":{"x":1,"x":2}}'):
            with self.assertRaisesRegex(ValueError, "DUPLICATE_JSON_KEY"):
                public.strict_json(raw)
            reference = self.model.put_bytes("duplicate-" + sha(raw) + ".json", raw)
            with self.assertRaisesRegex(ValueError, "DUPLICATE_JSON_KEY_FORBIDDEN"):
                adapter._metadata(self.model.session, reference)



class BridgeRetentionTests(_SyntheticPublicFixture):
    def test_explicit_web_namespace_and_current_board_identity_are_required(self):
        result=self.node();self.assertTrue(result["ok"],result)
        self.assertEqual(result["point"],dict(value=2.,mean=3.,frozen=False))
        row=self.pipeline.feed["rows"][0]
        for field,value in [("team","OTHER"),("opp","OTHER"),("pos","WR"),("game_id",row["game_id"]),("id",row["player_id"])]:
            player=dict(game_id=row["website_game_id"],id=row["sleeper_id"],team=row["team"],opp=row["opponent"],pos=row["position"])
            player[field]=value
            self.assertIsNone(self.node(player=player)["point"])
        for board in [dict(season=2098,week=8),dict(season=2099,week=9)]:
            self.assertIsNone(self.node(board=board)["point"])

    def test_original_canonical_and_website_duplicates_are_rejected(self):
        for field,value in [("sleeper_id","102"),("player_id","fictional-other-gsis")]:
            feed=deepcopy(self.pipeline.feed);row=deepcopy(feed["rows"][0]);row[field]=value;feed["rows"].append(row)
            with self.assertRaisesRegex(ValueError,"DUPLICATE_CANONICAL_OR_WEBSITE"):
                public.validate_feed(feed)
            self.assertFalse(self.node(feed)["ok"])

    def test_current_board_game_and_exact_kickoff_must_match_frozen_identity(self):
        row=self.pipeline.feed["rows"][0]
        game=dict(id=row["website_game_id"],kickoff=row["kickoff_utc"],home=row["team"],away=row["opponent"])
        board=dict(season=row["season"],week=row["week"],games=[game])
        self.assertIsNotNone(self.node(board=board)["point"])
        variants=[dict(season=row["season"],week=row["week"]),dict(board,games=[]),dict(board,games=[game,game])]
        for field,value in [("id","OTHER"),("kickoff","2099-10-31T05:00:00Z"),
                ("kickoff","2099-10-31T03:00:00.000001Z"),("kickoff","invalid"),
                ("home","OTHER"),("away",row["team"])]:
            variants.append(dict(board,games=[dict(game,**{field:value})]))
        for wrong in variants:
            self.assertIsNone(self.node(board=wrong)["point"],wrong)
        numeric=dict(game,id=int(game["id"]))
        self.assertIsNotNone(self.node(board=dict(board,games=[numeric]))["point"])

    def test_candidate_digest_preserves_exact_adapter_ascii_domain(self):
        value={"identity":"Fictional \u00e9", "value":3.0}
        self.assertEqual(public.candidate_digest(value),adapter._digest(value))
        self.assertNotEqual(public.candidate_digest(value),public.digest(value))

    def test_closed_v2_rejects_v1_nonfinite_typed_and_changed_mean_capture(self):
        for key,value in [("selected_projection","2"),("expected_mean",True),
                ("forecast_product","point_legacy"),("prediction_functional","expected_mean")]:
            feed=deepcopy(self.pipeline.feed);feed["rows"][0][key]=value
            with self.assertRaises(ValueError):public.validate_feed(feed)
            self.assertFalse(self.node(feed)["ok"])
        feed=deepcopy(self.pipeline.feed);feed["schema_version"]="weekly-derived-selected-feed-v1"
        with self.assertRaises(ValueError):public.validate_feed(feed)
        self.assertFalse(self.node(feed)["ok"])
        feed=deepcopy(self.pipeline.feed);feed["rows"][0]["expected_mean"]=float("inf")
        with self.assertRaises(ValueError):public.validate_feed(feed)
        candidate=deepcopy(self.pipeline.candidate);candidate["separate_expected_mean"]=99.
        candidate.pop("candidate_sha256");candidate["candidate_sha256"]=public.candidate_digest(candidate)
        with self.assertRaisesRegex(ValueError,"CAPTURE_DOES_NOT_BIND_THIS_CANDIDATE"):
            self.pipeline.finalize(candidate,self.pipeline.receipt)

    def test_public_validate_and_capture_finalize_are_stdlib_only(self):
        p=self.pipeline
        script=r'''
import json,sys,importlib.abc
class BlockModels(importlib.abc.MetaPathFinder):
 def find_spec(self,name,path=None,target=None):
  if name.split('.')[0] in {'numpy','pandas','scipy','sklearn','catboost','joblib'} or (name.startswith('nfl_lab.') and name not in {'nfl_lab.stat_point_mae_public_v2_2','nfl_lab.next_checkpoint_median_policy_v2_view'}):
   raise AssertionError('MODEL_IMPORT_BLOCKED:'+name)
sys.meta_path.insert(0,BlockModels());sys.path.insert(0,sys.argv[1])
from nfl_lab import stat_point_mae_public_v2_2 as wire
x=json.load(sys.stdin)
expected_registry=wire.canonical(x['registry']);expected_catalog=wire.canonical(x['catalog']);expected_receipt=wire.canonical(x['receipt'])
def verify_registry(kind,body):
 assert kind=='SOURCE_REGISTRY' and body==expected_registry
def verify_catalog(kind,body):
 assert kind=='CATALOG' and body==expected_catalog
registry=wire.admit_registry(x['registry'],verify_owner_registry=verify_registry)
catalog=wire.admit_catalog(x['catalog'],registry,verify_owner_catalog=verify_catalog)
def verify_capture(body,candidate_sha,catalog_sha,registry_sha):
 assert body==expected_receipt and candidate_sha==x['candidate']['candidate_sha256'] and catalog_sha==catalog.sha256 and registry_sha==registry.sha256
capture=wire.finalize_capture(x['candidate'],x['receipt'],catalog,registry,verify_owner_capture=verify_capture)
wire.validate_feed(x['feed']);assert capture.document==x['feed']['rows'][0]
assert not any(k.split('.')[0] in {'numpy','pandas','scipy','sklearn','catboost','joblib'} for k in sys.modules)
assert {k for k in sys.modules if k=='nfl_lab' or k.startswith('nfl_lab.')} == {'nfl_lab','nfl_lab.stat_point_mae_public_v2_2','nfl_lab.next_checkpoint_median_policy_v2_view'}
print('stdlib-only validation and capture finalization')
'''
        result=subprocess.run([sys.executable,"-I","-S","-B","-c",script,str(SOURCE)],
            input=json.dumps(dict(registry=p.registry_doc,catalog=p.catalog_doc,receipt=p.receipt,candidate=p.candidate,feed=p.feed)),
            text=True,capture_output=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn("stdlib-only",result.stdout)

    def test_predeadline_frozen_capture_can_republish_after_kickoff(self):
        p=self.pipeline
        def verified_retained_export(body,catalog_sha,registry_sha):
            feed=public.strict_json(body);row=deepcopy(feed["rows"][0]);self.assertTrue(row.pop("retained_capture"))
            original=deepcopy(p.capture.document);original.pop("retained_capture")
            self.assertEqual(row,original)
            self.assertEqual((catalog_sha,registry_sha),(p.catalog.sha256,p.registry.sha256))
        feed=public.export_feed([p.capture],p.catalog,p.registry,created_at="2099-10-31T04:00:00Z",
            owner_export_receipt_sha256=sha(b"fictional-retained-export"),verify_owner_export=verified_retained_export)
        result=self.node(feed,now="2099-10-31T04:05:00Z")
        self.assertTrue(result["ok"],result);self.assertTrue(result["point"]["frozen"])
        self.assertIn("Frozen Median fallback",result["card"])
        for field,value in [("issued_at","2099-10-31T04:00:00Z"),("persistence_completed_at","2099-10-31T03:00:00Z")]:
            wrong=deepcopy(feed);wrong["rows"][0][field]=value
            with self.assertRaises(ValueError):public.validate_feed(wrong)
            self.assertFalse(self.node(wrong)["ok"])

    def test_capture_owner_verifies_explicit_bridge_hash_and_mapping(self):
        p=self.pipeline;receipt=deepcopy(p.receipt);receipt["sleeper_id"]="999"
        with self.assertRaisesRegex(ValueError,"INDEPENDENT_CAPTURE_READBACK_REJECTED"):
            p.finalize(p.candidate,receipt)


if __name__ == "__main__":
    unittest.main()
