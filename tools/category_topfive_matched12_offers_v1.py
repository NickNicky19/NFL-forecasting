"""Outcome-blind, separately versioned line-only offered-board preparation.

Consumes authenticated normalized rows or exact identity-bound archived site
metadata. No fitting, outcomes, forecast values, network, storage or execution
on import. The original market adapter/canonicalizer are never modified.
"""
from __future__ import annotations

import hashlib
import json
import math
import numbers
import re

VERSION = "matched12-line-only-primary-v1-20261030"
HORIZON = "HISTORICAL_LEFT_LIMIT_KICKOFF_RECONSTRUCTION"
NUMERIC = ("pass_yd", "pass_td", "pass_cmp", "pass_att", "pass_int", "rush_yd",
           "rush_att", "rec", "rec_yd", "rush_rec_yd")
BOOKS = (68, 69, 79)
KEY = ("season", "week", "game_id", "player_id", "target", "horizon_id")
BAD_COLUMNS = {"actual", "actual_value", "outcome", "result", "win_loss", "roi",
               "profit", "final_score", "final_home_score", "final_away_score",
               *NUMERIC, "fantasy_ppr", "rec_tgt"}
GSIS = re.compile(r"00-[0-9]{7}\Z", re.ASCII)
SHA = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
SLEEPER = re.compile(r"[0-9]+\Z", re.ASCII)
RESOLVED = {"verified_registry_gsis", "resolved_registry_ascii_space_gsis",
            "resolved_source_exact_sleeper"}
SITE_BINDING_COLUMNS = {
    "season", "week", "source_game_id", "source_player_id", "game_id", "player_id",
    "team", "opponent", "position", "kickoff_utc", "identity_resolution_state",
    "identity_source_sha256", "identity_adapter_version", "event_crosswalk_sha256"}


def require(ok, text):
    if not ok:
        raise ValueError(text)


def finite(value):
    return not isinstance(value, bool) and isinstance(value, numbers.Real) and math.isfinite(float(value))


def reason_tokens(value):
    require(isinstance(value, str), "source rejection reasons must remain exact text")
    return set(filter(None, value.split(";")))


def _sha(value):
    return isinstance(value, str) and SHA.fullmatch(value) is not None


def _clock(value, *, aware):
    import pandas as pd
    try:
        stamp = pd.Timestamp(value)
        if pd.isna(stamp) or (stamp.tzinfo is not None) != aware:
            return None
        return stamp
    except (TypeError, ValueError):
        return None


def _price(value):
    # Invalid prices remain invalid; no conventional price is substituted.
    if not finite(value) or not float(value).is_integer() or -100 < value < 100:
        return None
    return float(value)


def _decimal(value):
    return 1 + value / 100 if value > 0 else 1 + 100 / abs(value)


def _public_key(row):
    values = [row[name] for name in KEY]
    return hashlib.sha256(json.dumps(values, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def prepare_annual_line_only(rows, *, admitted_source_sha256s):
    """Return primary/per-book/event lines, rejected rows and safe counts.

    ``rows`` is the unchanged retained normalizer output. A rejection set of
    exactly {invalid_american_odds} is the only newly admitted failure. Price
    qualification and settlement remain independent from finite-line usability.
    """
    import pandas as pd
    import numpy as np
    from nfl_lab import historical_market_comparison as old

    needed = {"season", "week", "game_id", "player_id", "team", "opponent", "position",
              "kickoff_utc", "target", "period", "side", "line", "american_odds", "book_id",
              "book_kind", "source_collection_naive", "source_eligible_exploratory", "identity_status",
              "duplicate_status", "source_row_number", "source_sha256", "source_member", "rejection_reasons"}
    require(needed <= set(rows), "normalized source schema incomplete")
    require(not BAD_COLUMNS.intersection(rows.columns), "outcome/statistic columns forbidden in offer preparation")
    require(admitted_source_sha256s and all(_sha(x) for x in admitted_source_sha256s), "authenticated source digests required")
    require(not rows.duplicated(["source_sha256", "source_row_number"]).any(), "repeated original source ordinal")
    work = rows.copy(deep=True)
    exclusions = []
    accepted = []
    for index, row in work.iterrows():
        failure = []
        reasons = reason_tokens(row.rejection_reasons)
        price_only = reasons == {"invalid_american_odds"}
        if reasons - {"invalid_american_odds"}: failure.append("ORIGINAL_NONPRICE_REJECTION_RETAINED")
        flag = row.source_eligible_exploratory
        if not isinstance(flag, (bool, np.bool_)):
            failure.append("UNKNOWN_OR_NONBOOLEAN_SOURCE_ELIGIBILITY")
        elif not reasons and not bool(flag):
            failure.append("SOURCE_ELIGIBILITY_FLAG_CONTRADICTION")
        if row.season != 2026 or row.week not in range(1, 8): failure.append("OUTSIDE_REGISTERED_2026_W1_W7")
        if row.source_sha256 not in admitted_source_sha256s: failure.append("UNADMITTED_SOURCE_DIGEST")
        if row.identity_status != "source_gsis_exact_historical_roster_schedule": failure.append("UNQUALIFIED_CANONICAL_IDENTITY")
        if row.duplicate_status not in ("unique", "exact_duplicate_representative"): failure.append("ORIGINAL_DUPLICATE_REJECTION_RETAINED")
        if row.book_kind != "named" or row.book_id not in BOOKS: failure.append("NOT_PERMITTED_NAMED_BOOK")
        if row.period != "event": failure.append("NOT_FULL_EVENT")
        if not isinstance(row.player_id, str) or not GSIS.fullmatch(row.player_id): failure.append("INVALID_CANONICAL_PLAYER")
        if any(not isinstance(row[k], str) or not row[k] for k in ("game_id", "team", "opponent", "position", "source_member")):
            failure.append("MISSING_CANONICAL_CONTEXT")
        if _clock(row.kickoff_utc, aware=True) is None: failure.append("UNQUALIFIED_KICKOFF_CLOCK")
        collected = _clock(row.source_collection_naive, aware=False)
        if collected is None: failure.append("UNQUALIFIED_OR_MISSING_NAIVE_COLLECTION_CLOCK")
        if not finite(row.line): failure.append("MISSING_NONFINITE_LINE")
        if row.target in NUMERIC:
            if row.side not in ("over", "under"): failure.append("UNSUPPORTED_NUMERIC_SIDE")
        elif row.target == "anytime_td":
            if row.side != "noside" or row.line != 0: failure.append("UNSUPPORTED_ATD_ENCODING")
        else: failure.append("UNSUPPORTED_MARKET_NO_INVENTED_TARGET_OR_CHART_OFFER")
        if failure:
            excluded = row.to_dict(); excluded["line_only_rejection_reasons"] = ";".join(failure); exclusions.append(excluded)
        else:
            item = row.to_dict(); item["line_only_price_admitted"] = price_only
            item["collector_sort"] = collected.isoformat(); accepted.append(item)

    columns = list(needed) + ["line_only_price_admitted", "collector_sort"]
    good = pd.DataFrame(accepted, columns=list(dict.fromkeys(columns)))
    quotes = []
    group = ["season", "week", "game_id", "player_id", "target", "book_id", "collector_sort", "line"]
    pair_ambiguous_rows = 0
    if len(good):
        for _, members in good.groupby(group, sort=False, dropna=False):
            target = members.iloc[0].target
            sides = ["noside"] if target == "anytime_td" else ["over", "under"]
            if any(int(members.side.eq(s).sum()) > 1 for s in sides):
                pair_ambiguous_rows += len(members)
                for _, row in members.iterrows():
                    item = row.to_dict(); item["line_only_rejection_reasons"] = "AMBIGUOUS_SAME_CLOCK_LINE_SIDE"; exclusions.append(item)
                continue
            first = members.sort_values("source_row_number", kind="stable").iloc[0]
            side_rows = {s: members.loc[members.side.eq(s)].iloc[0] if members.side.eq(s).any() else None for s in sides}
            over = side_rows.get("over", side_rows.get("noside")); under = side_rows.get("under")
            po = _price(over.american_odds) if over is not None else None
            pu = _price(under.american_odds) if under is not None else None
            usable_o = po is not None and abs(po) < 10000
            usable_u = pu is not None and abs(pu) < 10000
            both = target != "anytime_td" and over is not None and under is not None
            fair = (1/_decimal(po))/(1/_decimal(po)+1/_decimal(pu)) if both and usable_o and usable_u else None
            quote = {k: first[k] for k in ("season", "week", "game_id", "player_id", "team", "opponent", "position", "kickoff_utc", "target", "book_id", "source_sha256", "source_member")}
            quote.update(horizon_id=HORIZON, source_policy_id=VERSION+":ANNUAL_NAMED_NJ", source_stream="ANNUAL_NAMED_NJ",
                line=None if target == "anytime_td" else float(first.line), source_line=float(first.line), source_collection_naive=first.collector_sort,
                source_row_number=int(first.source_row_number), over_source_row_number=int(over.source_row_number) if over is not None else None,
                under_source_row_number=int(under.source_row_number) if under is not None else None,
                over_offer_present=over is not None, under_offer_present=under is not None,
                american_over_raw=over.american_odds if over is not None else None, american_under_raw=under.american_odds if under is not None else None,
                decimal_over=_decimal(po) if usable_o else None, decimal_under=_decimal(pu) if usable_u else None,
                over_price_qualified=usable_o, under_price_qualified=usable_u, valid_two_sided_prices=both and usable_o and usable_u,
                source_pair_fair_over=fair, pair_priority=0 if fair is not None else 1 if usable_o or usable_u else 2 if both else 3,
                even_distance=abs(fair-.5) if fair is not None else 0., line_only_price_admitted=bool(members.line_only_price_admitted.any()),
                original_rejection_reasons=";".join(sorted({r for text in members.rejection_reasons for r in reason_tokens(text)})),
                source_quote_time=None, quote_timing_status="TIMING_UNVERIFIED_RETROSPECTIVE_COLLECTION_CLOCK_NOT_QUOTE_TIME",
                cutoff_qualified=False, venue_settlement_status="UNQUALIFIED_SOURCE_RULES", market_probability_eligible=False,
                event_definition="at_least_one_rushing_or_receiving_td_SOURCE_RULE_UNVERIFIED" if target == "anytime_td" else "ordinary_statistical_threshold_only")
            quotes.append(quote)
    all_quotes = pd.DataFrame(quotes)
    if len(all_quotes):
        # Reuse the old, outcome-free threshold-coherence helper on actual valid prices only.
        pairs = all_quotes.loc[all_quotes.source_pair_fair_over.notna() & all_quotes.target.ne("anytime_td")]
        groups = ["season", "week", "game_id", "player_id", "target", "source_collection_naive", "book_id"]
        bad = old.crossing_mask(pairs, groups, "source_pair_fair_over") if len(pairs) else None
        if bad is not None and bad.any():
            at = bad.index[bad]; all_quotes.loc[at, "source_pair_fair_over"] = None
            all_quotes.loc[at, "pair_priority"] = 2; all_quotes.loc[at, "even_distance"] = 0.
        ordered = all_quotes.sort_values(["season", "week", "game_id", "player_id", "target", "book_id", "source_collection_naive", "pair_priority", "even_distance", "source_line", "source_row_number"], kind="stable")
        per_book = ordered.drop_duplicates(["season", "week", "game_id", "player_id", "target", "book_id"]).copy()
        per_book["book_priority"] = per_book.book_id.map({b:i for i,b in enumerate(BOOKS)})
        primary = per_book.sort_values(list(KEY)+["book_priority"], kind="stable").drop_duplicates(list(KEY)).copy()
        primary["opportunity_key"] = primary.apply(_public_key, axis=1)
        numeric = primary.loc[primary.target.isin(NUMERIC)].reset_index(drop=True)
        events = primary.loc[primary.target.eq("anytime_td")].reset_index(drop=True)
    else:
        per_book = primary = numeric = events = all_quotes.copy()
    return {"primary": numeric, "event_offers": events, "per_book": per_book, "all_quotes": all_quotes,
        "excluded": pd.DataFrame(exclusions), "audit": {"version":VERSION,"input_rows":len(rows),"line_eligible_source_rows":len(good),
        "primary_numeric_opportunities":len(numeric),"primary_ATD_event_offers":len(events),"excluded_rows":len(exclusions),
        "pair_ambiguous_source_rows":pair_ambiguous_rows,"retained_eligible_source_rows_after_pairing":len(good)-pair_ambiguous_rows,
        "cutoff_qualified":0,"new_probability_forecasts":0,"new_model_inference":0}}


def prepare_site_line_only(archive, bindings, *, expected_binding_sha256, source_sha256):
    """Full original props, never filtered by lean/highlight/outcome/late flag.

    Root supplies authenticated identity metadata generated by the existing
    source-qualified identity adapter and qualified event crosswalk. This API
    never resolves an ID from a name or today's team.
    """
    import pandas as pd
    require(set(bindings)==SITE_BINDING_COLUMNS, "exact source-only site binding schema required")
    require(not BAD_COLUMNS.intersection(bindings.columns), "outcomes forbidden in identity bindings")
    require(_sha(expected_binding_sha256) and _sha(source_sha256), "exact input digests required")
    serial = bindings.to_json(orient="table", date_format="iso", index=False, force_ascii=True).encode()
    require(hashlib.sha256(serial).hexdigest()==expected_binding_sha256,"site identity binding digest mismatch")
    require(archive.get("season")==2026 and archive.get("week") in range(4,8),"site source scope is 2026 Weeks4-7")
    groups = bindings.groupby(["season","week","source_game_id","source_player_id"],sort=False,dropna=False)
    lookup = {}
    for key, group in groups:
        distinct=group.drop_duplicates()
        lookup[key]=distinct.iloc[0] if len(distinct)==1 else None
    game_lookup={}
    for game in archive.get("games",[]):game_lookup.setdefault(game.get("id"),[]).append(game)
    all_rows=[];excluded=[]
    for player_ordinal,p in enumerate(archive.get("players",[])):
        binding=lookup.get((2026,archive["week"],p.get("game_id"),p.get("id")))
        errors=[]
        if binding is None:errors.append("MISSING_OR_AMBIGUOUS_EXACT_IDENTITY_BINDING")
        else:
            if binding.identity_resolution_state not in RESOLVED or binding.identity_adapter_version!="source-qualified-query-identity-v1":errors.append("UNQUALIFIED_IDENTITY_ADAPTER_STATE")
            if not _sha(binding.identity_source_sha256) or not _sha(binding.event_crosswalk_sha256):errors.append("MISSING_AUTHENTICATED_IDENTITY_EVENT_REFERENCES")
            if not isinstance(binding.player_id,str) or not GSIS.fullmatch(binding.player_id):errors.append("INVALID_CANONICAL_GSIS")
            if not isinstance(binding.source_player_id,str) or not SLEEPER.fullmatch(binding.source_player_id):errors.append("INVALID_SOURCE_SLEEPER_ID")
            if any(p.get(a)!=binding[b] for a,b in (("team","team"),("opp","opponent"),("pos","position"))):errors.append("ORIGINAL_CONTEXT_DIFFERS_FROM_BINDING")
            games=game_lookup.get(p.get("game_id"),[])
            if len(games)!=1:errors.append("MISSING_OR_AMBIGUOUS_SOURCE_EVENT")
            else:
                g=games[0];kick=_clock(g.get("kickoff"),aware=True);bound=_clock(binding.kickoff_utc,aware=True)
                if kick is None or bound is None or kick!=bound:errors.append("SOURCE_BINDING_KICKOFF_MISMATCH")
                if p.get("team") not in (g.get("home"),g.get("away")) or p.get("opp") not in (g.get("home"),g.get("away")) or p.get("team")==p.get("opp"):errors.append("SOURCE_GAME_TEAM_OPPONENT_MISMATCH")
        for prop_ordinal,q in enumerate(p.get("props",[])):
            reason=list(errors)
            if q.get("key") not in NUMERIC:reason.append("NO_SUPPORTED_NUMERIC_MARKET")
            if q.get("line_from") not in ("dk","sleeper"):reason.append("NOT_RECORDED_DK_OR_CONTEST_LINE")
            if not finite(q.get("line")):reason.append("MISSING_NONFINITE_RECORDED_LINE")
            original={"source_player_ordinal":player_ordinal,"source_prop_ordinal":prop_ordinal,
                "source_player_id":p.get("id"),"source_game_id":p.get("game_id"),"target":q.get("key"),
                "line":q.get("line"),"recorded_line_source":q.get("line_from"),"original_recorded_lean":q.get("lean"),
                "source_late_flag":p.get("late"),"archive_saved_at":archive.get("saved_at"),"source_sha256":source_sha256}
            if reason:excluded.append({**original,"line_only_rejection_reasons":";".join(reason)});continue
            original.update({k:binding[k] for k in ("season","week","game_id","player_id","team","opponent","position","kickoff_utc","identity_source_sha256","event_crosswalk_sha256")})
            original.update(horizon_id=HORIZON,source_policy_id=VERSION+":SITE_"+q["line_from"].upper(),
                source_stream="SITE_RECORDED_DK_JURISDICTION_UNKNOWN" if q["line_from"]=="dk" else "SITE_RECORDED_CONTEST_THRESHOLD_NOT_SPORTSBOOK_PRICE",
                quote_timing_status="TIMING_UNVERIFIED_ARCHIVE_SAVE_IS_NOT_ORIGINAL_QUOTE_OR_ISSUE_TIME",source_quote_time=None,
                cutoff_qualified=False,venue_settlement_status="UNQUALIFIED_SOURCE_RULES",book_id=None,
                decimal_over=None,decimal_under=None,market_probability_eligible=False,
                identity_adapter_version=binding.identity_adapter_version,identity_resolution_state=binding.identity_resolution_state)
            all_rows.append(original)
    frame=pd.DataFrame(all_rows)
    if len(frame):
        frame=frame.sort_values(list(KEY)+["source_player_ordinal","source_prop_ordinal"],kind="stable")
        # Original archive order is the predeclared tie, never an outcome or favorable line.
        dk=frame.loc[frame.recorded_line_source.eq("dk")].drop_duplicates(list(KEY)).copy()
        contest=frame.loc[frame.recorded_line_source.eq("sleeper")].drop_duplicates(list(KEY)).copy()
        for f in (dk,contest):f["opportunity_key"]=f.apply(_public_key,axis=1)
    else:dk=contest=frame.copy()
    return {"primary_dk":dk.reset_index(drop=True),"secondary_contest":contest.reset_index(drop=True),"all_lines":frame,
        "excluded":pd.DataFrame(excluded),"audit":{"version":VERSION,"original_players":len(archive.get("players",[])),
        "primary_DK_opportunities":len(dk),"secondary_contest_opportunities":len(contest),"excluded_rows":len(excluded),
        "lean_or_TopPick_filter":False,"late_flag_used_to_remove_lines":False,"cutoff_qualified":0}}


def combine_source_fallback(annual_primary, site_dk):
    """One model-independent primary key; annual available, then recorded DK.

    Sources/contract/timing strata remain explicit, including overlaps in W4/5.
    Contest thresholds never silently enter this headline source fallback.
    """
    import pandas as pd
    for frame in (annual_primary,site_dk):
        if len(frame):
            require(set(KEY)<=set(frame),"primary offer keys missing")
            require(not frame.duplicated(list(KEY)).any(),"duplicate within source primary")
            require(frame.season.eq(2026).all() and frame.week.isin(range(1,8)).all(),"outside fixed primary comparison")
    a=annual_primary.copy();b=site_dk.copy();a["source_fallback_priority"]=0;b["source_fallback_priority"]=1
    full=pd.concat([a,b],ignore_index=True)
    if not len(full):return full
    out=full.sort_values(list(KEY)+["source_fallback_priority"],kind="stable").drop_duplicates(list(KEY)).reset_index(drop=True)
    require(not out.duplicated(list(KEY)).any(),"model-independent board uniqueness failed")
    out["primary_board_policy"]=VERSION+":ANNUAL_THEN_RECORDED_DK_SOURCE_FALLBACK"
    return out
