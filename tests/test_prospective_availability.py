"""Entirely fictional metadata/value fixtures; not NFL evidence."""
from copy import deepcopy
from datetime import timedelta
import unittest

from nfl_lab.prospective_availability import (
    ContractError, HISTORICAL_LANE, LANE, VERSION,
    qualify_forecast_completion, qualify_history_capture, validate_model_contract,
)
from nfl_lab.state import digest, utc


def envelope(document):
    return {"document": document, "sha256": digest(document)}


def fixture():
    expected = {k: str(i) * 64 for i, k in enumerate(("availability_policy_sha256", "source_policy_sha256",
                "qualification_policy_sha256", "feature_contract_sha256"), start=1)}
    expected.update(statistics_source_id="fictional-official-action-credits", finality_source_id="fictional-independent-final-status")
    binding = {**{k: v for k, v in expected.items() if k.endswith("sha256")},
               "schema_version": VERSION + "-model-contract", "model_id": "fictional-new-version",
               "model_artifact_sha256": "5" * 64, "training_manifest_sha256": "6" * 64,
               "prospective_registration_sha256": "7" * 64,
               "training_availability_lane": HISTORICAL_LANE, "inference_availability_lane": LANE}
    prior = {"player_id": "fictional-player", "game_id": "fictional-prior-game", "season": 2026,
             "week": 4, "season_type": "REG", "period": "full_game_including_overtime",
             "team": "FICTIONAL_A", "opponent": "FICTIONAL_B", "kickoff_utc": "2026-10-01T17:00:00Z"}
    row = {**prior, "identity_state": "qualified", "conflict_state": "clear", "participation_state": "played",
           "primitives": {"rush_att": {"support": "explicit_value", "value": 0},
                          "rush_yd": {"support": "explicit_value", "value": -2}}}
    def capture(source, hour):
        return {"schema_version": "local-source-capture-success-v1", "source_id": source,
                "source_policy_sha256": expected["source_policy_sha256"], "body_sha256": "8" * 64,
                "original_receipt_sha256": "9" * 64, "status": "success", "upstream_publication_utc": None,
                "capture_started_utc": f"2026-10-01T{hour}:00:00Z", "body_completed_utc": f"2026-10-01T{hour}:01:00Z",
                "persist_started_utc": f"2026-10-01T{hour}:02:00Z", "persist_completed_utc": f"2026-10-01T{hour}:03:00Z"}
    status = envelope(capture(expected["finality_source_id"], "20"))
    source = envelope(capture(expected["statistics_source_id"], "21"))
    finality = envelope({"schema_version": "completed-game-qualification-v1", "completed": True,
                         "capture_sha256": status["sha256"], "game_identity": {k: v for k, v in prior.items() if k != "player_id"},
                         "parser_sha256": "a" * 64})
    version = {"schema_version": VERSION + "-history-version", "revision": "original", "supersedes_version_sha256": None,
               "qualified_row": envelope(row), "source_capture": source, "finality_capture": status, "finality": finality}
    version["qualification"] = envelope({"schema_version": "qualified-history-row-v1",
                "policy_sha256": expected["qualification_policy_sha256"], "qualified_row_sha256": version["qualified_row"]["sha256"],
                "source_capture_sha256": source["sha256"], "finality_sha256": finality["sha256"],
                "qualified_at_utc": "2026-10-01T21:04:00Z", "persist_completed_utc": "2026-10-01T21:05:00Z"})
    query = {**prior, "game_id": "fictional-future-game", "week": 5, "kickoff_utc": "2026-10-08T17:00:00Z",
             "cutoff_utc": "2026-10-08T16:00:00Z", "calculation_started_utc": "2026-10-08T15:00:00Z",
             "model_id": binding["model_id"], "required_primitives": ["rush_att", "rush_yd"],
             "requested_targets": ["rush_att", "rush_yd"]}
    return version, query, binding, expected


def rebind(version):
    """Only fixture repair; no real source/qualification claim."""
    for name in ("qualified_row", "source_capture", "finality_capture"):
        version[name] = envelope(version[name]["document"])
    finality = version["finality"]["document"]
    finality["capture_sha256"] = version["finality_capture"]["sha256"]
    version["finality"] = envelope(finality)
    q = version["qualification"]["document"]
    q.update(qualified_row_sha256=version["qualified_row"]["sha256"],
             source_capture_sha256=version["source_capture"]["sha256"], finality_sha256=version["finality"]["sha256"])
    version["qualification"] = envelope(q)


class ProspectiveAvailabilityTests(unittest.TestCase):
    def setUp(self):
        self.v, self.q, self.b, self.e = fixture()

    def qualify(self, parent=None):
        return qualify_history_capture(self.v, query=self.q, model_binding=self.b, expected=self.e, parent_version=parent)

    def test_01_recent_completed_capture_without_rewriting_seven_day_lane(self):
        decision = self.qualify()
        self.assertEqual(decision["state"], "ELIGIBLE")
        self.assertEqual(decision["completion_status"], "PENDING_ACTUAL_PERSISTENCE")
        self.assertGreater(utc(self.v["qualified_row"]["document"]["kickoff_utc"]) + timedelta(days=7), utc(self.q["cutoff_utc"]))
        self.assertIsNone(decision["upstream_publication_utc"])

    def test_02_mixed_lane_requires_explicit_new_model_contract(self):
        self.assertEqual(validate_model_contract(self.b, expected=self.e)["training_lane"], HISTORICAL_LANE)
        del self.b["schema_version"]
        with self.assertRaises(ContractError): self.qualify()

    def test_03_model_source_feature_and_query_versions_cannot_alias(self):
        for field in ("source_policy_sha256", "feature_contract_sha256", "model_id"):
            with self.subTest(field=field):
                b = deepcopy(self.b); b[field] = "wrong"
                with self.assertRaises(ContractError):
                    qualify_history_capture(self.v, query=self.q, model_binding=b, expected=self.e)
        for targets in (None, [], ["rush_att", "rush_att"], ["unknown-category"]):
            with self.subTest(targets=targets):
                query = {**self.q, "requested_targets": targets}
                with self.assertRaises(ContractError):
                    qualify_history_capture(self.v, query=query, model_binding=self.b, expected=self.e)

    def test_04_retrieval_clock_is_not_durable_success(self):
        capture = self.v["source_capture"]["document"]
        capture["retrieved_utc"] = capture.pop("persist_completed_utc")
        rebind(self.v)
        with self.assertRaises(ContractError): self.qualify()

    def test_05_capture_after_cutoff_or_calculation_is_rejected(self):
        self.q["calculation_started_utc"] = "2026-10-01T21:02:00Z"
        with self.assertRaises(ContractError): self.qualify()

    def test_06_cutoff_must_strictly_precede_future_kickoff(self):
        self.q["cutoff_utc"] = self.q["kickoff_utc"]
        with self.assertRaises(ContractError): self.qualify()

    def test_07_completed_flag_and_exact_game_identity_required(self):
        same_game_query = {**self.q, "game_id": self.v["qualified_row"]["document"]["game_id"]}
        with self.assertRaisesRegex(ContractError, "TARGET_GAME_IN_HISTORY"):
            qualify_history_capture(self.v, query=same_game_query, model_binding=self.b, expected=self.e)
        original = deepcopy(self.v)
        for field in ("completed", "game_identity"):
            with self.subTest(field=field):
                self.v = deepcopy(original)
                self.v["finality"]["document"][field] = False if field == "completed" else {}
                rebind(self.v)
                with self.assertRaises(ContractError): self.qualify()

    def test_08_pregame_cache_cannot_inherit_later_finality(self):
        self.v["source_capture"]["document"]["capture_started_utc"] = "2026-10-01T19:00:00Z"
        rebind(self.v)
        with self.assertRaises(ContractError): self.qualify()

    def test_09_document_hash_mismatch_rejected(self):
        self.v["qualified_row"]["document"]["primitives"]["rush_yd"]["value"] = -3
        with self.assertRaises(ContractError): self.qualify()

    def test_10_qualification_payload_and_policy_are_bound(self):
        for field in ("policy_sha256", "qualified_row_sha256"):
            original = deepcopy(self.v)
            with self.subTest(field=field):
                self.v["qualification"]["document"][field] = "b" * 64
                self.v["qualification"] = envelope(self.v["qualification"]["document"])
                with self.assertRaises(ContractError): self.qualify()
            self.v = original

    def test_11_DNP_unknown_and_played_zero_stay_distinct(self):
        self.assertEqual(self.qualify()["participation_state"], "played")
        for state, reason in (("DNP", "DNP"), ("unknown", "UNKNOWN_PARTICIPATION")):
            self.v["qualified_row"]["document"]["participation_state"] = state
            self.v["qualified_row"]["document"]["primitives"] = {}
            rebind(self.v)
            result = self.qualify()
            self.assertEqual((result["state"], result["reason"]), ("UNAVAILABLE", reason))

    def test_12_missing_primitive_is_never_zero_or_older_game(self):
        del self.v["qualified_row"]["document"]["primitives"]["rush_att"]
        rebind(self.v)
        with self.assertRaises(ContractError): self.qualify()

    def test_13_count_support_and_signed_yards(self):
        self.assertEqual(self.qualify()["state"], "ELIGIBLE")
        for invalid in (-1, .5, True, float("inf")):
            with self.subTest(invalid=invalid):
                version = deepcopy(self.v)
                version["qualified_row"]["document"]["primitives"]["rush_att"]["value"] = invalid
                if invalid == float("inf"):
                    with self.assertRaises(ValueError): rebind(version)
                else:
                    rebind(version)
                    with self.assertRaises(ContractError):
                        qualify_history_capture(version, query=self.q, model_binding=self.b, expected=self.e)

    def test_14_sparse_zero_needs_its_own_semantics_proof(self):
        self.v["qualified_row"]["document"]["primitives"]["rush_att"]["support"] = "qualified_sparse_zero"
        rebind(self.v)
        with self.assertRaises(ContractError): self.qualify()
        self.v["qualification"]["document"]["zero_semantics_sha256"] = "c" * 64
        rebind(self.v)
        self.assertEqual(self.qualify()["state"], "ELIGIBLE")

    def test_15_completion_count_cannot_exceed_attempts(self):
        self.q["required_primitives"] = ["pass_cmp", "pass_att"]
        self.v["qualified_row"]["document"]["primitives"].update(
            pass_att={"support": "explicit_value", "value": 2}, pass_cmp={"support": "explicit_value", "value": 3})
        rebind(self.v)
        with self.assertRaises(ContractError): self.qualify()

    def test_16_correction_appends_bound_parent_without_mutation(self):
        parent = deepcopy(self.v); parent_sha = digest(parent)
        self.v.update(revision="append_correction", supersedes_version_sha256=parent_sha)
        for key in ("capture_started_utc", "body_completed_utc", "persist_started_utc", "persist_completed_utc"):
            self.v["source_capture"]["document"][key] = self.v["source_capture"]["document"][key].replace("T21:", "T22:")
        for key in ("qualified_at_utc", "persist_completed_utc"):
            self.v["qualification"]["document"][key] = self.v["qualification"]["document"][key].replace("T21:", "T22:")
        rebind(self.v)
        self.assertEqual(self.qualify(parent)["state"], "ELIGIBLE")
        self.assertEqual(digest(parent), parent_sha)
        with self.assertRaises(ContractError): self.qualify()

    def completed_fixture(self):
        decision = self.qualify()
        calc = envelope({"schema_version": VERSION + "-calculation", "availability_sha256": digest(decision),
                         "started_at": self.q["calculation_started_utc"], "completed_at": "2026-10-08T15:01:00Z"})
        row = {k: self.q[k] for k in ("player_id", "game_id", "season", "week", "season_type", "period", "team", "opponent", "kickoff_utc", "model_id")}
        row.update(availability_sha256=digest(decision), calculation_receipt_sha256=calc["sha256"], issued_at="2026-10-08T15:02:00Z")
        rows = [{**row, "target": target} for target in self.q["requested_targets"]]
        batch = envelope({"schema_version": "lab-forecast-batch-v1", "persist_started_at": "2026-10-08T15:03:00Z", "rows": rows})
        persistence = envelope({"batch": batch["sha256"], "completed_at": "2026-10-08T15:04:00Z", "late_games": []})
        return decision, calc, batch, persistence

    def test_17_actual_postflight_uses_existing_immutable_batch_receipts(self):
        d, c, b, p = self.completed_fixture()
        unrelated = {**b["document"]["rows"][0], "target": "rec", "availability_sha256": "d" * 64,
                     "calculation_receipt_sha256": "e" * 64}
        b["document"]["rows"].append(unrelated)
        b = envelope(b["document"]); p["document"]["batch"] = b["sha256"]; p = envelope(p["document"])
        result = qualify_forecast_completion(d, calculation=c, batch=b, persistence=p)
        self.assertEqual(result["state"], "LOCAL_COMPLETION_QUALIFIED")
        self.assertEqual(result["qualified_targets"], ["rush_att", "rush_yd"])

    def test_18_late_or_mismatched_completion_never_becomes_success(self):
        for change in ("late", "batch", "binding", "missing-target", "duplicate-target", "wrong-target"):
            with self.subTest(change=change):
                d, c, b, p = self.completed_fixture()
                if change == "late": p["document"]["completed_at"] = self.q["kickoff_utc"]
                if change == "batch": p["document"]["batch"] = "d" * 64
                if change in ("binding", "missing-target", "duplicate-target", "wrong-target"):
                    if change == "binding": b["document"]["rows"][0]["availability_sha256"] = "d" * 64
                    if change == "missing-target": b["document"]["rows"].pop()
                    if change == "duplicate-target": b["document"]["rows"].append(deepcopy(b["document"]["rows"][0]))
                    if change == "wrong-target": b["document"]["rows"][-1]["target"] = "rec"
                    b = envelope(b["document"]); p["document"]["batch"] = b["sha256"]
                p = envelope(p["document"])
                with self.assertRaises(ContractError): qualify_forecast_completion(d, calculation=c, batch=b, persistence=p)
