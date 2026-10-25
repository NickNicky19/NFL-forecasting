"""Source-bound inputs for one exposed dynamic-opportunity reconstruction.

No acquisition, fitting, scoring, storage writes or operational activation.
The caller supplies unchanged owned-reference authentication and an exact
sealed read plan. All-position sums are recorded-credit proxies, not NFL totals.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from numbers import Real
from pathlib import Path
from zoneinfo import ZoneInfo

from .dynamic_opportunity_core import TASK_ROLES
from .state import digest, utc

VERSION = "dynamic-opportunity-source-v2-20261024"
YEARS = tuple(range(2019, 2025))
TASK_FIELDS = {"rush_att": ("carries", "rush_att"), "rec_tgt": ("targets", "rec_tgt")}
CALENDAR_COLUMNS = ("game_id", "season", "week", "game_type", "gameday", "gametime", "away_team", "home_team")
STAT_COLUMNS = ("player_id", "season", "week", "season_type", "team", "carries", "targets", "receptions", "receiving_yards")
ROSTER_COLUMNS = ("gsis_id", "season", "week", "game_type", "team", "position", "status")
HISTORY_COLUMNS = ("player_id", "season", "week", "game_id", "team", "opponent", "position", "kickoff_utc",
                   "outcome_available_utc", "participation_state", "participation_evidence", "source_policy",
                   "stats_observed", "rush_att", "rec_tgt", "rec", "rec_yd")
CONTEXT_COLUMNS = ("season", "week", "game_id", "player_id", "team", "opponent", "position", "kickoff_utc",
                   "cutoff_utc", "outcome_available_utc", "f_team_rush_att_mean3")
TEAM_ALIASES = {"LA": "LAR", "STL": "LAR", "SD": "LAC", "OAK": "LV"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def text(value):
    return isinstance(value, str) and bool(value.strip())


def canonical_team(value):
    require(text(value), "explicit source team required")
    return TEAM_ALIASES.get(value, value)


def finite_count(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0 and value == math.floor(value)


def missing_value(value):
    """Only absent values and numeric IEEE NaN are missing, never zero."""
    return value is None or (isinstance(value, Real) and value != value)


def calendar_rows(records):
    """Reproduce the source normalizer's REG calendar; no score/weather fields."""
    result = []
    for row in records:
        require(set(row) == set(CALENDAR_COLUMNS), "exact approved calendar projection required")
        year, week = int(row["season"]), int(row["week"])
        if year not in YEARS or row["game_type"] != "REG":
            continue
        local = datetime.fromisoformat(str(row["gameday"]) + "T" + str(row["gametime"]))
        require(local.tzinfo is None, "original local calendar time required")
        zone = ZoneInfo("America/New_York")
        first, second = local.replace(tzinfo=zone, fold=0), local.replace(tzinfo=zone, fold=1)
        require(first.utcoffset() == second.utcoffset()
                and first.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None) == local,
                "ambiguous or nonexistent schedule clock")
        kickoff = first.astimezone(timezone.utc)
        require(text(row["game_id"]) and 1 <= week <= 18, "calendar identity invalid")
        for own, other in (("home_team", "away_team"), ("away_team", "home_team")):
            result.append(dict(game_id=row["game_id"], season=year, week=week, season_type="REG",
                               team=canonical_team(row[own]), opponent=canonical_team(row[other]),
                               kickoff_utc=kickoff.isoformat(), available_utc=(kickoff + timedelta(days=7)).isoformat()))
    # Reuse the unchanged strict identity/reciprocal calendar validator.
    from .dynamic_opportunity_history import _calendar
    _calendar(result)
    return result


def index_calendar(calendar):
    from .dynamic_opportunity_history import _calendar
    return _calendar(calendar)


def allowed_periods(calendar, cutoff):
    """Exact source predicates; equality at the seven-day boundary is excluded."""
    cutoff = utc(cutoff)
    return sorted({(g["season"], g["week"], g["team"]) for g in calendar
                   if utc(g["available_utc"]) < cutoff})


def source_identity(row, kind):
    return (row["season"], row["week"], row["season_type" if kind == "statistics" else "game_type"],
            canonical_team(row["team"]), row["player_id" if kind == "statistics" else "gsis_id"])


def attach_row_pointers(identity_rows, projected_rows, *, body_sha256, kind, periods):
    """Authenticate filtered order against original identity-only row ordinals.

    Duplicate identities remain separate occurrences and reach later ambiguity
    gates. The identity projection must be read before any primitive projection.
    """
    require(kind in {"statistics", "rosters"}, "declared source kind required")
    wanted = set(periods)
    expected = [(i, row) for i, row in enumerate(identity_rows)
                if row["season_type" if kind == "statistics" else "game_type"] == "REG"
                and (row["season"], row["week"], canonical_team(row["team"])) in wanted]
    require(len(expected) == len(projected_rows), "filtered physical source inventory changed")
    result = []
    for (ordinal, identity), row in zip(expected, projected_rows):
        require(source_identity(identity, kind) == source_identity(row, kind), "physical source row order/identity changed")
        result.append({**row, "source_row_id": body_sha256 + ":row:" + str(ordinal),
                       "source_body_sha256": body_sha256})
    return result


def credit_rows(records, calendar, *, task, cutoff, statistics_sha256_by_season):
    """Access a primitive only after its exact calendar availability gate."""
    require(task in TASK_FIELDS, "declared task required")
    periods, _ = index_calendar(calendar)
    output, unassigned = [], []
    raw_field = TASK_FIELDS[task][0]
    for row in records:
        require(row["season"] in YEARS and row["season_type"] == "REG", "protected/non-REG statistic row")
        require(row.get("source_body_sha256") == statistics_sha256_by_season[str(row["season"])], "source body version changed")
        team = canonical_team(row["team"])
        game = periods.get((row["season"], row["week"], team))
        if game is None:
            unassigned.append({"source_row_id": row["source_row_id"], "reason": "unmapped_team_game"})
            continue
        if utc(game["available_utc"]) >= utc(cutoff):
            continue
        value = row.get(raw_field)
        missing = missing_value(value)
        support = "missing" if missing else "explicit_official_count"
        output.append(dict(source_row_id=row["source_row_id"], source_body_sha256=row["source_body_sha256"],
                           season=game["season"], week=game["week"], season_type="REG", game_id=game["game_id"],
                           team=team, player_id=row.get("player_id"), task=task, count=None if missing else value, count_support=support,
                           available_utc=game["available_utc"]))
    return output, unassigned


def membership_for_offer(offer, calendar, roster_records, *, membership_manifest_sha256):
    """Only an explicit Week1 anchor; no inferred first entry or transaction."""
    periods, games = index_calendar(calendar)
    cutoff = utc(offer["cutoff_utc"])
    player, team, year = offer["player_id"], offer["team"], offer["season"]
    observed = defaultdict(list); orphan = 0
    for row in roster_records:
        if row["season"] != year or row.get("gsis_id") != player:
            continue
        own = canonical_team(row["team"])
        game = periods.get((year, row["week"], own))
        if game is None:
            orphan += 1
            continue
        if row.get("game_type") != "REG" or utc(game["available_utc"]) >= cutoff:
            continue
        observed[(game["game_id"], own)].append(row)
    own_games = sorted((g for g in games.values() if g["season"] == year and g["team"] == team),
                       key=lambda g: (g["kickoff_utc"], g["game_id"]))
    anchor = next((g for g in own_games if g["week"] == 1), None)
    anchor_rows = [] if anchor is None else observed.get((anchor["game_id"], team), [])
    conflicts = any(own != team for _, own in observed)
    qualified = anchor is not None and len(anchor_rows) == 1 and not conflicts
    spell_id = digest(dict(player_id=player, team=team, season=year, boundary="explicit_week1_season_anchor",
                           membership_manifest_sha256=membership_manifest_sha256))
    spell = dict(state="qualified" if qualified else "unqualified", player_id=player, team=team, season=year,
                 spell_id=spell_id, boundary="season_start", started_utc=anchor["kickoff_utc"] if anchor else None,
                 membership_manifest_sha256=membership_manifest_sha256,
                 evidence="CURRENT_VINTAGE_EXPLICIT_WEEK1_MEMBERSHIP; not historical publication or transaction evidence")
    members = []
    for game in own_games:
        if utc(game["kickoff_utc"]) >= cutoff:
            continue
        records = observed.get((game["game_id"], team), [])
        ready = qualified and len(records) == 1
        members.append(dict(player_id=player, game_id=game["game_id"], team=team, spell_id=spell_id,
                            membership_manifest_sha256=membership_manifest_sha256,
                            membership_state="qualified_same_spell" if ready else "ambiguous_or_missing_membership",
                            source_row_ids=[r["source_row_id"] for r in records]))
    return spell, members, dict(anchor_records=len(anchor_rows), conflicting_team_membership=conflicts,
                                unmapped_membership_records=orphan, real_transaction_or_cold_start_qualified=False)


def qualified_player_rows(raw_records, history_records, calendar, *, task, cutoff):
    """Reuse the frozen permitted playing qualifier; never fill sparse fields."""
    require(task in TASK_FIELDS, "declared task required")
    periods, _ = index_calendar(calendar)
    raw = defaultdict(list)
    for row in raw_records:
        team = canonical_team(row["team"])
        raw[(row["season"], row["week"], team, row.get("player_id"))].append(row)
    result = []
    raw_field, normalized = TASK_FIELDS[task]
    for row in history_records:
        require(row["season"] in YEARS, "protected historical season")
        team = canonical_team(row["team"])
        game = periods.get((row["season"], row["week"], team))
        if game is None or utc(game["available_utc"]) >= utc(cutoff):
            continue
        require(row["game_id"] == game["game_id"] and row["opponent"] == game["opponent"]
                and utc(row["kickoff_utc"]) == utc(game["kickoff_utc"])
                and utc(row["outcome_available_utc"]) == utc(game["available_utc"]), "qualified history/calendar conflict")
        matches = raw.get((row["season"], row["week"], team, row["player_id"]), [])
        participation = row["participation_state"]
        require(participation in {"played", "unknown", "DNP"}, "invalid retained participation state")
        require(text(row.get("source_policy")), "qualified history source policy required")
        count = None; support = "missing"; reason = "missing_or_ambiguous_raw_record"
        if len(matches) == 1:
            explicit = matches[0].get(raw_field)
            qualified = row.get(normalized)
            if participation == "played":
                # Missing normalized support is not a contradictory finite
                # observation. Retain the slot without borrowing the raw count.
                for value in (explicit, qualified):
                    require(missing_value(value) or finite_count(value), "raw/qualified count support conflict")
                if missing_value(explicit):
                    reason = "missing_explicit_raw_count"
                elif missing_value(qualified):
                    reason = "missing_qualified_normalized_count"
                else:
                    require(explicit == qualified, "raw/qualified count support conflict")
                    count, support, reason = explicit, "explicit_value", "unchanged_qualified_played_explicit_raw_count"
            elif participation != "played":
                reason = "unknown_or_DNP_never_becomes_zero"
        result.append(dict(player_id=row["player_id"], game_id=game["game_id"], team=team, opponent=game["opponent"],
                           season=game["season"], week=game["week"], season_type="REG", kickoff_utc=game["kickoff_utc"],
                           available_utc=game["available_utc"], position=row["position"], task=task,
                           source_qualified=len(matches) == 1, participation_state=participation,
                           count=count, count_support=support, support_reason=reason,
                           source_row_ids=[r["source_row_id"] for r in matches]))
    return result


def seal_source_binding(plan, calendar, membership_manifest):
    return dict(availability_lane="reconstructed_kickoff_plus_7_days", statistics_lag_days=7, season_type="REG",
                source_policy_sha256=plan["source_policy"]["sha256"], source_manifest_sha256=plan["source_manifest"]["sha256"],
                calendar_sha256=plan["calendar"]["sha256"], calendar_rows_sha256=digest(calendar),
                membership_manifest_sha256=digest(membership_manifest), qualified_history_sha256=plan["qualified_history"]["sha256"],
                qualification_policy_sha256=plan["qualification_policy"]["sha256"],
                statistics_sha256_by_season={str(y): plan["statistics"][str(y)]["sha256"] for y in YEARS},
                calendar_inventory_complete=True)


class ProjectionSource:
    """Actual read prerequisite; unreachable without owned authentication.

    ``authenticator`` must be the frozen caller adapter around the unchanged
    validate_owned_references. No source/body/row is decoded by construction.
    """
    def __init__(self, plan, *, authenticator, reader=None):
        require(plan.get("state") == "FROZEN_ROOT_REVIEWER_SEALED" and plan.get("seal"), "actual source plan is not sealed")
        self.plan = deepcopy(plan)
        self.authenticator = authenticator
        self.reader = reader or self._arrow
        self.references = {r["path"]: r["sha256"] for r in plan["owned_inputs"]}
        require(len(self.references) == len(plan["owned_inputs"]), "duplicate source reference path")
        self.entry = authenticator(self.references)
        self.identity_cache = {}; self.cache = defaultdict(list); self.loaded = defaultdict(set)
        self.last_cutoff = None; self.read_audit = []

    @staticmethod
    def _arrow(path, columns, filters):
        import pyarrow.dataset as ds
        dataset = ds.dataset(path, format="parquet")
        require(set(columns) <= set(dataset.schema.names), "required projected source columns missing")
        predicate = None
        for conjunction in filters:
            term = ds.scalar(True) if not conjunction else None
            for field, op, value in conjunction:
                expr = ds.field(field).isin(value) if op == "in" else ds.field(field) == value
                term = expr if term is None else term & expr
            predicate = term if predicate is None else predicate | term
        require(predicate is not None, "explicit source predicates required")
        return dataset.to_table(columns=list(columns), filter=predicate, use_threads=False).to_pylist()

    def _project(self, ref, columns, filters, *, role):
        require(self.references.get(ref["path"]) == ref["sha256"], "read outside authenticated source bindings")
        if filters == [[]]:
            source_kinds = [kind for kind in ("statistics", "rosters")
                            if any(r["path"] == ref["path"] for r in self.plan[kind].values())]
            require(len(source_kinds) == 1 and role == "identity_only_physical_ordinal", "all-row read is identity-only")
            kind = source_kinds[0]
            expected = {"player_id" if kind == "statistics" else "gsis_id", "season", "week",
                        "season_type" if kind == "statistics" else "game_type", "team"}
            require(set(columns) == expected, "all-row projection cannot contain a primitive or other metadata")
        rows = self.reader(ref["path"], tuple(columns), filters)
        self.read_audit.append(dict(path=ref["path"], sha256=ref["sha256"], columns=list(columns),
                                    predicates=deepcopy(filters), role=role, returned_rows=len(rows)))
        return rows

    def advance(self, calendar, cutoff):
        stamp = utc(cutoff)
        require(self.last_cutoff is None or stamp >= self.last_cutoff, "source cutoffs must advance monotonically")
        self.last_cutoff = stamp
        eligible = allowed_periods(calendar, stamp)
        for year in YEARS:
            new = [p for p in eligible if p[0] == year and p not in self.loaded[year]]
            if not new:
                continue
            for kind, columnset in (("statistics", STAT_COLUMNS), ("rosters", ROSTER_COLUMNS)):
                ref = self.plan[kind][str(year)]
                season_kind = "season_type" if kind == "statistics" else "game_type"
                identity_columns = ("player_id" if kind == "statistics" else "gsis_id", "season", "week", season_kind, "team")
                if (kind, year) not in self.identity_cache:
                    self.identity_cache[kind, year] = self._project(ref, identity_columns,
                        [[]], role="identity_only_physical_ordinal")
                filters = []
                for _, week, team in new:
                    source_teams = [team] + [alias for alias, canonical in TEAM_ALIASES.items() if canonical == team]
                    filters.append([("season", "==", year), ("week", "==", week), (season_kind, "==", "REG"), ("team", "in", source_teams)])
                values = self._project(ref, columnset, filters, role="strictly_available_feature_or_prior")
                self.cache[kind].extend(attach_row_pointers(self.identity_cache[kind, year], values,
                    body_sha256=ref["sha256"], kind=kind, periods=new))
            filters = [[("season", "==", year), ("week", "==", week), ("team", "==", team)] for _, week, team in new]
            history = self._project(self.plan["qualified_history"], HISTORY_COLUMNS, filters, role="qualified_prior_or_feature")
            self.cache["qualified_history"].extend(history)
            self.loaded[year].update(new)
        return self.cache

    def query_context(self, year):
        require(year in (2020, 2021, 2022, 2023, 2024), "only registered development/forward context years")
        ref = self.plan["queries"].get(str(year), self.plan["accepted_features"])
        columns = list(CONTEXT_COLUMNS)
        return self._project(ref, columns, [[("season", "==", year)]], role="query_context_no_labels_or_participation")

    def calendar(self):
        ref = self.plan["calendar"]
        require(self.references.get(ref["path"]) == ref["sha256"], "calendar outside authenticated source bindings")
        with Path(ref["path"]).open(newline="") as stream:
            reader = csv.DictReader(stream)
            header = reader.fieldnames or ()
            require(len(header) == len(CALENDAR_COLUMNS) and set(header) == set(CALENDAR_COLUMNS),
                    "exact unique approved cached calendar header required")
            result = calendar_rows(list(reader))
        self.read_audit.append(dict(path=ref["path"], sha256=ref["sha256"], columns=list(CALENDAR_COLUMNS),
                                    role="calendar_metadata_only", returned_rows=len(result)))
        return result

    def close(self):
        return self.authenticator(self.references)


def historical_requests(offers, calendar, raw_records, roster_records, history_records, *, task, plan, replay_policy):
    """One common-cutoff batch; only the explicit new historical adapter runs."""
    require(offers and len({utc(o["cutoff_utc"]) for o in offers}) == 1, "one nonempty common-cutoff batch required")
    cutoff = offers[0]["cutoff_utc"]
    years = {g["season"] for g in calendar}
    require(len(years) == 1 and {o["season"] for o in offers} == years, "one complete source-season calendar per request batch")
    raw_records = [r for r in raw_records if r["season"] in years]
    roster_records = [r for r in roster_records if r["season"] in years]
    history_records = [r for r in history_records if r["season"] in years]
    membership_manifest = dict(version=VERSION, calendar_sha256=digest(calendar),
        source_rosters={str(y): plan["rosters"][str(y)]["sha256"] for y in YEARS},
        records=[{k: row.get(k) for k in (*ROSTER_COLUMNS, "source_row_id", "source_body_sha256")} for row in roster_records],
        availability="strict reconstructed kickoff+7days<query cutoff", boundary="explicit_week1_season_anchor_only")
    binding = seal_source_binding(plan, calendar, membership_manifest)
    derived, members, audits = [], [], []
    for offer in offers:
        spell, selected_members, audit = membership_for_offer(offer, calendar, roster_records,
            membership_manifest_sha256=binding["membership_manifest_sha256"])
        derived.append({**offer, "spell": spell, "task": task})
        members.extend(selected_members); audits.append(dict(offer_id=offer["offer_id"], **audit))
    # Distinct offers for a player share the exact membership record, never
    # inflate adapter multiplicity. Conflicting records remain separate.
    unique_members = {digest(row): row for row in members}
    credits, unassigned = credit_rows(raw_records, calendar, task=task, cutoff=cutoff,
                                     statistics_sha256_by_season=binding["statistics_sha256_by_season"])
    players = qualified_player_rows(raw_records, history_records, calendar, task=task, cutoff=cutoff)
    from .dynamic_opportunity_history import build_recorded_proxy_panel
    from .dynamic_opportunity_history_replay_v2 import build_historical_offer_windows
    panel = build_recorded_proxy_panel(calendar, credits, task=task, source_binding=binding,
        asof_utc=cutoff, requested_player_ids=[o["player_id"] for o in offers])
    result = build_historical_offer_windows(derived, calendar, list(unique_members.values()), players, panel,
        task=task, source_binding=binding, replay_policy=replay_policy)
    result.update(producer_version=VERSION, membership_manifest_sha256=binding["membership_manifest_sha256"],
                  producer_membership_audit=audits, unmapped_source_credit_rows=unassigned,
                  source_binding=binding, no_new_sparse_zero_semantics=True)
    return result


def offer_contexts(query_rows, calendar, *, query_reference, task):
    """Derived manifests retain original context/body pointers and clock values."""
    _, games = index_calendar(calendar)
    require(task in TASK_ROLES, "declared workload task required")
    result = []; seen = set()
    for ordinal, original in enumerate(query_rows):
        require(set(CONTEXT_COLUMNS) <= set(original), "original context/volume projection incomplete")
        key = tuple(original[k] for k in ("season", "week", "game_id", "player_id"))
        require(text(original["player_id"]) and key not in seen, "duplicate or missing original query identity")
        seen.add(key)
        game = games.get((original["game_id"], original["team"]))
        require(game is not None and all(original[k] == game[k] for k in ("season", "week", "opponent"))
                and utc(original["kickoff_utc"]) == utc(game["kickoff_utc"]), "query/calendar context conflict")
        require(utc(original["cutoff_utc"]) <= utc(original["kickoff_utc"]), "historical query after kickoff")
        item = {k: original[k] for k in CONTEXT_COLUMNS}
        for key in ("kickoff_utc", "cutoff_utc", "outcome_available_utc"):
            item[key] = utc(item[key]).isoformat()
        volume = item["f_team_rush_att_mean3"]
        if type(volume) in (int, float) and not math.isfinite(volume):
            item["f_team_rush_att_mean3"] = None
        item.update(offer_id=digest(dict(query_sha256=query_reference["sha256"], ordinal=ordinal, task=task)),
                    original_query_reference={**query_reference, "row_ordinal": ordinal},
                    season_type=game["season_type"], season_type_provenance="exact_bound_REG_calendar_join_not_persisted_query_default",
                    baseline_reference={"state": "REQUIRED_SEPARATE_EXACT_CATEGORY_CDF_BINDING"})
        result.append(item)
    require(len({r["offer_id"] for r in result}) == len(result), "duplicate derived original offers")
    return result
