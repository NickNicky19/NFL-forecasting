"""Fictional choice/outcome metadata only; no NFL bodies, fits, loads or HTTP."""
from copy import deepcopy
from datetime import timedelta
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from nfl_lab import audit_weekly_epoch_v1 as epoch
from nfl_lab import weekly_adaptive as selector, weekly_generic_producer as generic
from nfl_lab import gha_private_checkpoint as checkpoint
from nfl_lab.state import canonical, digest, utc

REGISTERED = utc("2026-10-25T10:00:00Z")
CONTINUED = REGISTERED + timedelta(minutes=3)


def h(value):
    return digest(value)


def fixture(*, active_reference=True):
    replay = dict(schema_version="audit-count-checkpoint-v1-replay-catalog", repository="NickNicky19/NFL-forecasting",
        source_sha="a" * 40, run_id="12345", fits=0, model_pairs=18, scientific_qualification=False, public_release=False, slots=[])
    catalog = dict(schema_version=selector.VERSION, methods={}, categories={})
    for target, family, method in checkpoint.JOBS:
        count = method == "COUNT_A"
        replay["slots"].append(dict(target=target, family=family, method_id=method,
            procedure_version=h(["corrected", method]), model_sha256=h(["model", target, method]),
            manifest_sha256=h(["manifest", target, method]), transport_manifest_sha256=h(["transport", target, method]),
            warm_rows=2, warm_bits_identical=True, fallback_rows=2,
            fallback_oracle_applicable=count, fallback_oracle_passed=True if count else None))
        spec = catalog["methods"].setdefault(method, dict(procedure_version=h(["old", method]), model_versions=[],
            registered_at="2026-10-20T00:00:00Z", procedure_operational_eligible=True, procedure_replay_eligible=False))
        spec["model_versions"].append(h(["old-manifest", target, method]))
        support = "bernoulli" if target == "anytime_td" else "signed_integer" if target.endswith("_yd") else "count"
        product, metric = {"count": ("point_mean", "point_mse"), "signed_integer": ("point_median", "point_mae"),
            "bernoulli": ("binary_probability", "brier")}[support]
        category = catalog["categories"].setdefault(target, dict(state="READY", support=support, product=product,
            primary_metric=metric, reference_id="R0", shortlist=[], eligible_methods=["R0"]))
        category["shortlist"].append(method); category["eligible_methods"].append(method)
    catalog["methods"]["R0"] = dict(procedure_version=h("fictional-reference-procedure"), model_versions=[h("fictional-reference-model")]
        if active_reference else [], registered_at="2026-10-20T00:00:00Z", procedure_operational_eligible=active_reference,
        procedure_replay_eligible=False, role="reference")
    startup = {t: "LAB_CDF" for t in catalog["categories"]}
    startup.update(rush_att="COUNT_A", rec="COUNT_A", rec_yd="CATBOOST_MEDIUM", rush_rec_yd="CATBOOST_MEDIUM", anytime_td="TD_EQUAL_CDF_CAT")
    policy = dict(schema_version="weekly-provisional-live-policy-v1", categories=[dict(category=t, startup_method_id=m) for t, m in startup.items()],
        TD_EQUAL_CDF_CAT=dict(members={"LAB_CDF": .5, "CATBOOST_MEDIUM": .5}))
    schedule = [dict(season=2026, week=7, game_type="REG", game_id=name, kickoff_utc=kickoff)
        for name, kickoff in (("fictional-elapsed", "2026-10-23T00:15:00Z"), ("fictional-sunday", "2026-10-25T20:00:00Z"),
                             ("fictional-monday", "2026-10-26T20:00:00Z"))]
    slate = generic.prepare_slate(schedule, season=2026, week=7, now=utc("2026-10-22T12:00:00Z"),
        game_cutoffs={r["game_id"]: (utc(r["kickoff_utc"]) - timedelta(hours=1)).isoformat() for r in schedule})
    history = dict(schema_version=selector.VERSION, offers=[], forecasts=[], outcomes=[], decisions=[], weeks=[])
    choice = generic.freeze_choices(selector, history, catalog, policy, slate, actual_choice_at=utc("2026-10-22T12:00:00Z"))
    # This is a fictional losing-history archive, bound but never read for the
    # corrected epoch's policy scores. No old record is rewritten or dropped.
    old_history = canonical(dict(weeks=[dict(week=6, COUNT_A_loss=123456, LAB_CDF_loss=0)]))
    raw = (json.dumps(choice, sort_keys=True, separators=(",", ":")) + "\n").encode()
    completion = dict(schema_version=generic.VERSION + "-weekly-choice-completion",
        choice_binding=dict(path="/fictional/original/WEEKLY_CHOICE.json", bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()),
        persisted_completed_at="2026-10-22T12:01:00Z", original_predeadline_completion=None)
    return dict(raw=raw, completion=completion, slate=slate, catalog=catalog, policy=policy, replay=replay, schedule=schedule,
        old_history=old_history, history_binding=dict(bytes=len(old_history), sha256=hashlib.sha256(old_history).hexdigest()))


def prepare(f, **kwargs):
    return epoch.prepare_epoch(f["raw"], f["completion"], f["slate"], f["catalog"], f["policy"], f["replay"],
        history_binding=f["history_binding"], clock=lambda: REGISTERED, **kwargs)


def cas_receipt(scope, values, written, completed):
    """Fictional contract fixture; actual owned-CAS execution is tested below."""
    return dict(schema_version=epoch.VERSION + "-owned-cas-readback", scope=scope,
        owner_identity_sha256=h("fictional-CAS-owner"), owned_validation_sha256=h("fictional-local-ownership-check"),
        write_completed_at=written.isoformat(), readback_started_at=written.isoformat(), readback_completed_at=completed.isoformat(),
        documents=[dict(role=role, binding=dict(bytes=len(canonical(value)), sha256=hashlib.sha256(canonical(value)).hexdigest()),
            payload_sha256=digest(value)) for role, value in sorted(values.items())], remote_durability_qualified=False)


def artifact_proof(e, replay=None):
    return dict(scope="EFFECTIVE18_MODELS_ONLY", proof_sha256=h("fictional-qualified-effective18-model-restore-proof"),
        replay_catalog_sha256=digest(e.document["replay_catalog"] if replay is None else replay), model_pairs=18)


def registered(e):
    completion = dict(schema_version=epoch.VERSION + "-registration-completion", epoch_sha256=e.sha256,
        catalog_sha256=digest(e.document["catalog"]), selection_recipe_sha256=digest(e.document["selection_recipe"]),
        persisted_completed_at=(REGISTERED + timedelta(minutes=1)).isoformat(), owner_registration_sha256=h("fictional-owner-GO"),
        qualified_artifact_restore=artifact_proof(e), metadata_remote_durability_qualified=False,
        metadata_cas_readback=cas_receipt("EPOCH_METADATA", {"epoch": e.document}, REGISTERED + timedelta(seconds=10), REGISTERED + timedelta(minutes=1)),
        current_values_used=False, fits=0)
    return epoch.bind_registration(e, completion, now=REGISTERED + timedelta(minutes=2))


def continuation(f, r):
    cutoffs = {row["game_id"]: (utc(row["kickoff_utc"]) - timedelta(minutes=30)).isoformat()
        for row in f["schedule"] if utc(row["kickoff_utc"]) > CONTINUED}
    return epoch.continue_week(r, f["schedule"], cutoffs, clock=lambda: CONTINUED)


def next_slate(week, first):
    schedule = [dict(season=2026, week=week, game_type="REG", game_id="fictional-week-" + str(week), kickoff_utc=first)]
    return generic.prepare_slate(schedule, season=2026, week=week,
        game_cutoffs={schedule[0]["game_id"]: (utc(first) - timedelta(hours=1)).isoformat()}, now=utc(first) - timedelta(days=2))


def history(r, choices, *, pending=False):
    e = r.epoch
    bundle = dict(schema_version=selector.VERSION, offers=[], forecasts=[], outcomes=[], decisions=[], weeks=[])
    catalog = epoch.artifact_catalog(e)["catalog"]
    slots = {(s["target"], s["method_id"]): s for s in e.document["replay_catalog"]["slots"]}
    for index, chosen in enumerate(choices):
        selected = next(s for s in chosen.document["choice"]["selections"] if s["decision"]["category"] == "rush_att")
        decision = deepcopy(selected["decision"]); decision["correction_epoch_sha256"] = e.sha256
        week = decision["week"]
        kickoff = utc("2026-10-25T20:00:00Z") + timedelta(days=7 * index)
        cutoff = kickoff - timedelta(minutes=30)
        offer = dict(category="rush_att", season=2026, week=week, slate_id=decision["slate_id"], game_id="fictional-history-" + str(week),
            player_id="fictional-player", horizon="player_game", cutoff_utc=cutoff.isoformat(), kickoff_utc=kickoff.isoformat(),
            correction_epoch_sha256=e.sha256)
        offer["offered_id"] = selector.offered_id(offer)
        bundle["offers"].append(offer); bundle["decisions"].append(decision)
        for method, value in (("R0", 50), ("LAB_CDF", 10 if index == 0 else 20), ("COUNT_A", 20)):
            version = slots["rush_att", method]["manifest_sha256"] if method in epoch.FAMILIES else catalog["methods"][method]["model_versions"][0]
            issued = utc(decision["weekly_decision_cutoff_utc"]) + timedelta(minutes=2)
            bundle["forecasts"].append(dict(offer, method_id=method, procedure_version=catalog["methods"][method]["procedure_version"],
                model_version=version, product="point_mean", prediction_functional="expected_mean", forecast_value=value,
                evidence_lane="original_pregame", operational_eligible=True, reference_stream="live_R0" if method == "R0" else "candidate",
                issued_at=issued.isoformat(), source_capture_completed_at=(issued - timedelta(minutes=1)).isoformat(),
                training_cutoff_utc="2026-09-04T00:00:00Z", training_max_available_utc="2026-08-31T00:00:00Z",
                training_source_capture_completed_at="2026-09-01T00:00:00Z", training_started_at="2026-09-02T00:00:00Z",
                training_completed_at="2026-09-03T00:00:00Z"))
        available = kickoff + timedelta(days=1, hours=5)
        bundle["outcomes"].append(dict(offered_id=offer["offered_id"], revision=1, participation_state="played", actual=10,
            available_at=available.isoformat(), correction_epoch_sha256=e.sha256))
        bundle["weeks"].append(dict(category="rush_att", season=2026, week=week, slate_id=decision["slate_id"],
            completed_at=(kickoff + timedelta(hours=5)).isoformat(),
            grade_completed_at=(available + timedelta(hours=1, days=30 if pending else 0)).isoformat(),
            weekly_decision_cutoff_utc=decision["weekly_decision_cutoff_utc"], slate_first_kickoff_utc=decision["slate_first_kickoff_utc"],
            correction_epoch_sha256=e.sha256))
    return dict(schema_version=epoch.VERSION + "-history", epoch_sha256=e.sha256,
        legacy_history_binding=deepcopy(e.origin["history_binding"]), bundle=bundle)


class EpochChecks(unittest.TestCase):
    def setUp(self):
        self.f = fixture(); self.e = prepare(self.f); self.r = registered(self.e); self.c = continuation(self.f, self.r)

    def test_actual_new_clock_and_procedures_preserve_originals_and_old_api_stays_strict(self):
        self.assertEqual(self.e.document["registered_at_utc"], REGISTERED.isoformat())
        self.assertEqual(self.e.origin["choice_file"]["sha256"], hashlib.sha256(self.f["raw"]).hexdigest())
        self.assertEqual(self.e.document["original"]["history_binding"], self.f["history_binding"])
        self.assertEqual(self.e.document["selection_recipe"]["code_pins"], epoch.implementation_pins())
        for method in epoch.FAMILIES:
            self.assertNotEqual(self.e.document["catalog"]["methods"][method]["procedure_version"], self.f["catalog"]["methods"][method]["procedure_version"])
            self.assertEqual(self.e.document["catalog"]["methods"][method]["registered_at"], REGISTERED.isoformat())
        original = json.loads(self.f["raw"])
        generic.restore_choices(original, slate=self.f["slate"], catalog=self.f["catalog"], policy=self.f["policy"], selector=selector, now=CONTINUED)
        with self.assertRaisesRegex(ValueError, "procedure/catalog"):
            generic.restore_choices(original, slate=self.f["slate"], catalog=self.e.document["catalog"], policy=self.f["policy"], selector=selector, now=CONTINUED)
        self.assertFalse(self.e.document["old_procedure_losses_inherited"])
        self.assertFalse(self.e.document["scientific_qualification"])

    def test_exact_authenticated_original_hash_precedes_metadata_decode(self):
        with patch.object(epoch, "_decode", side_effect=AssertionError("must not decode before hash")):
            with self.assertRaisesRegex(epoch.EpochError, "ORIGINAL_DURABLE"):
                epoch.prepare_epoch(self.f["raw"] + b" ", self.f["completion"], self.f["slate"], self.f["catalog"], self.f["policy"], self.f["replay"],
                    history_binding=self.f["history_binding"], clock=lambda: REGISTERED)

    def test_restore_uses_original_effective_clock_without_new_registration(self):
        restored = epoch.restore_epoch(self.e.document, self.f["raw"], self.f["completion"], self.f["slate"], self.f["catalog"], self.f["policy"],
            history_binding=self.f["history_binding"], now=CONTINUED)
        self.assertEqual(restored.sha256, self.e.sha256)
        wrong = deepcopy(self.e.document); wrong["registered_at_utc"] = "2026-10-20T00:00:00Z"
        with self.assertRaises(epoch.EpochError):
            epoch.restore_epoch(wrong, self.f["raw"], self.f["completion"], self.f["slate"], self.f["catalog"], self.f["policy"],
                history_binding=self.f["history_binding"], now=CONTINUED)

    def test_replay_requires_all18_warm_bits_and_independent_count_oracle(self):
        for field, index in (("warm_bits_identical", 0), ("fallback_oracle_passed", 11)):
            changed = deepcopy(self.f); changed["replay"]["slots"][index][field] = False
            with self.subTest(field=field), self.assertRaisesRegex(epoch.EpochError, "EFFECTIVE18"):
                prepare(changed)

    def test_continuation_never_reselects_or_inherits_old_scores_and_keeps_td_weights(self):
        with patch.object(selector, "select", side_effect=AssertionError("no selection after original choice")):
            continued = continuation(self.f, self.r)
        self.assertEqual(epoch._signature(continued.document["choice"]["selections"]), self.e.origin["signature"])
        self.assertTrue(continued.document["slate"]["slate_contract"]["late_capture"])
        self.assertEqual(set(continued.document["slate"]["game_cutoffs"]), {"fictional-sunday", "fictional-monday"})
        td = next(s for s in continued.document["choice"]["selections"] if s["decision"]["category"] == "anytime_td")
        self.assertEqual([(m["method_id"], m["weight"]) for m in td["members"]], [("LAB_CDF", .5), ("CATBOOST_MEDIUM", .5)])
        self.assertTrue(all("scores" not in s["evidence"] for s in continued.document["choice"]["selections"]))

    def test_remaining_census_has_no_coverage_cut_and_no_elapsed_game_backfill(self):
        with self.assertRaises(ValueError):
            epoch.continue_week(self.r, self.f["schedule"], {"fictional-monday": "2026-10-26T19:30:00Z"}, clock=lambda: CONTINUED)
        later = epoch.continue_week(self.r, self.f["schedule"], {"fictional-monday": "2026-10-26T19:30:00Z"},
            clock=lambda: utc("2026-10-25T21:00:00Z"))
        self.assertEqual(set(later.document["slate"]["game_cutoffs"]), {"fictional-monday"})
        self.assertEqual(epoch._signature(later.document["choice"]["selections"]), self.e.origin["signature"])

    def test_changed_families_weights_or_old_procedure_rejected_even_with_new_document_hash(self):
        for field, value in (("weight", .75), ("method_id", "LAB_CDF"), ("procedure_version", h("old-procedure"))):
            changed = deepcopy(self.c.document)
            selection = next(s for s in changed["choice"]["selections"] if s["decision"]["category"] == "rush_att")
            selection["members"][0][field] = value
            forged = epoch.EpochChoice(changed, digest(changed))
            with self.subTest(field=field), self.assertRaises(epoch.EpochError):
                forged.verify(self.r, CONTINUED)

    def test_registration_cannot_authorize_before_persistence_or_use_mutated_epoch(self):
        with self.assertRaises(epoch.EpochError):
            epoch.bind_registration(self.e, self.r.completion, now=REGISTERED)
        self.e.document["fits"] = 1
        with self.assertRaisesRegex(epoch.EpochError, "CHANGED"):
            self.r.verify(CONTINUED)

    def test_capture_requires_fresh_durable_choice_version_catalog_before_any_values(self):
        versions = epoch.selected_versions(self.r, self.c, now=CONTINUED)
        completion = dict(schema_version=epoch.VERSION + "-choice-completion", choice_sha256=self.c.sha256,
            catalog_sha256=versions["catalog_sha256"], selected_versions_sha256=digest(versions),
            persisted_completed_at=(CONTINUED + timedelta(minutes=1)).isoformat(), qualified_artifact_restore=artifact_proof(self.e),
            metadata_cas_readback=cas_receipt("CHOICE_AND_SELECTED_VERSIONS", {"choice": self.c.document, "selected_versions": versions},
                CONTINUED + timedelta(seconds=10), CONTINUED + timedelta(minutes=1)),
            metadata_remote_durability_qualified=False, current_values_used=False)
        start = CONTINUED + timedelta(minutes=2)
        permit = epoch.authorize_capture(self.r, self.c, completion, clock=lambda: start)
        self.assertFalse(permit.document["metadata_remote_durability_qualified"])
        self.assertFalse(permit.document["captured_bundle_remote_durability_qualified"])
        epoch.validate_materialization(permit, source_started_at=start, source_completed_at=start + timedelta(seconds=1),
            issued_at=start + timedelta(seconds=2), game_id="fictional-sunday")
        for changed in (dict(completion, current_values_used=True), dict(completion, selected_versions_sha256="0" * 64)):
            with self.assertRaises(epoch.EpochError):
                epoch.authorize_capture(self.r, self.c, changed, clock=lambda: start)
        with self.assertRaises(epoch.EpochError):
            epoch.authorize_capture(self.r, self.c, completion, clock=lambda: CONTINUED)
        with self.assertRaises(epoch.EpochError):
            epoch.validate_materialization(permit, source_started_at=REGISTERED, source_completed_at=start, issued_at=start, game_id="fictional-sunday")
        with self.assertRaises(epoch.EpochError):
            epoch.validate_materialization(permit, source_started_at=start, source_completed_at=start,
                issued_at="2026-10-25T19:30:00Z", game_id="fictional-sunday")

    def test_local_cas_receipt_is_separate_from_models_only_restore_proof(self):
        for field, value in (("metadata_remote_durability_qualified", True),):
            changed = deepcopy(self.r.completion); changed[field] = value
            with self.assertRaises(epoch.EpochError):
                epoch.bind_registration(self.e, changed, now=CONTINUED)
        changed = deepcopy(self.r.completion)
        changed["qualified_artifact_restore"]["scope"] = "EPOCH_METADATA"
        with self.assertRaisesRegex(epoch.EpochError, "MODELS_ONLY"):
            epoch.bind_registration(self.e, changed, now=CONTINUED)
        changed = deepcopy(self.r.completion)
        changed["metadata_cas_readback"]["documents"][0]["payload_sha256"] = h("unrelated metadata")
        with self.assertRaisesRegex(epoch.EpochError, "CAS_METADATA_PAYLOAD"):
            epoch.bind_registration(self.e, changed, now=CONTINUED)

    def test_actual_owned_cas_write_readback_needs_no_remote_metadata_job(self):
        from nfl_lab.operational_storage import OperationalStorage
        root = Path(__file__).resolve().parents[1]
        policy = json.loads((root / "config/operational-source-policy-v2.json").read_text())
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            store = OperationalStorage(base / "cache", policy, state=base / "state")
            owned = store.register_root(base / "metadata")
            path = owned / "CORRECTION_EPOCH.json"
            store.atomic_json(path, self.e.document)
            raw = path.read_bytes()
            binding = dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
            clock = iter((REGISTERED + timedelta(seconds=30), REGISTERED + timedelta(seconds=40)))
            receipt = epoch.owned_cas_readback(store, {"epoch": binding}, {"epoch": self.e.document}, scope="EPOCH_METADATA",
                written_at=REGISTERED + timedelta(seconds=20), clock=lambda: next(clock))
            self.assertFalse(receipt["remote_durability_qualified"])
            self.assertNotIn(str(base), json.dumps(receipt))
            self.assertEqual(receipt["documents"][0]["payload_sha256"], self.e.sha256)
            completion = deepcopy(self.r.completion)
            completion.update(metadata_cas_readback=receipt, persisted_completed_at=receipt["readback_completed_at"])
            epoch.bind_registration(self.e, completion, now=CONTINUED)
            unowned = base / "unowned.json"; unowned.write_bytes(raw)
            wrong = dict(binding, path=str(unowned))
            with self.assertRaisesRegex(epoch.EpochError, "ACTUAL_OWNED_CAS"):
                epoch.owned_cas_readback(store, {"epoch": wrong}, {"epoch": self.e.document}, scope="EPOCH_METADATA",
                    written_at=REGISTERED, clock=lambda: CONTINUED)

    def test_relocated_manifest_union_passes_real_panel_gate_without_changing_epoch(self):
        relocated = deepcopy(self.f["replay"])
        for slot in relocated["slots"]:
            slot["manifest_sha256"] = h(["fresh-root", slot["target"], slot["method_id"]])
        union = epoch.artifact_catalog(self.e, relocated)
        current = history(self.r, [self.c])["bundle"]
        forecast = next(r for r in current["forecasts"] if r["method_id"] == "COUNT_A")
        original = forecast["model_version"]
        fresh = next(s for s in relocated["slots"] if (s["target"], s["method_id"]) == ("rush_att", "COUNT_A"))["manifest_sha256"]
        selector.Panel(current, union["catalog"])
        forecast["model_version"] = fresh
        selector.Panel(current, union["catalog"])
        self.assertNotIn(fresh, self.e.document["catalog"]["methods"]["COUNT_A"]["model_versions"])
        self.assertIn(original, union["catalog"]["methods"]["COUNT_A"]["model_versions"])
        self.assertEqual(selector.procedure_catalog(union["catalog"]), selector.procedure_catalog(self.e.document["catalog"]))
        relocated["slots"][0]["model_sha256"] = "f" * 64
        with self.assertRaisesRegex(epoch.EpochError, "RELOCATION"):
            epoch.artifact_catalog(self.e, relocated)

    def test_next_week_real_p2_scores_only_resolved_current_epoch_and_retains_negative_week(self):
        old = self.f["old_history"]
        first_history = history(self.r, [self.c])
        week8 = epoch.select_next_week(self.r, first_history, next_slate(8, "2026-10-29T20:00:00Z"), self.c,
            clock=lambda: utc("2026-10-28T10:00:00Z"))
        selected = next(s for s in week8.document["choice"]["selections"] if s["decision"]["category"] == "rush_att")
        self.assertEqual(selected["members"][0]["method_id"], "LAB_CDF")
        self.assertEqual(selected["evidence"]["scores"]["COUNT_A"], 100)
        second_history = history(self.r, [self.c, week8])
        before = digest(second_history)
        week9 = epoch.select_next_week(self.r, second_history, next_slate(9, "2026-11-05T20:00:00Z"), week8,
            clock=lambda: utc("2026-11-04T10:00:00Z"))
        selected = next(s for s in week9.document["choice"]["selections"] if s["decision"]["category"] == "rush_att")
        self.assertEqual(selected["evidence"]["scores"]["LAB_CDF"], 50)
        self.assertEqual(selected["evidence"]["scores"]["COUNT_A"], 100)
        self.assertEqual(len(selected["evidence"]["common_period"]), 2)
        self.assertEqual(len(week9.document["resolved_prior_keys"]), 2)
        self.assertEqual(digest(second_history), before); self.assertEqual(self.f["old_history"], old)

    def test_pending_grades_do_not_score_and_unscoped_or_old_forecasts_never_migrate(self):
        slate = next_slate(8, "2026-10-29T20:00:00Z")
        pending = history(self.r, [self.c], pending=True)
        choice = epoch.select_next_week(self.r, pending, slate, self.c, clock=lambda: utc("2026-10-28T10:00:00Z"))
        self.assertEqual(choice.document["resolved_prior_keys"], [])
        selected = next(s for s in choice.document["choice"]["selections"] if s["decision"]["category"] == "rush_att")
        self.assertFalse(selected["evidence"]["scores"])
        for kind, field, value in (("forecasts", "correction_epoch_sha256", "0" * 64),
                                  ("forecasts", "issued_at", "2026-10-20T00:00:00Z"),
                                  ("forecasts", "procedure_version", h(["old", "COUNT_A"]))):
            bad = history(self.r, [self.c]); bad["bundle"][kind][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                epoch.select_next_week(self.r, bad, slate, self.c, clock=lambda: utc("2026-10-28T10:00:00Z"))

    def test_actual_unobserved_reference_stays_unavailable_without_explicit_new_control_metadata(self):
        f = fixture(active_reference=False); e = prepare(f)
        self.assertFalse(e.document["catalog"]["methods"]["R0"]["procedure_operational_eligible"])
        control = dict(procedure_version=h("new-observed-reference"), model_versions=[h("observed-reference-artifact")],
            procedure_operational_eligible=True, procedure_replay_eligible=False, role="reference",
            training_state="UPSTREAM_TRAINING_UNOBSERVED", control_policy_sha256=h("registered-reference-policy"),
            control_source_version="fictional-observed-reference-v1", event_contract=selector.ANYTIME_EVENT_CONTRACT)
        e = prepare(f, effective_controls={"R0": control})
        self.assertEqual(e.document["catalog"]["methods"]["R0"]["registered_at"], REGISTERED.isoformat())
        self.assertEqual(e.document["catalog"]["methods"]["R0"]["training_state"], "UPSTREAM_TRAINING_UNOBSERVED")
        self.assertEqual(e.document["catalog"]["categories"]["anytime_td"]["event_contract"], selector.ANYTIME_EVENT_CONTRACT)
        self.assertNotIn("training_started_at", e.document["catalog"]["methods"]["R0"])
        self.assertFalse(f["catalog"]["methods"]["R0"]["procedure_operational_eligible"])

    def routine_choice(self):
        now = utc("2026-10-28T10:00:00Z")
        return epoch.select_next_week(self.r, history(self.r, [self.c]),
            next_slate(8, "2026-10-29T20:00:00Z"), self.c, clock=lambda: now), now

    def capture_permit(self):
        versions = epoch.selected_versions(self.r, self.c, now=CONTINUED)
        completed = CONTINUED + timedelta(minutes=1)
        completion = dict(schema_version=epoch.VERSION + "-choice-completion", choice_sha256=self.c.sha256,
            catalog_sha256=versions["catalog_sha256"], selected_versions_sha256=digest(versions),
            persisted_completed_at=completed.isoformat(), qualified_artifact_restore=artifact_proof(self.e),
            metadata_cas_readback=cas_receipt("CHOICE_AND_SELECTED_VERSIONS", {"choice": self.c.document, "selected_versions": versions},
                CONTINUED + timedelta(seconds=10), completed), metadata_remote_durability_qualified=False, current_values_used=False)
        start = CONTINUED + timedelta(minutes=2)
        return epoch.authorize_capture(self.r, self.c, completion, clock=lambda: start), start

    def test_routine_rehashed_double_weight_is_rejected_before_version_or_issuance(self):
        choice, now = self.routine_choice()
        changed = deepcopy(choice.document)
        selection = next(s for s in changed["choice"]["selections"] if s["decision"]["category"] == "rush_att")
        self.assertEqual(selection["members"][0]["weight"], 1)
        selection["members"][0]["weight"] = 2
        forged = epoch.EpochChoice(changed, digest(changed))
        with patch.object(selector, "issue", side_effect=AssertionError("invalid choice reached materialization")):
            with self.assertRaises(epoch.EpochError): forged.verify(self.r, now)
            with self.assertRaises(epoch.EpochError): epoch.selected_versions(self.r, forged, now=now)
        # Positive hand oracle: valid weight1 materializes the saved point20.
        chosen = next(s for s in choice.document["choice"]["selections"] if s["decision"]["category"] == "rush_att")
        panel = selector.Panel(history(self.r, [self.c, choice])["bundle"], epoch.artifact_catalog(self.e)["catalog"])
        self.assertEqual(generic.issue_registered(selector, panel, chosen, atomic_TD=True)[0]["forecast_value"], 20)

    def test_incomplete_rehashed_capture_permit_rejected_before_materialization(self):
        document = dict(schema_version=epoch.VERSION + "-capture-permit", fits=0, reselect=False,
            metadata_remote_durability_qualified=False, captured_bundle_remote_durability_qualified=False,
            actual_capture_authorized_at="2026-10-25T10:05:00Z", game_cutoffs={"fictional-game": "2026-10-25T19:30:00Z"})
        forged = epoch.CapturePermit(document, digest(document))
        with self.assertRaises(epoch.EpochError): forged.verify()
        with self.assertRaises(epoch.EpochError):
            epoch.validate_materialization(forged, source_started_at="2026-10-25T10:06:00Z",
                source_completed_at="2026-10-25T10:07:00Z", issued_at="2026-10-25T10:08:00Z", game_id="fictional-game")

    def test_routine_members_state_and_eligibility_are_closed(self):
        choice, now = self.routine_choice()
        def selected(value):
            return next(s for s in value["choice"]["selections"] if s["decision"]["category"] == "rush_att")
        mutations = [lambda s: s["members"][0].update(weight=0), lambda s: s["members"][0].update(weight=-1),
            lambda s: s["members"][0].update(weight=True), lambda s: s["members"][0].update(weight=.5),
            lambda s: s["members"].append(deepcopy(s["members"][0])), lambda s: s.update(state="ABSTAIN_NO_ELIGIBLE_PROCEDURE"),
            lambda s: s.update(state="SUCCESS"), lambda s: s.update(members=[]),
            lambda s: s["members"][0].update(choice_eligible=1), lambda s: s["members"][0].update(choice_eligible=False),
            lambda s: s["members"][0].update(extra="UNREGISTERED"), lambda s: s["members"][0].update(method_id="UNKNOWN")]
        for mutate in mutations:
            changed = deepcopy(choice.document); mutate(selected(changed))
            with self.subTest(mutation=mutate), self.assertRaises(epoch.EpochError):
                epoch.EpochChoice(changed, digest(changed)).verify(self.r, now)
        # A normalized two-method blend is still not an ordinary P2 choice.
        changed = deepcopy(choice.document); s = selected(changed); first = s["members"][0]; first["weight"] = .5
        second = deepcopy(first); second.update(method_id="COUNT_A", procedure_version=self.e.document["catalog"]["methods"]["COUNT_A"]["procedure_version"])
        s["members"].append(second)
        with self.assertRaises(epoch.EpochError): epoch.EpochChoice(changed, digest(changed)).verify(self.r, now)

    def test_registered_td_halves_and_empty_abstention_remain_valid(self):
        choice, now = self.routine_choice(); choice.verify(self.r, now)
        td = next(s for s in choice.document["choice"]["selections"] if s["decision"]["category"] == "anytime_td")
        self.assertEqual([(m["method_id"], m["weight"]) for m in td["members"]], [("LAB_CDF", .5), ("CATBOOST_MEDIUM", .5)])
        for weights in [(.25, .75), (1., 1.)]:
            changed = deepcopy(choice.document)
            altered = next(s for s in changed["choice"]["selections"] if s["decision"]["category"] == "anytime_td")
            for member, weight in zip(altered["members"], weights): member["weight"] = weight
            with self.subTest(weights=weights), self.assertRaises(epoch.EpochError):
                epoch.EpochChoice(changed, digest(changed)).verify(self.r, now)
        f = fixture(active_reference=False); f["catalog"]["methods"]["COUNT_A"]["procedure_operational_eligible"] = False
        empty = dict(schema_version=selector.VERSION, offers=[], forecasts=[], outcomes=[], decisions=[], weeks=[])
        original = generic.freeze_choices(selector, empty, f["catalog"], f["policy"], f["slate"], actual_choice_at=utc("2026-10-22T12:00:00Z"))
        f["raw"] = canonical(original); f["completion"]["choice_binding"].update(bytes=len(f["raw"]), sha256=hashlib.sha256(f["raw"]).hexdigest())
        corrected = prepare(f); continued = continuation(f, registered(corrected))
        abstain = next(s for s in continued.document["choice"]["selections"] if s["decision"]["category"] == "rush_att")
        self.assertEqual(abstain["state"], "ABSTAIN_NO_ELIGIBLE_PROCEDURE"); self.assertEqual(abstain["members"], [])
        continued.verify(registered(corrected), CONTINUED)

    def test_capture_permit_fields_hashes_types_flags_and_cutoffs_are_closed(self):
        permit, start = self.capture_permit(); permit.verify()
        for field in permit.document:
            changed = deepcopy(permit.document); changed.pop(field)
            with self.subTest(missing=field), self.assertRaises(epoch.EpochError):
                epoch.CapturePermit(changed, digest(changed)).verify()
        changes = [dict(extra="UNKNOWN"), dict(fits=False), dict(fits=1), dict(reselect=0), dict(reselect=True),
            dict(metadata_remote_durability_qualified=0), dict(metadata_remote_durability_qualified=True),
            dict(captured_bundle_remote_durability_qualified=True), dict(game_cutoffs={}), dict(game_cutoffs=[]),
            dict(game_cutoffs={"fictional-sunday": "naive"}), dict(game_cutoffs={"fictional-sunday": "2026-10-25T19:30:00"}),
            dict(game_cutoffs={"fictional-sunday": start.isoformat()}), dict(actual_capture_authorized_at=7)]
        changes += [{field: "invalid-hash"} for field in permit.document if field.endswith("_sha256")]
        for update in changes:
            changed = dict(permit.document, **update)
            with self.subTest(update=update), self.assertRaises(epoch.EpochError):
                epoch.CapturePermit(changed, digest(changed)).verify()
        epoch.validate_materialization(permit, source_started_at=start, source_completed_at=start + timedelta(seconds=1),
            issued_at=start + timedelta(seconds=2), game_id="fictional-sunday")

    def test_existing_catalog_procedure_identifiers_are_not_redefined_by_member_guard(self):
        f = fixture(); f["catalog"]["methods"]["R0"]["procedure_version"] = "original-registered-R0-v1"
        next(c for c in f["policy"]["categories"] if c["category"] == "rush_att")["startup_method_id"] = "R0"
        empty = dict(schema_version=selector.VERSION, offers=[], forecasts=[], outcomes=[], decisions=[], weeks=[])
        original = generic.freeze_choices(selector, empty, f["catalog"], f["policy"], f["slate"], actual_choice_at=utc("2026-10-22T12:00:00Z"))
        f["raw"] = canonical(original); f["completion"]["choice_binding"].update(bytes=len(f["raw"]), sha256=hashlib.sha256(f["raw"]).hexdigest())
        e = prepare(f); r = registered(e); c = continuation(f, r); c.verify(r, CONTINUED)
        member = next(s for s in c.document["choice"]["selections"] if s["decision"]["category"] == "rush_att")["members"][0]
        self.assertEqual(member["procedure_version"], "original-registered-R0-v1")
        self.assertEqual(member["weight"], 1)


if __name__ == "__main__":
    unittest.main()
