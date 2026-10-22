import copy
import hashlib
import json
from decimal import Decimal
from pathlib import Path

import pytest

from nfl_lab.receiving import (CORE_SHA256, RECEPTION_REGISTERED_AT, RECEPTION_WEEKS,
                               SourceDocument, evaluate_receiving, reception_half_adjustment)
from nfl_lab.retained import receiving_yards_core_draft as retained_core


def fixture():
    context = dict(player_id="synthetic", game_id="future", team="A", opponent="B",
                   season=2000, week=7, period="full_game_with_ot",
                   cutoff_at="2000-10-22T12:00:00Z", kickoff_at="2000-10-22T17:00:00Z",
                   projection_observed_at="2000-10-22T11:00:00Z", website_yards=40.5,
                   projected_targets=6., projection_source_ref="synthetic-projection")
    schedule = dict(player_id="synthetic", season=2000, period=context["period"],
                    through_week=6, weeks=[])
    records = []
    for week in range(1, 7):
        # Synthetic dates merely provide strict chronology; no NFL outcomes.
        ended = f"2000-10-{week + 1:02}T20:00:00Z"
        schedule["weeks"].append(dict(week=week, state="game", game_id=f"g{week}",
                                      team="A", opponent="B", ended_at=ended))
        records.append(dict(player_id="synthetic", game_id=f"g{week}", team="A", opponent="B",
                            period=context["period"], season=2000, week=week,
                            ended_at=ended, stats_observed_at=f"2000-10-{week + 1:02}T22:00:00Z",
                            participation="played", targets={6: 10, 5: 2, 4: 8}.get(week, 5),
                            yards={6: 100, 5: 10, 4: 50}.get(week, 25), source_ref="synthetic-stats"))
    return context, schedule, dict(records=records), dict(context)


def evaluate(context, schedule, stats, projected, *, mutate_documents=None):
    documents = {}
    pins = {}
    for name, reference, payload in (("opportunities", "synthetic-schedule", schedule),
                                     ("statistics", "synthetic-stats", stats),
                                     ("projection", "synthetic-projection", projected)):
        observed = context["projection_observed_at"] if name == "projection" else "2000-10-21T12:00:00Z"
        document = SourceDocument(reference, json.dumps(payload, sort_keys=True).encode(), observed)
        documents[name] = document
        pins[reference] = hashlib.sha256(document.payload).hexdigest()
    if mutate_documents:
        mutate_documents(documents)
    return evaluate_receiving(context, **documents, trusted_hashes=pins)


def test_retained_core_bytes_are_unchanged():
    assert hashlib.sha256(Path(retained_core.__file__).read_bytes()).hexdigest() == CORE_SHA256


def test_source_authenticated_exact_latest_three_pooled_and_signed():
    args = fixture()
    before = copy.deepcopy(args)
    result = evaluate(*args)
    assert result.value == Decimal("48")
    assert result.history_game_ids == ("g6", "g5", "g4")
    assert result.state == "CANDIDATE_ARITHMETIC"
    assert args == before
    for row in args[2]["records"]:
        row["yards"] = -10
    assert evaluate(*args).value == Decimal("-9")


@pytest.mark.parametrize("change", ["unknown", "missing", "missing_yards", "missing_targets"])
def test_intervening_unknown_or_unfavorable_game_is_never_skipped(change):
    context, schedule, stats, projected = fixture()
    if change == "missing":
        stats["records"].pop(4)
    elif change == "unknown":
        stats["records"][4]["participation"] = "unknown"
    else:
        del stats["records"][4][change.removeprefix("missing_")]
    result = evaluate(context, schedule, stats, projected)
    assert result.state == "UNCHANGED_WEBSITE_FALLBACK"
    assert result.value == Decimal("40.5")


def test_bye_and_explicit_dnp_do_not_count_as_appearances():
    context, schedule, stats, projected = fixture()
    schedule["weeks"][5] = dict(week=6, state="bye", team="A")
    stats["records"].pop(5)
    stats["records"][4]["participation"] = "dnp"
    result = evaluate(context, schedule, stats, projected)
    assert result.state == "CANDIDATE_ARITHMETIC"
    assert result.history_game_ids == ("g4", "g3", "g2")


def test_trade_is_explicit_original_core_team_fallback_not_skipped_old_team():
    context, schedule, stats, projected = fixture()
    schedule["weeks"][4]["team"] = "C"
    stats["records"][4]["team"] = "C"
    result = evaluate(context, schedule, stats, projected)
    assert result.state == "UNCHANGED_WEBSITE_FALLBACK"
    assert result.reason == "history_identity_mismatch"
    assert result.history_game_ids == ("g6", "g5", "g4")


def test_new_player_and_early_season_do_not_borrow_previous_season():
    context, schedule, stats, projected = fixture()
    for index in range(4):
        schedule["weeks"][index] = dict(week=index+1, state="not_rostered")
    stats["records"] = stats["records"][4:]
    assert evaluate(context, schedule, stats, projected).reason == "exactly_three_selected_appearances_required"
    context["week"] = projected["week"] = 2
    schedule["through_week"] = 1
    schedule["weeks"] = [dict(week=1, state="not_rostered")]
    stats["records"] = []
    assert evaluate(context, schedule, stats, projected).state == "UNCHANGED_WEBSITE_FALLBACK"


def test_cannot_omit_schedule_week_or_duplicate_a_game_or_use_another_projection():
    context, schedule, stats, projected = fixture()
    schedule["weeks"].pop(4)
    assert evaluate(context, schedule, stats, projected).reason == "missing_or_duplicate_prior_week"
    context, schedule, stats, projected = fixture()
    projected["projected_targets"] = 7
    assert "projection_content_mismatch" in evaluate(context, schedule, stats, projected).reason


@pytest.mark.parametrize("change", ["hash", "late", "retrospective"])
def test_source_tampering_and_retroactive_clocks_cannot_qualify(change):
    def mutate(documents):
        source = documents["statistics"]
        if change == "hash":
            source = SourceDocument(source.reference, source.payload + b" ", source.observed_at)
        elif change == "late":
            source = SourceDocument(source.reference, source.payload, "2000-10-22T12:00:01Z")
        else:
            source = SourceDocument(source.reference, source.payload, source.observed_at,
                                    time_basis="downloaded_revised_history_today")
        documents["statistics"] = source
    assert evaluate(*fixture(), mutate_documents=mutate).state == "UNCHANGED_WEBSITE_FALLBACK"


def test_late_original_projection_abstains_and_frozen_reception_formula_unchanged():
    context, schedule, stats, projected = fixture()
    context["projection_observed_at"] = projected["projection_observed_at"] = "2000-10-22T12:00:01Z"
    assert evaluate(context, schedule, stats, projected).state == "ABSTAIN"
    assert reception_half_adjustment(2.5, 3.8) == Decimal("3.15")
    assert RECEPTION_REGISTERED_AT == "2026-10-16T19:36:46.224755Z"
    assert RECEPTION_WEEKS == tuple(range(7, 15))
