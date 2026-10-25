"""Fictional direct-website engineering fixtures; never real NFL scoring."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import nfl_lab.website_cdf as campaign
from nfl_lab.cdf_engine import KEYS, LeafCDFModel, prediction_rows, score_frozen_rows
from nfl_lab.website_cdf_evaluation import (
    bind_outcomes, ensemble_frozen_rows, literal_controls, paired_rows,
    report_ensemble, report_target, score_ensemble, target_query,
)
from test_cdf_engine import fictional


def website_fixture():
    train, query, category = fictional()
    query["season"], query["week"] = 2026, 6
    query["kickoff_utc"] = pd.Timestamp("2026-10-18T17:00:00Z")
    query["cutoff_utc"] = pd.Timestamp("2026-10-18T10:00:00Z")
    query["feature_max_source_available_utc"] = pd.Timestamp("2026-10-12T00:00:00Z")
    query["outcome_available_utc"] = pd.NaT
    query["participation_state"] = "unknown"
    offers = query[KEYS + ["position", "team", "opponent", "kickoff_utc", "cutoff_utc"]].copy()
    offers["target"] = category["target"]
    offers["website_point"], offers["raw_point"], offers["simple_point"] = 7., 9., np.nan
    offers["website_probability"], offers["raw_probability"], offers["simple_probability"] = np.nan, np.nan, np.nan
    outcomes = query[KEYS].copy()
    outcomes["target"] = category["target"]
    outcomes["actual"] = np.arange(len(query), dtype=float)
    outcomes["participation_state"], outcomes["outcome_state"] = "played", "qualified_played"
    outcomes["quarantined"] = False
    outcomes["outcome_source_version"] = "fictional-v1"
    return train, query, offers, outcomes, category


def test_original_offer_order_and_permuted_outcomes_bind_by_identity():
    _, query, offers, outcomes, category = website_fixture()
    offers = offers.iloc[::-1].reset_index(drop=True)
    selected, retained = target_query(query.sample(frac=1, random_state=12), offers, category["target"])
    assert selected.player_id.tolist() == retained.player_id.tolist()
    assert selected.game_id.tolist() == retained.game_id.tolist()
    bound = bind_outcomes(selected, outcomes.sample(frac=1, random_state=54), category)
    expected = selected[KEYS].merge(outcomes[KEYS + ["actual"]], on=KEYS, how="left", sort=False)
    np.testing.assert_array_equal(bound[category["target"]], expected.actual)
    assert bound.qualified_outcome_source_version.eq("fictional-v1").all()


@pytest.mark.parametrize("mutation", ["missing_offer", "duplicate_offer", "wrong_team", "missing_outcome", "extra_outcome", "duplicate_outcome"])
def test_population_and_context_mismatch_rejected(mutation):
    _, query, offers, outcomes, category = website_fixture()
    if mutation == "missing_offer":
        query = query.iloc[1:]
    elif mutation == "duplicate_offer":
        offers = pd.concat([offers, offers.iloc[:1]])
    elif mutation == "wrong_team":
        offers.loc[0, "team"] = "fictional-wrong"
    elif mutation == "missing_outcome":
        outcomes = outcomes.iloc[1:]
    elif mutation == "extra_outcome":
        outcomes.loc[0, "player_id"] = "fictional-extra"
    else:
        outcomes = pd.concat([outcomes, outcomes.iloc[:1]])
    with pytest.raises(ValueError):
        selected, _ = target_query(query, offers, category["target"])
        bind_outcomes(selected, outcomes, category)


def test_quarantine_missing_dnp_unknown_and_played_zero_retained():
    train, query, offers, outcomes, category = website_fixture()
    outcomes.loc[0, "quarantined"] = True
    outcomes.loc[1, "participation_state"] = "DNP"
    outcomes.loc[2, "participation_state"] = "unknown"
    outcomes.loc[3, "actual"] = np.nan
    outcomes.loc[4, "actual"] = 0
    bound = bind_outcomes(query, outcomes, category)
    assert np.isnan(bound.loc[0, category["target"]])
    assert bound.loc[0, "qualified_actual"] == 0  # preserved source, explicitly excluded
    model = LeafCDFModel.fit(train, category, "base")
    scored = score_frozen_rows(model, bound, prediction_rows(model, query))
    control = literal_controls(offers, scored, category)
    value, rows = paired_rows(scored, control.loc[control.method.eq("website")], category)
    assert len(rows) == len(query)
    assert value["paired_rows"] == len(query) - 4
    assert rows.loc[4, "paired_eligible"]


def test_primary_is_median_vs_literal_site_and_each_control_has_same_keys():
    train, query, offers, outcomes, category = website_fixture()
    model = LeafCDFModel.fit(train, category, "base")
    bound = bind_outcomes(query, outcomes, category)
    scored = score_frozen_rows(model, bound, prediction_rows(model, query))
    scored["median"] = scored.actual + 1
    scored["mean"] = scored.actual + 100
    offers["website_point"] = scored.actual + 3
    offers["raw_point"] = scored.actual + 5
    offers.loc[0, "raw_point"] = np.nan
    controls = literal_controls(offers, scored, category)
    report, rows = report_target(scored, controls, category)
    primary = next(x for x in report["paired"] if x["status"] == "primary")
    assert primary["comparator"] == "website"
    assert primary["candidate_point"] == "median"
    assert primary["delta_candidate_minus_control"] == -2
    assert primary["paired_rows"] == len(query)
    raw = next(x for x in report["paired"] if x["comparator"] == "raw" and x["population"] == "all_original_offered" and x["status"] == "secondary")
    assert raw["paired_rows"] == len(query) - 1
    assert raw["delta_candidate_minus_control"] == -4
    assert primary["interval"] is None
    assert rows.groupby(["comparator", "population"]).size().eq(len(query)).all()


def test_td_probability_is_genuine_literal_and_zero_keeps_infinite_log_loss():
    train, query, offers, outcomes, category = website_fixture()
    category["support"], category["target"] = "bernoulli", "anytime_td"
    train["anytime_td"] = train.pass_att % 2
    outcomes["target"] = "anytime_td"
    outcomes["actual"], outcomes["rush_td"], outcomes["rec_td"] = 1., 0., 1.
    offers["target"], offers["website_probability"] = "anytime_td", 0.
    offers["raw_point"] = 100  # never converted into an event probability
    model = LeafCDFModel.fit(train, category, "base")
    scored = score_frozen_rows(model, bind_outcomes(query, outcomes, category), prediction_rows(model, query))
    controls = literal_controls(offers, scored, category)
    assert controls.loc[controls.method.eq("raw"), "point"].isna().all()
    assert np.isposinf(controls.loc[controls.method.eq("website"), "log_score"]).all()
    value, _ = paired_rows(scored, controls.loc[controls.method.eq("website")], category)
    assert value["primary_loss"] == "brier"
    assert value["candidate_point"] == "mean"
    offers.loc[0, "website_probability"] = 1.1
    with pytest.raises(ValueError, match="outside"):
        literal_controls(offers, scored, category)
    outcomes.loc[0, "rec_td"] = np.nan
    with pytest.raises(ValueError, match="composite"):
        bind_outcomes(query, outcomes, category)


def test_only_2019_to_2025_labels_available_before_earliest_cutoff_train():
    train, query, _, _, _ = website_fixture()
    train.loc[0, "season"] = 2018
    train.loc[1, "season"] = 2026
    train.loc[2, "outcome_available_utc"] = query.cutoff_utc.min()
    train.loc[3, "outcome_available_utc"] = pd.NaT
    selected, audit = campaign.training_split(train, query)
    assert len(selected) == len(train) - 4
    assert audit["training_seasons"] == [2020]
    query.loc[0, "feature_max_source_available_utc"] = query.loc[0, "cutoff_utc"]
    with pytest.raises(ValueError, match="source"):
        campaign.training_split(train, query)


def test_single_equalweight_numeric_blend_is_frozen_point_heuristic_and_missing_site_abstains():
    train, query, offers, outcomes, category = website_fixture()
    model = LeafCDFModel.fit(train, category, "base")
    frozen = prediction_rows(model, query)
    frozen["median"], frozen["mean"] = 10., 20.
    offers["website_point"] = 4.
    offers.loc[0, "website_point"] = np.nan
    blend = ensemble_frozen_rows(frozen, offers, category)
    assert np.isnan(blend.loc[0, "ensemble_point"])
    assert blend.loc[0, "abstention"] == "missing_literal_website"
    assert blend.loc[1:, "ensemble_point"].eq(7.).all()
    assert blend.loc[1:, "ensemble_mean_point"].eq(12.).all()
    assert blend.distribution.eq("none_point_heuristic").all()
    assert not {"median", "mean", "crps"} & set(blend)
    assert blend.actual.isna().all()
    scored = score_frozen_rows(model, bind_outcomes(query, outcomes, category), frozen)
    scored_blend = score_ensemble(blend, scored, category)
    assert scored_blend.log_score.isna().all()
    report, rows = report_ensemble(scored_blend, literal_controls(offers, scored, category), category)
    primary = next(x for x in report["paired"] if x["status"] == "primary")
    assert primary["candidate_point"] == "ensemble_point"
    assert primary["paired_rows"] == len(query) - 1
    assert len(rows) == 6 * len(query)
    assert "no numeric probability law" in report["point_semantics"]


def test_equalweight_td_defines_bernoulli_probability_without_clipping_or_numeric_law():
    train, query, offers, outcomes, category = website_fixture()
    category["target"], category["support"] = "anytime_td", "bernoulli"
    train["anytime_td"] = train.pass_att % 2
    offers["target"], outcomes["target"] = "anytime_td", "anytime_td"
    outcomes["actual"], outcomes["rush_td"], outcomes["rec_td"] = 1., 1., 0.
    model = LeafCDFModel.fit(train, category, "context")
    frozen = prediction_rows(model, query)
    frozen["mean"], frozen["median"] = .6, 1.
    offers["website_probability"] = .2
    blend = ensemble_frozen_rows(frozen, offers, category)
    np.testing.assert_allclose(blend.ensemble_point, .4)
    scored = score_frozen_rows(model, bind_outcomes(query, outcomes, category), frozen)
    scored_blend = score_ensemble(blend, scored, category)
    np.testing.assert_allclose(scored_blend.brier, .36)
    np.testing.assert_allclose(scored_blend.log_score, -np.log(.4))
    frozen["mean"], offers["website_probability"] = 0., 0.
    scored_zero = score_ensemble(ensemble_frozen_rows(frozen, offers, category), scored, category)
    assert np.isposinf(scored_zero.log_score).all()
    assert scored_zero.ensemble_point.eq(0.).all()


def test_no_seal_or_existing_output_cannot_launch(tmp_path):
    registry = tmp_path / "draft.json"
    registry.write_text(json.dumps({"state": "DRAFT"}))
    with pytest.raises(ValueError, match="reviewer seal"):
        campaign.run(registry, tmp_path / "new")
    assert not (tmp_path / "new").exists()
    retained = tmp_path / "old"
    retained.mkdir()
    (retained / "failure").write_text("preserve")
    with pytest.raises(FileExistsError, match="restart"):
        campaign.run(registry, retained)
    assert (retained / "failure").read_text() == "preserve"


def test_all_forecasts_precede_one_score_and_failures_are_consumed(tmp_path, monkeypatch):
    registry = {"output_directory": str(tmp_path / "outputs"), "categories": {target: {"state": "BLOCKED_LABEL_CONTRACT" if target == "fantasy_ppr" else "READY"} for target in campaign.TARGETS}}
    source = tmp_path / "sealed.json"
    source.write_text(json.dumps(registry))
    monkeypatch.setattr(campaign, "check_seal", lambda _: registry)
    monkeypatch.setattr(campaign, "environment_receipt", lambda: {"fictional": True})
    calls = []

    def fictional_process(arguments, output, directory, **kwargs):
        calls.append(arguments[0])
        if arguments[0] == "predict-trial":
            assert not (output / "score-consumed.json").exists()
            assert (directory / "attempt-consumed.json").exists()
            if len(calls) == 2:
                (directory / "retained-failure").write_text("fictional failed attempt")
                return {"returncode": 1, "cpu_seconds": .001}
            frozen = directory / "fictional-forecast.txt"
            frozen.write_text("frozen before labels")
            campaign.write_json(directory / "prediction-manifest.json", {"bindings": {frozen.name: campaign.digest(frozen)}})
        else:
            assert len(calls) == 23
            assert (output / "forecast-freeze.json").exists()
            statuses = json.loads((output / "attempts.json").read_text())
            assert len(statuses) == 24
            assert sum(x["state"] == "BLOCKED_CATEGORY_CONTRACT" for x in statuses) == 2
            assert sum(x["state"] == "FAILED_CONSUMED" for x in statuses) == 1
            (output / "score-consumed.json").write_text("one fictional phase")
            campaign.write_json(output / "website-cdf-report.json", {"fictional": True})
        return {"returncode": 0, "cpu_seconds": .001}

    monkeypatch.setattr(campaign, "monitored_process", fictional_process)
    output = tmp_path / "outputs"
    assert campaign.run(source, output)
    assert calls.count("predict-trial") == 22
    assert calls.count("score-report") == 1
    assert (output / "trials/pass_yd/context/retained-failure").is_file()
    complete = json.loads((output / "completion.json").read_text())
    assert complete["fit_attempts_consumed"] == 22
    with pytest.raises(FileExistsError):
        campaign.run(source, output)
    with pytest.raises(ValueError, match="sealed create-only"):
        campaign.run(source, tmp_path / "second-output")


def test_real_score_entrypoint_requires_freeze_and_consumes_only_once(tmp_path, monkeypatch):
    monkeypatch.setattr(campaign, "check_seal", lambda _: {"output_directory": str(tmp_path)})
    with pytest.raises(ValueError, match="global forecast freeze"):
        campaign.score_report("fictional", tmp_path)
    (tmp_path / "forecast-freeze.json").write_text("{}")
    (tmp_path / "score-consumed.json").write_text("retained partial score")
    with pytest.raises(ValueError, match="one score pass"):
        campaign.score_report("fictional", tmp_path)


def test_fictional_model_freeze_score_roundtrip_preserves_source_and_rejects_rescore(tmp_path, monkeypatch):
    train, query, offers, outcomes, category = website_fixture()
    paths = {}
    for name, frame in [("training_features", train), ("query_features", query),
                        ("opportunities", offers), ("outcomes", outcomes)]:
        path = tmp_path / (name + ".parquet")
        frame.to_parquet(path, index=False)
        paths[name] = {"path": str(path), "sha256": campaign.digest(path)}
    registry = {"inputs": paths, "categories": {"pass_att": category}, "output_directory": str(tmp_path / "private-output"),
                "source_qualification": "fictional only", "prior_search_and_exposure": "fictional only"}
    monkeypatch.setattr(campaign, "check_seal", lambda _: registry)
    real_reader = pd.read_parquet
    reads = []

    def tracked_reader(path, *args, **kwargs):
        reads.append(str(path))
        return real_reader(path, *args, **kwargs)

    monkeypatch.setattr(pd, "read_parquet", tracked_reader)
    output = tmp_path / "private-output"
    directory = output / "trials/pass_att/base"
    directory.mkdir(parents=True)
    campaign.write_json(directory / "attempt-consumed.json", {"attempt": 1})
    campaign.prediction_trial("fictional", directory, "pass_att", "base")
    assert paths["outcomes"]["path"] not in reads
    frozen = real_reader(directory / "candidate-frozen.parquet")
    assert frozen.actual.isna().all()
    assert frozen.participation_state.eq("unread").all()
    status = {"target": "pass_att", "panel": "base", "trial": "trials/pass_att/base", "state": "PREDICTION_FROZEN"}
    campaign.write_json(output / "attempts.json", [status])
    manifest = json.loads((directory / "prediction-manifest.json").read_text())
    bindings = {str((directory / name).relative_to(output)): value for name, value in manifest["bindings"].items()}
    campaign.write_json(output / "forecast-freeze.json", {"bindings": bindings, "attempts_sha256": campaign.digest(output / "attempts.json")})
    campaign.score_report("fictional", output)
    assert reads.count(paths["outcomes"]["path"]) == 1
    scored = real_reader(directory / "candidate-scored.parquet")
    assert scored.qualified_outcome_source_version.eq("fictional-v1").all()
    assert scored.outcome_state.eq("qualified_played").all()
    assert scored["mean"].equals(frozen["mean"])
    assert (output / "website-cdf-report.json").is_file()
    assert (directory / "ensemble-frozen.parquet").is_file()
    assert (directory / "ensemble-scored.parquet").is_file()
    assert (directory / "ensemble-report.json").is_file()
    report = json.loads((output / "website-cdf-report.json").read_text())
    assert report["primary_contrast_slots"] == 48
    assert report["blocked_ppr_slots"] == 4
    assert {x["method_family"] for x in report["slots"]} == {"pure_cdf", "website_equalweight"}
    with pytest.raises(ValueError, match="one score pass"):
        campaign.score_report("fictional", output)
    with pytest.raises(FileExistsError, match="no retry"):
        campaign.prediction_trial("fictional", directory, "pass_att", "base")


def test_monitor_kills_process_group_on_rss_budget_and_retains_failure(tmp_path, monkeypatch):
    class FakeProcess:
        pid = 12345
        returncode = None

        def __init__(self, *args, **kwargs):
            assert kwargs["start_new_session"] is True
            assert kwargs["env"]["OMP_NUM_THREADS"] == "2"

        def poll(self):
            return self.returncode

    monkeypatch.setattr(campaign.subprocess, "Popen", FakeProcess)
    monkeypatch.setattr(campaign, "proc_usage", lambda _: (campaign.LIMITS["memory_bytes"] + 1, .01))
    terminated = []

    def fake_terminate(process):
        terminated.append(process.pid)
        process.returncode = -15

    monkeypatch.setattr(campaign, "terminate_group", fake_terminate)
    usage = campaign.monitored_process(["fictional"], tmp_path, tmp_path, remaining_wall=30, remaining_cpu=30)
    assert usage["reason"] == "RSS_LIMIT"
    assert usage["returncode"] == -15
    assert terminated == [12345]
    assert (tmp_path / "stdout.log").exists()
    assert (tmp_path / "stderr.log").exists()


def fictional_seal(tmp_path, monkeypatch):
    source = tmp_path / "fictional-source.txt"
    source.write_text("fictional bytes; no football observations")
    binding = {"path": str(source), "sha256": campaign.digest(source)}
    monkeypatch.setattr(campaign, "ORIGINAL_HASHES", {"original_baseline": binding["sha256"], "original_board": binding["sha256"]})
    module = Path(campaign.__file__)
    names = ["website_cdf.py", "website_cdf_evaluation.py", "cdf_campaign.py", "cdf_engine.py", "cdf_evaluation.py"]
    code = [{"path": str(module.with_name(name)), "sha256": campaign.digest(module.with_name(name))} for name in names]
    categories = {target: {"state": "READY" if target != "fantasy_ppr" else "BLOCKED_LABEL_CONTRACT"} for target in campaign.TARGETS}
    prior = tmp_path / "fictional-prior.json"
    campaign.write_json(prior, {"categories": categories, "source": binding, "code_bindings": code})
    payload = {"registration_id": campaign.VERSION, "categories": categories, "budgets": campaign.LIMITS,
        "ensemble_design": campaign.ENSEMBLE_DESIGN, "output_directory": str(tmp_path / "one-output"),
        "prior_registry": {"path": str(prior), "sha256": campaign.digest(prior)},
        "inputs": {name: binding for name in ["training_features", "query_features", "opportunities", "outcomes"]},
        "source_bindings": {"original_baseline": binding, "original_board": binding},
        "code_bindings": code, "prerequisite_bindings": []}
    plan = tmp_path / "fictional-plan.json"
    campaign.write_json(plan, dict(payload, state="DRAFT"))
    registry = tmp_path / "fictional-registry.json"
    seal = {"integrator": "/root", "reviewer": "/root/fictional_reviewer", "decision": "PASS_BOUNDED_EXPOSED_RESEARCH_ONLY",
            "reviewed_plan_path": str(plan), "reviewed_plan_sha256": campaign.digest(plan)}
    campaign.write_json(registry, dict(payload, state="SEALED_ROOT_AND_REVIEWER", seal=seal))
    return registry, source


def test_seal_binds_exact_review_payload_code_and_all_input_bytes(tmp_path, monkeypatch):
    registry, source = fictional_seal(tmp_path, monkeypatch)
    assert campaign.check_seal(registry)["registration_id"] == campaign.VERSION
    source.write_text("changed source bytes")
    with pytest.raises(ValueError, match="sealed bytes changed"):
        campaign.check_seal(registry)


def test_seal_rejects_unreviewed_payload_changes(tmp_path, monkeypatch):
    registry, _ = fictional_seal(tmp_path, monkeypatch)
    content = json.loads(registry.read_text())
    content["output_directory"] = str(tmp_path / "another-output")
    campaign.write_json(registry, content)
    with pytest.raises(ValueError, match="differs from reviewed plan"):
        campaign.check_seal(registry)
