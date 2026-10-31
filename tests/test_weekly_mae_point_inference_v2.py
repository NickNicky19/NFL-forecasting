"""Synthetic artifacts with actual installed legacy/MAE prepare and prediction.

No NFL artifact, provider, fitting, native qualification or actual owner grant.
The small LeafCDF shell and independent exact-byte owner verifier are fixtures.
"""
from copy import deepcopy
from dataclasses import fields
from datetime import timedelta
import hashlib
import json
from pathlib import Path
import pickle
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from scipy import sparse
from nfl_lab import weekly_mae_point_inference_v2_1 as mae
from nfl_lab import weekly_future_inference as legacy
from nfl_lab.cdf_engine import LeafCDFModel, SupportPrior


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


class FictionalStorage:
    fictional_test_storage = True

    def write_bytes(self, path, body):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        path.chmod(0o444)


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
                 rb_prior_q=.75, late_fit=False):
        self.root, self.storage = Path(directory), FictionalStorage()
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
        self.contract = dict(source_policy_sha256="a" * 64, feature_builder_sha256="b" * 64,
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


class MaePointInferenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.fixture = SyntheticPreparedLeaf(self.temp.name)

    def tearDown(self):
        self.fixture.close()
        self.temp.cleanup()

    def test_real_prepared_session_legacy_mean_bits_and_complete_role_positions(self):
        f = self.fixture
        fixed_clock = lambda: legacy.utc("2099-10-31T00:08:00Z")
        expected = [row for chunk in f.session.predict_chunks(f.artifact["sha256"], f.frame,
            context=f.context, clock=fixed_clock, batch_size=2) for row in chunk]
        rows = f.predict(batch_size=2, clock=fixed_clock)
        self.assertEqual([r["player_id"] for r in rows], f.frame.player_id.tolist())
        self.assertEqual([r["query_row_ordinal"] for r in rows], [0, 1, 2, 3])
        for old, new in zip(expected, rows):
            self.assertEqual(new["original_forecast"], old)
            self.assertEqual(np.asarray([new["separate_expected_mean"]], dtype="<f8").tobytes(),
                             np.asarray([old["forecast_value"]], dtype="<f8").tobytes())
            self.assertLess(new["functional_proof"]["cdf_below"], .5)
            self.assertGreaterEqual(new["functional_proof"]["cdf_at"], .5)
            self.assertFalse(new["public_export_authorized"])
        self.assertEqual(rows[2]["forecast_value"], 2.)
        self.assertEqual(rows[2]["separate_expected_mean"], 3.)
        self.assertEqual(rows[1]["forecast_value"], 0.)
        self.assertEqual(rows[1]["functional_proof"]["cdf_at"], .5)
        self.assertEqual([r["public_scope_eligible"] for r in rows], [True, False, True, False])
        self.assertEqual([r["operational_eligible"] for r in rows], [True, False, True, False])
        self.assertEqual(rows[0]["information_cutoff_utc"], "2099-10-31T00:05:00+00:00")
        self.assertNotEqual(rows[0]["information_cutoff_utc"], rows[0]["issue_deadline_utc"])
        self.assertTrue(any(r["phase"] == "CURRENT_SNAPSHOT" for r in f.admission_requests))

    def test_full_support_prior_median_can_exceed_empirical_max(self):
        with tempfile.TemporaryDirectory(dir=Path(self.temp.name)) as directory:
            f = SyntheticPreparedLeaf(directory, rb_prior_q=.99)
            try:
                rows = f.predict()
                self.assertEqual(rows[2]["forecast_value"], 68.)
                self.assertGreater(rows[2]["forecast_value"], float(f.model.support.max()))
                self.assertGreater(rows[2]["separate_expected_mean"], rows[2]["forecast_value"])
            finally:
                f.close()

    def test_negative_signed_yards_remain_signed_and_separate_mean(self):
        with tempfile.TemporaryDirectory(dir=Path(self.temp.name)) as directory:
            f = SyntheticPreparedLeaf(directory, target="rush_yd", support="signed_integer")
            try:
                rows = f.predict()
                self.assertLess(rows[0]["forecast_value"], 0)
                self.assertNotEqual(rows[0]["forecast_value"], rows[0]["separate_expected_mean"])
                for row in rows:
                    self.assertEqual(row["original_forecast"]["forecast_value"], row["forecast_value"])
            finally:
                f.close()

    def test_missing_prior_preserves_all_abstentions(self):
        with tempfile.TemporaryDirectory(dir=Path(self.temp.name)) as directory:
            f = SyntheticPreparedLeaf(directory, no_prior=True)
            try:
                rows = f.predict()
                self.assertEqual(len(rows), len(f.frame))
                self.assertTrue(all(r["forecast_value"] is None and r["functional_proof"] is None
                                    and not r["operational_eligible"] for r in rows))
            finally:
                f.close()

    def test_json_profile_and_self_asserted_approval_do_not_create_capability(self):
        f = self.fixture
        with self.assertRaisesRegex(ValueError, "OWNER_ADMISSION_CAPABILITY"):
            list(mae.predict_point_chunks(f.session, f.doc, f.frame, context=f.context,
                source_receipt=f.source_ref, clock=Clock()))
        with self.assertRaisesRegex(ValueError, "OWNER_VERIFIER"):
            mae.bind_profile(f.session, f.doc, verify_owner_admission=True)
        with self.assertRaisesRegex(ValueError, "INDEPENDENT_OWNER_ADMISSION"):
            mae.bind_profile(f.session, f.doc, verify_owner_admission=lambda *_: True)
        with self.assertRaisesRegex(ValueError, "MUST_NOT_BE_SERIALIZED"):
            pickle.dumps(f.profile)

    def test_owner_rejects_other_owned_source_before_any_legacy_prediction(self):
        f = self.fixture
        source = json.loads(Path(f.source_ref["path"]).read_bytes())
        other = f.put("other-owned-source.json", dict(source, arbitrary="same-looking-other-snapshot"))
        with patch.object(legacy.FutureInferenceSession, "predict_chunks", side_effect=AssertionError("PREDICTION_REACHED")):
            with self.assertRaisesRegex(ValueError, "OWNER_SNAPSHOT_NOT_ADMITTED"):
                list(mae.predict_point_chunks(f.session, f.profile, f.frame, context=f.context,
                    source_receipt=other, clock=Clock()))

    def test_same_prepared_model_object_and_unchanged_profile_required(self):
        f = self.fixture
        manifest, model = f.session.models[f.artifact["sha256"]]
        f.session.models[f.artifact["sha256"]] = (manifest, deepcopy(model))
        try:
            with self.assertRaisesRegex(ValueError, "ADMITTED_MODEL_OR_ADAPTER_CHANGED"):
                f.predict()
        finally:
            f.session.models[f.artifact["sha256"]] = (manifest, model)
        changed = f.profile.document
        changed["public_roles"] = ["FB"]
        changed["procedure_version"] = mae.view_procedure(changed)
        with self.assertRaisesRegex(ValueError, "PUBLIC_ROLE_SUBSET"):
            mae.bind_profile(f.session, changed, verify_owner_admission=f.verify_owner)

    def test_future_feature_clock_rejected_before_legacy_prediction(self):
        f = self.fixture
        f.frame.loc[91, "feature_max_source_available_utc"] = "2099-10-31T00:05:01Z"
        f.rebind_features()
        with self.assertRaisesRegex(ValueError, "FEATURE_AVAILABLE_AFTER_INFORMATION_CUTOFF"):
            f.predict()

    def test_naive_cutoff_rejected_instead_of_assumed_timezone(self):
        f = self.fixture
        f.frame.loc[91, "cutoff_utc"] = "2099-10-31T01:00:00"
        f.rebind_features()
        with self.assertRaisesRegex(ValueError, "AWARE_CLOCK"):
            f.predict()

    def test_unknown_warm_clock_reaches_unchanged_legacy_rejection(self):
        f = self.fixture
        f.frame.loc[91, "feature_max_source_available_utc"] = None
        f.rebind_features()
        with self.assertRaisesRegex(ValueError, "query source availability must precede cutoff"):
            f.predict()

    def test_legacy_source_and_fit_checks_are_still_executed(self):
        f = self.fixture
        context = deepcopy(f.context)
        context["source_contract"] = dict(context["source_contract"], changed=True)
        with self.assertRaisesRegex(ValueError, "FEATURE_QUERY_SOURCE_BINDING"):
            list(mae.predict_point_chunks(f.session, f.profile, f.frame, context=context,
                source_receipt=f.source_ref, clock=Clock()))
        # Use a fresh actual synthetic export with late fit metadata so unchanged
        # legacy operational prediction, not a fake replacement, rejects it.
        with tempfile.TemporaryDirectory(dir=Path(self.temp.name)) as directory:
            late = SyntheticPreparedLeaf(directory, late_fit=True)
            try:
                with self.assertRaisesRegex(ValueError, "fit/source availability is after actual issuance"):
                    late.predict()
            finally:
                late.close()

    def test_extraction_finishing_at_deadline_emits_no_prefix(self):
        f = self.fixture
        clock = Clock()
        original = mae._law_values
        def overrun(*args, **kwargs):
            result = original(*args, **kwargs)
            clock.value = legacy.utc(f.context["cutoff_utc"])
            return result
        with patch.object(mae, "_law_values", overrun):
            with self.assertRaisesRegex(ValueError, "POINT_ISSUANCE_MUST_PRECEDE_DEADLINE"):
                next(mae.predict_point_chunks(f.session, f.profile, f.frame, context=f.context,
                    source_receipt=f.source_ref, clock=clock, batch_size=1))

    def test_second_traversal_missing_position_cannot_emit_partial_frame(self):
        f = self.fixture
        original = LeafCDFModel.predict_batches
        calls = 0
        def incomplete(model, frame, **kwargs):
            nonlocal calls
            calls += 1
            for positions, law, reasons in original(model, frame, **kwargs):
                if calls == 2:
                    return
                yield positions, law, reasons
        with patch.object(LeafCDFModel, "predict_batches", incomplete):
            with self.assertRaisesRegex(ValueError, "INCOMPLETE_LAW_POPULATION"):
                next(mae.predict_point_chunks(f.session, f.profile, f.frame, context=f.context,
                    source_receipt=f.source_ref, clock=Clock()))

    def test_malformed_identity_cannot_qualify(self):
        f = self.fixture
        f.frame.loc[91, "player_id"] = "nan "
        f.rebind_features()
        with self.assertRaisesRegex(ValueError, "CANONICAL_QUERY_IDENTITY"):
            f.predict()

    def test_duplicate_query_identity_cannot_qualify(self):
        f = self.fixture
        f.frame.loc[13, "player_id"] = f.frame.loc[91, "player_id"]
        with self.assertRaisesRegex(ValueError, "identities must be unique"):
            f.predict()

    def test_response_like_subclass_cannot_be_disguised_as_core_leaf(self):
        f = self.fixture
        class DifferentLeafRecipe(LeafCDFModel):
            pass
        other = DifferentLeafRecipe(**{field.name: deepcopy(getattr(f.model, field.name))
                                       for field in fields(LeafCDFModel)})
        f.session.models[f.artifact["sha256"]] = (f.manifest, other)
        try:
            with self.assertRaisesRegex(ValueError, "EXACT_CORE_NUMERIC_LEAF_MODEL_REQUIRED"):
                f.predict()
        finally:
            f.session.models[f.artifact["sha256"]] = (f.manifest, f.model)

    def test_second_law_traversal_changed_mean_bits_rejected(self):
        f = self.fixture
        original = LeafCDFModel.predict_batches
        calls = 0
        def changed(model, frame, **kwargs):
            nonlocal calls
            calls += 1
            for positions, law, reasons in original(model, frame, **kwargs):
                if calls == 2 and not any(reasons):
                    law = legacy.cdf.MixtureBatch(law.support, np.flip(law.weights, axis=1),
                        law.prior, prior_weight=law.b)
                yield positions, law, reasons
        with patch.object(LeafCDFModel, "predict_batches", changed):
            with self.assertRaisesRegex(ValueError, "LEGACY_FUNCTIONAL_BITS_CHANGED"):
                f.predict()

    def test_duplicate_law_position_cannot_emit_partial_frame(self):
        f = self.fixture
        original = LeafCDFModel.predict_batches
        calls = 0
        def duplicated(model, frame, **kwargs):
            nonlocal calls
            calls += 1
            for positions, law, reasons in original(model, frame, **kwargs):
                yield positions, law, reasons
                if calls == 2:
                    yield positions, law, reasons
        with patch.object(LeafCDFModel, "predict_batches", duplicated):
            with self.assertRaisesRegex(ValueError, "DUPLICATE_OR_INVALID_LAW_POSITION"):
                f.predict()

    def test_owned_source_receipt_clock_after_asof_is_not_repaired(self):
        f = self.fixture
        source = json.loads(Path(f.source_ref["path"]).read_bytes())
        source["manifest"]["source_receipts"]["fictional"]["retrieved_utc"] = "2099-10-31T00:05:01Z"
        f.source_ref = f.put("source-after-information-cutoff.json", source)
        with self.assertRaisesRegex(ValueError, "SOURCE_RECEIPT_AFTER_INFORMATION_CUTOFF"):
            f.predict()

    def test_outcome_columns_do_not_enter_law_or_query_binding(self):
        f = self.fixture
        expected = f.predict()
        f.frame["rush_att"] = [123456, -999, np.inf, np.nan]
        f.frame["participation_state"] = ["played", "DNP", "unknown", "not_a_real_state"]
        changed = f.predict()
        self.assertEqual([r["candidate_sha256"] for r in expected],
                         [r["candidate_sha256"] for r in changed])


if __name__ == "__main__":
    unittest.main()
