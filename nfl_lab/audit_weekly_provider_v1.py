"""Private E7 provider adapter for audit_weekly_grade_v1.acquire.

ABI: Collector(storage=owned_storage, output=NEW_PRIVATE_PATH,
authenticate=LIVE_PARENT_CALLBACK)(grade.provider_request(...)) returns the
grade module's exact five-field observations document. The live parent callback
must authenticate the request and the owned source body/native receipt/URL/
clocks against its actual permitted-source execution/API evidence. JSON flags
and saved callback results grant no authority. Parent grade authentication and
fresh-reader durability are still separate requirements.

Only original live.fetch, live.schedule_games and scoring.stat_value are used.
No models, historical supplement loader, roster/players lookup, new scoring,
outcome resolution, public output or network runs on import. The adapter never
retries; the unchanged E7 downloader retains its at-most-three HTTP attempts.
Its native receipt does not record an HTTP status or authenticate publication
time. Neither is invented here: HTTP/API authentication belongs to the live
parent, and source_timestamp remains None. Missing/INA/gp=0 is not DNP or zero.
This source has no independently supported explicit-DNP parser.
The parent must run its existing native 180s/120CPU/512MiB worker envelope;
cooperative checks here cannot interrupt an in-flight frozen HTTP helper.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import re
import time

from . import audit_weekly_grade_v1 as grade, weekly_grading as grading
from . import gha_private_checkpoint as cp, private_draft_store as store, state
from . import live, scoring
from .operational_io import operational_io
from .operational_storage import OperationalStorage

VERSION = "audit-weekly-provider-v1"
ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "config/operational-source-policy-v2.json"
# The original numeric loader remains the producer's feature/source authority.
# This metadata-only copy is usable only while that exact validator is installed.
_SOURCE_LOADER_SHA256 = "069c498ebef85fee291f7f9913bebc6d157988d2242de5feb6b066d6ba68e11e"
_POLICY_ID = "permitted-operational-nfl-history-v2-20261023"
_SCHEDULE_COLUMNS = ["game_id", "season", "week", "game_type", "gameday", "gametime", "away_team", "home_team"]
_SOURCE_SPECS = {
    "schedules": ("schedules.csv", "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"),
    "players": ("players.parquet", "https://github.com/nflverse/nflverse-data/releases/download/players/players.parquet"),
    "statistics": ("stats_player_week_{season}.parquet", "https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_{season}.parquet"),
    "rosters": ("roster_weekly_{season}.parquet", "https://github.com/nflverse/nflverse-data/releases/download/weekly_rosters/roster_weekly_{season}.parquet"),
    "license": ("nflverse_LICENSE.md", "https://raw.githubusercontent.com/nflverse/nflverse-data/main/LICENSE.md"),
}
REQUEST_KEYS = {"schema_version", "scope", "source_policy_sha256", "as_of", "games", "opportunities", "retries", "fits", "research_or_tuning"}
GAME_KEYS = {"season", "week", "website_game_id", "game_id", "kickoff_utc", "home", "away"}
OPPORTUNITY_KEYS = set(grading.METADATA) | {"schema_version", "original_game_id", "website_game_id", "target", "offered_id",
    "identity_binding", "identity_binding_sha256", "bridge", "primary_role"}
BRIDGE_KEYS = {"gsis_id", "gsis_game_id", "sleeper_id", "website_player_id", "website_game_id", "team", "opponent",
    "kickoff_utc", "query_source_sha256", "schedule_source_sha256", "identity_binding_sha256"}
NATIVE_BRIDGE_KEYS = BRIDGE_KEYS | {"identity_bridge_kind", "actual_visible_board_compatibility"}
LIMITS = dict(games=576, periods=18, opportunities=18000, source_body_bytes=50 << 20,
    request_bytes=64 << 20, private_bytes=512 << 20, adapter_retries=0, fits=0, searches=0,
    wall_seconds=180, CPU_seconds=120, RSS_bytes=512 << 20, threads=2,
    native_downloader_attempts_per_URL=3)
_KEY = object()


class ProviderError(ValueError):
    """Fixed public-safe guards; never expose raw provider bodies/rows."""


def require(value, code):
    if not value:
        raise ProviderError(code)


def _load_source_policy(policy: Path | str | dict) -> dict:
    """The exact 069c loader's policy checks, without its numerical imports."""
    require(store.sha(store.read_local(ROOT / "nfl_lab/operational_sources.py", 2 << 20)) == _SOURCE_LOADER_SHA256,
        "ORIGINAL_SOURCE_POLICY_VALIDATOR_REQUIRED")
    if isinstance(policy, (str, Path)):
        body = Path(policy).read_bytes()
        result = json.loads(body)
        file_sha = hashlib.sha256(body).hexdigest()
    else:
        result = dict(policy)
        file_sha = result.get("_policy_sha256")
    clean = {k: v for k, v in result.items() if not k.startswith("_")}
    if clean.get("policy_id") != _POLICY_ID:
        raise ValueError("unsupported operational source policy")
    if set(clean.get("sources", {})) != set(_SOURCE_SPECS):
        raise ValueError("source policy whitelist changed")
    for kind, (name, url) in _SOURCE_SPECS.items():
        spec = clean["sources"][kind]
        if spec.get("name") != name or spec.get("url") != url:
            raise ValueError("source policy URL/name changed: " + kind)
    if clean["sources"]["schedules"].get("columns") != _SCHEDULE_COLUMNS:
        raise ValueError("schedule metadata columns changed")
    if clean.get("history", {}).get("statistics_lag_days") != 7 or clean["history"].get("season_type") != "REG":
        raise ValueError("unsupported availability/season-type policy")
    predicates = clean["history"].get("parquet_predicates", {})
    if predicates.get("statistics_season_type") != "season_type == REG" or predicates.get("roster_season_type") != "game_type == REG":
        raise ValueError("explicit REG parquet predicates required")
    canonical = hashlib.sha256((json.dumps(clean, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()).hexdigest()
    if file_sha and not isinstance(policy, (str, Path)) and result.get("_canonical_policy_sha256") != canonical:
        raise ValueError("normalized operational policy body changed")
    return {**clean, "_policy_sha256": file_sha or canonical, "_canonical_policy_sha256": canonical}


def pins():
    names = ("nfl_lab/audit_weekly_provider_v1.py", "tools/audit_weekly_provider_v1.py",
        "nfl_lab/audit_weekly_grade_v1.py", "nfl_lab/weekly_grading.py", "nfl_lab/scoring.py", "nfl_lab/live.py",
        "nfl_lab/data.py", "nfl_lab/operational_io.py", "nfl_lab/operational_storage.py",
        "nfl_lab/operational_sources.py", "config/operational-source-policy-v2.json")
    return {name:store.sha(store.read_local(ROOT/name, 2 << 20)) for name in names}


def validate_request(document, *, at):
    """Metadata only; never accept forecasts/labels or an endpoint from JSON."""
    require(type(document) is dict and set(document) == REQUEST_KEYS
        and document["schema_version"] == grade.VERSION+"-provider-request"
        and document["scope"] == "FIXED_COMPLETED_GAME_OPERATIONAL_GRADING_ONLY"
        and document["source_policy_sha256"] == cp.POLICY_SHA
        and type(document["retries"]) is int and document["retries"] == 0
        and type(document["fits"]) is int and document["fits"] == 0
        and document["research_or_tuning"] is False, "CLOSED_REGISTERED_E7_REQUEST_REQUIRED")
    require(state.utc(document["as_of"]) <= state.utc(at)
        and len(state.canonical(document)) <= LIMITS["request_bytes"], "ACTUAL_BOUNDED_REQUEST_CLOCK")
    games, rows = document["games"], document["opportunities"]
    require(type(games) is list and len(games) <= LIMITS["games"]
        and type(rows) is list and len(rows) <= LIMITS["opportunities"], "BOUNDED_COMPLETE_METADATA_NO_ROW_TRUNCATION")
    by_id = {}; periods = set()
    for game in games:
        require(type(game) is dict and set(game) == GAME_KEYS
            and type(game["season"]) is int and 2012 <= game["season"] <= state.utc(at).year
            and type(game["week"]) is int and 1 <= game["week"] <= 18
            and type(game["website_game_id"]) is str and re.fullmatch(r"[1-9][0-9]*",game["website_game_id"])
            and type(game["game_id"]) is str and 0 < len(game["game_id"]) <= 128
            and all(type(game[k]) is str and re.fullmatch(r"[A-Z]{1,4}",game[k]) for k in ("home", "away"))
            and game["home"] != game["away"]
            and all(live.TEAMS.get(game[k],game[k]) == game[k] for k in ("home", "away")), "EXACT_REGISTERED_GAME_METADATA")
        require(state.utc(game["kickoff_utc"]) < state.utc(document["as_of"]), "FUTURE_GAME_OUTCOME_REQUEST_FORBIDDEN")
        key = "espn:"+game["website_game_id"]
        require(key not in by_id, "DUPLICATE_REGISTERED_PROVIDER_GAME")
        by_id[key] = game; periods.add((game["season"],game["week"]))
    require(len(periods) <= LIMITS["periods"], "FINITE_REGISTERED_PERIODS")
    seen = {}
    if rows:
        try:
            grading.validate_collector_rows(rows)
        except (KeyError, TypeError, ValueError):
            raise ProviderError("EXACT_FROZEN_COLLECTOR_IDENTITIES_REQUIRED") from None
    for row in rows:
        require(set(row) == OPPORTUNITY_KEYS and row["target"] in grading.TARGETS
            and row["identity_binding"] == "frozen_exact_weekly_query_bridge"
            and type(row["primary_role"]) is bool, "CLOSED_ELEVEN_TARGET_OPPORTUNITY_METADATA")
        game = by_id.get(row["game_id"])
        require(game is not None and (row["season"],row["week"],row["original_game_id"])
            == (game["season"],game["week"],game["game_id"])
            and state.utc(row["kickoff_utc"]) == state.utc(game["kickoff_utc"])
            and {row["team"],row["opponent"]} == {game["home"],game["away"]}, "OPPORTUNITY_EXACT_REGISTERED_GAME_REQUIRED")
        b = row["bridge"]
        # Both the grade API's minimal frozen bridge and the actual native
        # producer's closed bridge are supported. Display-compatibility text
        # is not a proof of source identity, participation or website release.
        require(set(b) in (BRIDGE_KEYS,NATIVE_BRIDGE_KEYS) and b["website_player_id"] == row["sleeper_id"]
            and all(store.HASH.fullmatch(str(b[k])) for k in ("query_source_sha256", "schedule_source_sha256", "identity_binding_sha256")),
            "COMPLETE_SOURCE_BOUND_GSIS_SLEEPER_ESPN_BRIDGE")
        if set(b) == NATIVE_BRIDGE_KEYS:
            require(b["identity_bridge_kind"] == "EXACT_ORIGINAL_WEEKLY_ROSTER_AND_SCHEDULE_NOT_NAMES"
                and type(b["actual_visible_board_compatibility"]) is str and len(b["actual_visible_board_compatibility"]) <= 128,
                "EXACT_NATIVE_IDENTITY_BRIDGE_METADATA")
        identity = (row["game_id"],row["player_id"])
        require(identity not in seen or seen[identity] == row["sleeper_id"], "ONE_FROZEN_SLEEPER_PER_CANONICAL_PLAYER_GAME")
        seen[identity] = row["sleeper_id"]
    return deepcopy(document)


def _binding(storage, path, expected=None):
    ref = storage.validate_reference(path, expected)
    return {k:ref[k] for k in ("path", "bytes", "sha256")}


class Capture:
    """Live typed local evidence, not a serialized provider/durability permit."""
    def __init__(self, storage, root, completion, key):
        require(key is _KEY, "LIVE_PROVIDER_CAPTURE_REQUIRED")
        self.storage, self.root = storage, root
        self.document = deepcopy(completion); self.sha256 = state.digest(completion)

    def verify(self):
        require(self.sha256 == state.digest(self.document), "PROVIDER_CAPTURE_CHANGED")
        require(_binding(self.storage,self.root/"COMPLETION.json",self.sha256)["sha256"] == self.sha256
            and self.document["code_pins"] == pins(), "EXACT_PROVIDER_COMPLETION_AND_CODE_PINS")
        for ref in [self.document["request"], self.document["observations"]] + self.document["sources"]:
            require(Path(ref["path"]).is_relative_to(self.root), "CONFINED_PROVIDER_CAPTURE_GRAPH")
            require(_binding(self.storage, ref["path"], ref["sha256"]) == ref, "OWNED_PROVIDER_CAPTURE_GRAPH")
        return self

    def __reduce__(self):
        raise ProviderError("LIVE_PROVIDER_CAPTURE_CANNOT_BE_SERIALIZED")


class Collector:
    """One private owned E7 attempt, suitable for grade.acquire(collect=...).

    authenticate receives a closed live request with kind, inputs, their digest
    and the actual callback clock. In AUTHORIZE_REGISTERED_REQUEST it must bind
    the owned request to the genuine parent permit. In AUTHENTICATE_SOURCE_BODY
    it must bind the exact owned body/native receipt and source URL/clocks to
    the actual E7 transport/API evidence. COMPLETE_PROVIDER_OBSERVATIONS binds
    the resulting local file graph. Strict True is required each time; JSON is
    never execution authority. capture is set only after every gate succeeds.

    fetch is the original live.fetch seam; a parent may supply its already
    qualified E7 callable with that exact ABI. Never supply a JSON cache as an
    authenticator. Native E7 downloader receipts lack actual HTTP status; the
    adapter truthfully records None and delegates that proof to the parent.
    """
    def __init__(self, *, storage, output, authenticate, source_policy=POLICY, fetch=None, clock=state.now_utc):
        require(isinstance(storage, OperationalStorage) and callable(authenticate)
            and callable(clock), "OWNED_STORAGE_AND_LIVE_PARENT_CALLBACK_REQUIRED")
        policy = _load_source_policy(source_policy)
        frozen_policy = _load_source_policy(POLICY)
        require(policy["_policy_sha256"] == frozen_policy["_policy_sha256"] == cp.POLICY_SHA
            and policy["_canonical_policy_sha256"] == frozen_policy["_canonical_policy_sha256"],
            "UNCHANGED_E7_SOURCE_POLICY_REQUIRED")
        self.storage, self.output = storage, store.parents_safe(output)
        self.authenticate, self.fetch, self.clock = authenticate, fetch or live.fetch, clock
        require(callable(self.fetch), "EXISTING_E7_FETCH_CALLBACK_REQUIRED")
        self._used = False; self.capture = None; self._refs = []; self._events = 0

    def _write(self, name, document):
        path = self.output/name
        self.storage.write_bytes(path, state.canonical(document), replace=False)
        return _binding(self.storage,path)

    def _event(self, kind, **details):
        self._events += 1
        self._write("events/"+str(self._events).zfill(3)+".json",dict(kind=kind,at=state.utc(self.clock()).isoformat(),**details))

    def _auth(self, kind, inputs):
        self._budget()
        request = dict(schema_version=VERSION+"-authentication-request",kind=kind,
            inputs=deepcopy(inputs),inputs_sha256=state.digest(inputs),at=state.utc(self.clock()).isoformat())
        require(self.authenticate(deepcopy(request)) is True, "LIVE_PARENT_SOURCE_AUTHENTICATION_REJECTED")
        self._budget()

    def _budget(self):
        require(0 <= time.monotonic()-self._monotonic_started <= LIMITS["wall_seconds"]
            and 0 <= (state.utc(self.clock())-self._actual_started).total_seconds() <= LIMITS["wall_seconds"],
            "PROVIDER_WALL_BUDGET_EXCEEDED_PARENT_NATIVE_GUARD_REQUIRED")

    def _source(self, kind, season, week, namespace, request_ref):
        self._budget()
        name = kind+"-"+str(season)+"-"+str(week)
        url = (f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?seasontype=2&week={week}&dates={season}"
            if kind == "schedule" else f"https://api.sleeper.app/stats/nfl/{season}/{week}?season_type=regular")
        began = state.utc(self.clock())
        raw = self.storage.live_root/namespace/(name+".json")
        meta = raw.with_name(raw.name+".receipt.json")
        self._event("SOURCE_STARTED",kind_requested=kind,season=season,week=week,url=url,
            native_body_path=str(raw),native_receipt_path=str(meta))
        copied = []
        try:
            parsed, returned = self.fetch(self.storage.cache,name,url,day=namespace,storage=self.storage)
        finally:
            # Keep every completed native file even if the unchanged fetcher
            # subsequently fails JSON decoding. Raw bodies stay private.
            for source, suffix in ((raw,".json"),(meta,".json.receipt.json")):
                if not source.exists():
                    continue
                _binding(self.storage,source)
                dest = self.output/"sources"/(name+suffix)
                self.storage.import_file(source,dest)
                ref = _binding(self.storage,dest); copied.append(ref); self._refs.append(ref)
        ended = state.utc(self.clock())
        self._budget()
        require(len(copied) == 2, "COMPLETE_OWNED_NATIVE_BODY_RECEIPT_PAIR_REQUIRED")
        receipt = cp.strict_json(store.read_local(meta, 1 << 20))
        require(type(receipt) is dict and type(returned) is dict and receipt == returned,
            "NATIVE_E7_RECEIPT_EXACT_RETURNED_BYTES")
        require(receipt.get("name") == name+".json" and receipt.get("url") == url
            and receipt.get("status") == "acquired" and returned.get("cache_reused") is not True
            and not receipt.get("stale") and receipt.get("original_publication_utc") is None
            and type(receipt.get("bytes")) is int and 0 < receipt["bytes"] <= LIMITS["source_body_bytes"]
            and began <= state.utc(receipt["retrieved_utc"]) <= ended, "GENUINE_FRESH_E7_BODY_AND_HONEST_CLOCK_REQUIRED")
        _binding(self.storage,raw,receipt["sha256"]); _binding(self.storage,meta)
        # The receipt length already passed the unchanged source-body ceiling
        # and CAS/SHA gates. Exact size/hash readback below still detects change.
        body = store.read_local(raw,receipt["bytes"])
        require(len(body) == receipt["bytes"] and store.sha(body) == receipt["sha256"], "NATIVE_SOURCE_PHYSICAL_BODY_SHA")
        evidence = dict(request=request_ref,kind=kind,season=season,week=week,url=url,body=copied[0],native_receipt=copied[1],
            actual_started_at=began.isoformat(),actual_completed_at=ended.isoformat(),observed_at=receipt["retrieved_utc"],
            http_status=None,source_timestamp=None,
            transport="original_live_fetch" if self.fetch is live.fetch else "parent_supplied_E7_fetch")
        self._auth("AUTHENTICATE_SOURCE_BODY",evidence)
        # Parent callbacks cannot replace a qualified body between auth/parse.
        _binding(self.storage,raw,receipt["sha256"])
        for ref in copied:
            require(_binding(self.storage,ref["path"],ref["sha256"]) == ref, "SOURCE_PAIR_CHANGED_AFTER_PARENT_AUTH")
        qualified = cp.strict_json(body)
        require(state.canonical(parsed) == state.canonical(qualified), "FETCH_PAYLOAD_MUST_EQUAL_OWNED_SOURCE_BYTES")
        self._event("SOURCE_AUTHENTICATED",body_sha256=receipt["sha256"],native_receipt_sha256=copied[1]["sha256"],
            kind_requested=kind,season=season,week=week)
        return qualified,receipt

    def __call__(self, request):
        require(not self._used, "ONE_PROVIDER_ATTEMPT_ONLY_NO_RETRY")
        self._used = True
        began = state.utc(self.clock())
        self._actual_started,self._monotonic_started = began,time.monotonic()
        request = validate_request(request,at=began)
        require(not self.output.exists(), "NEW_PRIVATE_PROVIDER_OUTPUT_REQUIRED")
        self.storage.register_root(self.output)
        with operational_io(self.storage,run_root=self.output):
            request_ref = self._write("REQUEST.json",request)
            self._event("ATTEMPT_STARTED",request_sha256=request_ref["sha256"],fits=0)
            try:
                self._auth("AUTHORIZE_REGISTERED_REQUEST",dict(request=request_ref,source_policy_sha256=cp.POLICY_SHA,limits=LIMITS))
                namespace = began.strftime("%Y-%m-%d")+"/"+VERSION+"/"+store.sha(str(self.output).encode())
                observations = []; finality = []; missing = []
                by_id = {"espn:"+g["website_game_id"]:g for g in request["games"]}
                periods = sorted({(g["season"],g["week"]) for g in request["games"]})
                for season,week in periods:
                    board,br = self._source("schedule",season,week,namespace,request_ref)
                    require(type(board) is dict and type(board.get("week",{}).get("number")) is int
                        and board["week"]["number"] == week and type(board.get("season",{}).get("year")) is int
                        and board["season"]["year"] == season, "EXACT_ESPN_REGISTERED_REG_PERIOD")
                    parsed = live.schedule_games(board)
                    raw_events = {"espn:"+str(e["id"]):e for e in board.get("events",[])}
                    matched = []; finals = set()
                    requested = {k:g for k,g in by_id.items() if (g["season"],g["week"]) == (season,week)}
                    for game in parsed:
                        original = requested.get(game["game_id"])
                        if original is None:
                            continue
                        require(state.utc(game["kickoff_utc"]) == state.utc(original["kickoff_utc"])
                            and (game["home"],game["away"]) == (original["home"],original["away"]), "PROVIDER_GAME_IDENTITY_MISMATCH")
                        raw_status = raw_events[game["game_id"]]["competitions"][0].get("status",{}).get("type",{})
                        final = game["final"] is True and raw_status.get("state") == "post" and raw_status.get("name") == "STATUS_FINAL"
                        event_status = raw_events[game["game_id"]].get("status",{}).get("type")
                        if event_status is not None:
                            final = final and event_status.get("completed") is True and event_status.get("state") == "post" and event_status.get("name") == "STATUS_FINAL"
                        matched.append({k:game[k] for k in ("game_id","kickoff_utc","home","away")}|dict(final=bool(final)))
                        if final:
                            finals.add(game["game_id"])
                    missing.extend(sorted(set(requested)-{g["game_id"] for g in matched}))
                    finality.append(dict(season=season,week=week,games=matched,status_source_sha256=br["sha256"],observed_at=br["retrieved_utc"]))
                    offers = [r for r in request["opportunities"] if r["game_id"] in finals]
                    if not offers:
                        continue
                    stats,sr = self._source("statistics",season,week,namespace,request_ref)
                    observations.extend(project_statistics(stats,offers,source_receipt=sr,status_receipt=br))
                captured = state.utc(self.clock())
                document = dict(schema_version=grade.VERSION+"-provider-observations",source_policy_sha256=cp.POLICY_SHA,
                    captured_at=captured.isoformat(),observations=observations,finality=finality)
                observation_ref = self._write("OBSERVATIONS.json",document)
                completion = dict(schema_version=VERSION+"-local-completion",state="EMPTY_PENDING_NO_HTTP" if not periods else "LOCAL_PROVIDER_OBSERVATIONS_PENDING_GRADE_AUTH",
                    request=request_ref,observations=observation_ref,sources=deepcopy(self._refs),actual_started_at=began.isoformat(),
                    actual_completed_at=captured.isoformat(),source_policy_sha256=cp.POLICY_SHA,missing_game_status=missing,
                    observed_rows=len(observations),requested_opportunities=len(request["opportunities"]),
                    resolved_numeric_rows=sum(r["participation_state"] == "played" and r["actual"] is not None for r in observations),
                    pending_game_opportunities=len(request["opportunities"])-len(observations),
                    adapter_retries=0,native_HTTP_attempts_not_claimed=True,native_downloader_attempts_per_URL=3,
                    explicit_DNP_source_unavailable=True,local_only=True,public_release=False,fits=0,searches=0,code_pins=pins())
                self._auth("COMPLETE_PROVIDER_OBSERVATIONS",completion)
                self._write("COMPLETION.json",completion)
                self.capture = Capture(self.storage,self.output,completion,_KEY).verify()
                return deepcopy(document)
            except Exception as error:
                code = str(error) if isinstance(error,ProviderError) else "E7_PROVIDER_FAILURE_"+type(error).__name__
                self._event("ATTEMPT_FAILED",failure=code,retained_sources=deepcopy(self._refs),public_release=False,fits=0)
                raise


def project_statistics(stats, offers, *, source_receipt, status_receipt):
    """Existing live/scoring semantics; no zero fill, roster DNP, or fuzzy IDs."""
    wanted = {r["sleeper_id"] for r in offers}; entries = {}
    require(type(stats) in (dict,list), "CLOSED_SLEEPER_STATISTICS_CONTAINER")
    iterator = stats.items() if type(stats) is dict else ((s.get("player_id") if type(s) is dict else None,s) for s in stats)
    for sid,entry in iterator:
        sid = str(sid)
        if sid not in wanted:
            continue
        require(sid not in entries and type(entry) is dict, "DUPLICATE_OR_MALFORMED_REQUESTED_SLEEPER_ROW")
        actual_id = entry.get("player_id",sid)
        require(type(actual_id) in (str,int) and str(actual_id) == sid, "SLEEPER_SOURCE_KEY_ID_MISMATCH")
        entries[sid] = entry
    result = []
    for row in offers:
        require(row["target"] in grading.TARGETS, "ELEVEN_TARGETS_ONLY_FANTASY_BLOCKED")
        entry = entries.get(row["sleeper_id"])
        st = entry.get("stats",{}) if entry is not None else {}
        require(type(st) is dict, "MALFORMED_REQUESTED_PLAYER_STATISTICS")
        quarantined = False
        if entry is not None:
            player = entry.get("player") or {}
            require(type(player) is dict, "MALFORMED_SOURCE_PLAYER_IDENTITY")
            for key in ("season","week"):
                if key in entry:
                    require(type(entry[key]) is int and entry[key] == row[key], "SOURCE_STATISTICS_PERIOD_MISMATCH")
            team = entry.get("team") or player.get("team")
            gsis = entry.get("gsis_id") or player.get("gsis_id")
            game = entry.get("game_id")
            quarantined = (bool(team and live.TEAMS.get(team,team) != row["team"])
                or bool(gsis and gsis != row["player_id"])
                or bool(game and str(game) not in {row["game_id"],row["website_game_id"],row["original_game_id"]}))
        gp = st.get("gp"); snaps = st.get("off_snp")
        played = not quarantined and (type(gp) in (int,float) and gp == 1
            or type(snaps) in (int,float) and math.isfinite(snaps) and snaps > 0)
        value = scoring.stat_value(row["target"],st) if played else None
        if row["target"] in grading.COUNTS and value is not None and not float(value).is_integer():
            value = None
        item = dict(player_id=row["player_id"],game_id=row["game_id"],target=row["target"],actual=value,
            participation_state="played" if played else "unknown",source="sleeper-stats-nfl",
            source_sha256=source_receipt["sha256"],status_sha256=status_receipt["sha256"],
            observed_at=source_receipt["retrieved_utc"],source_timestamp=None)
        if quarantined:
            item["identity_quarantined"] = True
        result.append(item)
    return result


def collect(request, **kwargs):
    """Convenience one-attempt ABI; keep Collector to retain its typed capture."""
    return Collector(**kwargs)(request)
