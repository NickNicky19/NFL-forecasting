"""Fictional metadata identities only; no NFL observations or model execution."""
import json

import pandas as pd
import pytest

from nfl_lab.query_identity import OUTPUT_COLUMNS, VERSION, resolve_query_identities

SHA = "a" * 64


def query(players, games=None):
    n = len(players)
    return pd.DataFrame({"cutoff_utc": pd.to_datetime(["2026-01-01T00:00Z"] * n, utc=True),
        "game_id": games or ["fictional-game-" + str(i) for i in range(n)],
        "kickoff_utc": pd.to_datetime(["2026-01-02T00:00Z"] * n, utc=True), "opponent": "B",
        "outcome_available_utc": pd.to_datetime([None] * n, utc=True), "participation_state": "unknown",
        "player_id": players, "position": "QB", "season": 2026, "team": "A", "week": 1})


def registry(rows):
    return pd.DataFrame(rows, columns=["player_id", "sleeper_id", "identity_status"])


def exact(player="00-0000001", sleeper="123"):
    return (player, sleeper, "source_exact_binding")


def test_exact_resolution_preserves_context_alias_index_dtype_and_inputs():
    original = query(["sleeper:123", " 00-0000001 ", "00-0000001", "00-0000009", "sleeper:999"])
    original.index = pd.Index([8, 3, 3, 17, 0], name="original-order")
    original["player_id"] = original.player_id.astype("string")
    source = registry([exact()])
    before, source_before = original.copy(deep=True), source.copy(deep=True)
    result, receipt = resolve_query_identities(original, source, identity_sha256=SHA)
    assert result.player_id.tolist() == ["00-0000001"] * 3 + ["00-0000009", "sleeper:999"]
    assert result.original_player_id.tolist() == original.player_id.tolist()
    assert list(result) == list(original) + list(OUTPUT_COLUMNS)
    assert result.player_id.dtype == original.player_id.dtype
    context_columns = [column for column in original if column != "player_id"]
    pd.testing.assert_frame_equal(result[context_columns], original[context_columns])
    pd.testing.assert_index_equal(result.index, original.index)
    pd.testing.assert_frame_equal(original, before)
    pd.testing.assert_frame_equal(source, source_before)
    assert result.identity_source_sha256.eq(SHA).all() and result.identity_adapter_version.eq(VERSION).all()
    assert receipt["changed_player_ids"] == 2
    assert receipt["registry_verified_or_resolved_rows"] == 3
    assert receipt["unresolved_or_unverified_rows"] == 2
    again, replay = resolve_query_identities(original, source, identity_sha256=SHA)
    pd.testing.assert_frame_equal(result, again)
    assert receipt == replay
    # Only aggregate counts and hashes, never player IDs or aliases, enter the receipt.
    body = json.dumps(receipt, sort_keys=True, allow_nan=False)
    assert "00-0000001" not in body and "sleeper:123" not in body


@pytest.mark.parametrize("player", ["sleeper:0123", "sleeper:１２３", "sleeper:١٢٣", "sleeper:123 ",
    " sleeper:123", "Sleeper:123", "sleeper:", "sleeper:123.0", "\t00-0000001", "00-0000001\t",
    "\u00a000-0000001\u00a0", "00- 0000001", "00-００００００１", " 00-0000009 "])
def test_no_fuzzy_numeric_unicode_or_generic_whitespace_normalization(player):
    result, receipt = resolve_query_identities(query([player]), registry([exact()]), identity_sha256=SHA)
    assert result.player_id.iloc[0] == player
    assert receipt["registry_verified_or_resolved_rows"] == 0


def test_leading_zero_sleeper_text_resolves_only_its_exact_registered_alias():
    result, _ = resolve_query_identities(query(["sleeper:00123", "sleeper:123"]),
        registry([exact(sleeper="00123")]), identity_sha256=SHA)
    assert result.player_id.tolist() == ["00-0000001", "sleeper:123"]


@pytest.mark.parametrize("rows", [
    [exact(), exact("00-0000002", "123")],
    [exact(), exact("00-0000001", "456")],
    [exact(), ("00-0000001", None, "ambiguous_source_binding")],
    [exact(), (None, "123", "source_exact_binding")],
    [exact(), ("not-gsis", "123", "source_exact_binding")],
    [exact(), ("00-0000001", None, "source_exact_binding")],
    [exact(), ("00-0000001", "123", "no_sleeper_binding")],
])
def test_conflicting_or_unusable_registry_rows_quarantine_affected_alias_only(rows):
    rows = rows + [exact("00-0000003", "789")]
    result, receipt = resolve_query_identities(query(["sleeper:123", "sleeper:789"]), registry(rows), identity_sha256=SHA)
    assert result.player_id.tolist() == ["sleeper:123", "00-0000003"]
    assert result.identity_resolution_state.iloc[0] == "unresolved_ambiguous_registry_binding"
    assert receipt["registry"]["quarantined_rows"] >= 1


def test_unusable_rows_are_retained_in_aggregate_and_identical_rows_are_harmless():
    source = registry([exact(), exact(), (None, None, "no_sleeper_binding"),
        ("bad-gsis", None, "source_exact_binding"), ("00-0000002", None, "source_exact_binding")])
    result, receipt = resolve_query_identities(query(["sleeper:123", " 00-0000002 ", "00-0000009"]), source, identity_sha256=SHA)
    assert result.player_id.tolist() == ["00-0000001", "00-0000002", "00-0000009"]
    assert receipt["registry"]["identical_duplicate_rows"] == 1
    assert receipt["registry"]["unusable_rows"] == 3
    assert result.identity_resolution_state.iloc[2] == "unverified_gsis_not_in_registry"


@pytest.mark.parametrize("column,value", [("player_id", 123), ("sleeper_id", 123), ("sleeper_id", True),
    ("identity_status", None), ("identity_status", "untrusted"), ("identity_status", 3), ("player_id", ["00-0000001"])])
def test_nonmissing_nontext_registry_values_and_unknown_status_fail_closed(column, value):
    source = registry([exact()]).astype(object)
    source.at[0, column] = value
    with pytest.raises(ValueError):
        resolve_query_identities(query(["sleeper:123"]), source, identity_sha256=SHA)


@pytest.mark.parametrize("kind", ["input", "canonical_sleeper", "canonical_ascii_space"])
def test_same_game_collisions_never_drop_or_select_rows(kind):
    players = {"input": ["sleeper:123", "sleeper:123"], "canonical_sleeper": ["sleeper:123", "00-0000001"],
        "canonical_ascii_space": [" 00-0000001 ", "00-0000001"]}[kind]
    original = query(players, ["same-fictional-game"] * 2)
    before = original.copy(deep=True)
    with pytest.raises(ValueError, match="duplicate input|canonical same-game"):
        resolve_query_identities(original, registry([exact()]), identity_sha256=SHA)
    pd.testing.assert_frame_equal(before, original)


def test_schema_reserved_fields_query_types_and_source_hash_fail_closed():
    valid = query(["sleeper:123"])
    for field in ("pass_yd", "f_player_pass_yd_mean3", *OUTPUT_COLUMNS):
        changed = valid.assign(**{field: "fictional"})
        with pytest.raises(ValueError):
            resolve_query_identities(changed, registry([exact()]), identity_sha256=SHA)
    for field in ("player_id", "game_id"):
        changed = valid.copy()
        changed[field] = 123
        with pytest.raises(ValueError):
            resolve_query_identities(changed, registry([exact()]), identity_sha256=SHA)
    with pytest.raises(ValueError, match="unknown"):
        resolve_query_identities(valid.assign(participation_state="played"), registry([exact()]), identity_sha256=SHA)
    for invalid in ("a" * 63, "A" * 64, " " + SHA, 123):
        with pytest.raises(ValueError, match="SHA256"):
            resolve_query_identities(valid, registry([exact()]), identity_sha256=invalid)
    with pytest.raises(ValueError, match="registry"):
        resolve_query_identities(valid, registry([exact()]).assign(player_name="forbidden"), identity_sha256=SHA)


def test_empty_query_and_registry_keep_exact_schema_and_deterministic_receipt():
    empty = query([])
    source = registry([])
    first, receipt = resolve_query_identities(empty, source, identity_sha256=SHA)
    second, replay = resolve_query_identities(empty, source, identity_sha256=SHA)
    pd.testing.assert_frame_equal(first, second)
    assert len(first) == 0 and receipt == replay and receipt["input_rows"] == receipt["output_rows"] == 0


@pytest.mark.parametrize("player", ["", " ", "\t", "\u00a0"])
def test_empty_or_whitespace_only_player_identity_is_not_a_stable_namespace(player):
    with pytest.raises(ValueError, match="player_id must be nonempty"):
        resolve_query_identities(query([player]), registry([exact()]), identity_sha256=SHA)
