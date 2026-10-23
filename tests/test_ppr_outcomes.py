from copy import deepcopy

import pytest

from nfl_lab.ppr_outcomes import qualify_ppr_panel
from nfl_lab.ppr_sources import NFL_FIELDS, RARE_GAPS
from nfl_lab.scoring import PPR_COMPONENTS


RECEIPT = {"status": "acquired", "sha256": "a" * 64, "url": "https://example.test/ppr",
           "retrieved_utc": "2026-10-23T00:00:00Z", "original_publication_utc": None}


def planned(player="p", **updates):
    return {"player_id": player, "game_id": "2023_01_A_B", "team": "A", "opponent": "B",
            "season": 2023, "week": 1, "season_type": "REG", "position": "QB", **updates}


def observed(player="p", **updates):
    return {**planned(player), "stats": {**{key: 0 for key in PPR_COMPONENTS}, "gp": 1}, **updates}


def run(plans, source, kind="sleeper", receipt=RECEIPT):
    return qualify_ppr_panel(plans, source, source_kind=kind, source_receipt=receipt)


def test_all_planned_rows_retained_including_zero_negative_unknown_and_absent():
    source = [observed("zero"), observed("negative", stats={**observed()["stats"], "pass_int": 1}),
              observed("unknown", stats={key: 0 for key in PPR_COMPONENTS})]
    plans = [planned(x) for x in ["zero", "negative", "unknown", "absent"]]
    before = deepcopy((plans, source))
    report = run(plans, source)
    assert report["planned_rows"] == 4 and report["qualified_exact_rows"] == 2
    assert [row["exact_ppr"] for row in report["rows"]] == [0, -1, None, None]
    assert [row["qualification"] for row in report["rows"]][-2:] == ["participation_unknown", "missing_source_observation"]
    assert (plans, source) == before


def test_sparse_provider_totals_and_nflverse_rare_zeros_remain_unqualified():
    sparse = observed(stats={"gp": 1, "rec": 1, "rec_yd": 10, "pts_ppr": 2})
    row = run([planned()], [sparse])["rows"][0]
    assert row["exact_ppr"] is None and "st_ff" in row["missing_components"]
    nfl = observed(stats={**{field: 0 for field in NFL_FIELDS.values()}, "fantasy_points_ppr": 0},
                   snaps={"offense_snaps": 1, "defense_snaps": 0, "st_snaps": 0})
    row = run([planned()], [nfl], "nflverse")["rows"][0]
    assert row["participation_state"] == "played" and row["exact_ppr"] is None
    assert set(row["missing_components"]) == set(RARE_GAPS)


def test_exact_rare_credit_exception_and_final_rounding_are_preserved():
    raw = {**observed()["stats"], "pass_yd": 1, "rec_yd": -0.3, "fum_rec_td": 1,
           "idp_fum_rec": 1, "fum_lost": 1, "st_ff": 1}
    assert run([planned()], [observed(stats=raw)])["rows"][0]["exact_ppr"] == -0.99
    del raw["idp_fum_rec"]
    assert run([planned()], [observed(stats=raw)])["rows"][0]["exact_ppr"] is None


def test_participation_position_and_identity_are_independent_of_point_total():
    source = [observed(stats={**observed()["stats"], "gp": 0, "pts_ppr": 99})]
    assert run([planned()], source)["rows"][0]["qualification"] == "participation_unknown"
    source = [observed(position=None)]
    assert run([planned()], source)["rows"][0]["qualification"] == "source_position_unqualified"
    source = [observed(game_id="different")]
    result = run([planned()], source)
    assert result["rows"][0]["qualification"] == "missing_source_observation"
    assert result["unmatched_source_rows"] == 1
    with pytest.raises(ValueError, match="duplicate PPR source"):
        run([planned()], [observed(), observed()])
    with pytest.raises(ValueError, match="duplicate planned"):
        run([planned(), planned()], [observed()])


@pytest.mark.parametrize("receipt", [{}, {**RECEIPT, "sha256": "bad"},
                                     {**RECEIPT, "retrieved_utc": "2026-10-23"}])
def test_source_receipt_requires_integrity_and_aware_retrieval_clock(receipt):
    with pytest.raises(ValueError, match="PPR source"):
        run([planned()], [observed()], receipt=receipt)


def test_invalid_count_and_missing_identity_fail_without_point_substitution():
    bad = observed(stats={**observed()["stats"], "rec": 0.5, "pts_ppr": 99})
    row = run([planned()], [bad])["rows"][0]
    assert row["qualification"] == "invalid_components" and row["invalid_components"] == ["rec"]
    with pytest.raises(ValueError, match="identity missing"):
        run([planned(game_id=None)], [])


def test_known_inactive_is_distinct_from_unknown_and_conflicting_play_evidence():
    inactive = observed(stats={}, roster_status="INA", participation_evidence="explicit_weekly_inactive")
    row = run([planned()], [inactive])["rows"][0]
    assert row["participation_state"] == "DNP" and row["exact_ppr"] is None
    assert row["qualification"] == "known_dnp_outside_conditional_population"
    inactive["stats"] = {"gp": 1}
    row = run([planned()], [inactive])["rows"][0]
    assert row["participation_state"] == "conflicting" and row["exact_ppr"] is None
    assert row["qualification"] == "participation_evidence_conflict"
