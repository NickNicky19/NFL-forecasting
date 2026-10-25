"""Fictional E7 responses in real owned storage; no providers, outcomes or fits."""
import ast
from copy import deepcopy
from datetime import timedelta
import hashlib
import json
import os
from pathlib import Path
import pickle
import socket
import subprocess
import sys
from types import SimpleNamespace

import pytest

from nfl_lab import audit_weekly_provider_v1 as p, audit_weekly_grade_v1 as g
from nfl_lab import state, private_draft_store as store
from nfl_lab.operational_storage import OperationalStorage
from nfl_lab.operational_io import operational_io
from nfl_lab import data
from tools import audit_weekly_provider_v1 as cli

AT = state.utc("2026-10-28T08:00:00Z")
KICKOFF = "2026-10-25T17:00:00Z"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(socket.socket,"connect",lambda *_:pytest.fail("REAL_PROVIDER_NETWORK_FORBIDDEN"))


def request(targets=("rec",), *, empty=False):
    games, offers = [], []
    if not empty:
        games = [dict(season=2026,week=7,website_game_id="112",game_id="2026_07_BBB_AAA",kickoff_utc=KICKOFF,home="AAA",away="BBB")]
        b = dict(gsis_id="00-0000001",gsis_game_id=games[0]["game_id"],sleeper_id="123",website_player_id="123",website_game_id="112",
            team="AAA",opponent="BBB",kickoff_utc=KICKOFF,query_source_sha256="a"*64,schedule_source_sha256="b"*64,
            identity_bridge_kind="EXACT_ORIGINAL_WEEKLY_ROSTER_AND_SCHEDULE_NOT_NAMES",actual_visible_board_compatibility="NOT_YET_CHECKED")
        b["identity_binding_sha256"] = state.digest(b)
        for target in targets:
            identity = dict(season=2026,week=7,game_id=games[0]["game_id"],player_id=b["gsis_id"],category=target)
            offers.append(dict(schema_version="weekly-grading-v1-opportunity",season=2026,week=7,game_id="espn:112",
                original_game_id=games[0]["game_id"],website_game_id="112",player_id=b["gsis_id"],sleeper_id="123",position="RB",team="AAA",opponent="BBB",
                kickoff_utc=KICKOFF,cutoff_utc="2026-10-25T16:00:00Z",target=target,offered_id=state.digest(identity),
                identity_binding="frozen_exact_weekly_query_bridge",identity_binding_sha256=b["identity_binding_sha256"],bridge=deepcopy(b),primary_role=True))
    return dict(schema_version=g.VERSION+"-provider-request",scope="FIXED_COMPLETED_GAME_OPERATIONAL_GRADING_ONLY",
        source_policy_sha256=p.cp.POLICY_SHA,as_of=AT.isoformat(),games=games,opportunities=offers,retries=0,fits=0,research_or_tuning=False)


def board(*, final=True, state_name=None, status_name=None, extra=False):
    status = dict(completed=final,state=state_name or ("post" if final else "in"),name=status_name or ("STATUS_FINAL" if final else "STATUS_IN_PROGRESS"))
    event = dict(id="112",date=KICKOFF,status=dict(type=deepcopy(status)),competitions=[dict(status=dict(type=deepcopy(status)),
        competitors=[dict(homeAway="home",team=dict(abbreviation="AAA")),dict(homeAway="away",team=dict(abbreviation="BBB"))])])
    events = [event]
    if extra:
        other = deepcopy(event);other["id"]="999";events.append(other)
    return dict(season=dict(year=2026,type=2),week=dict(number=7),events=events)


class Transport:
    """Independent fictional API observer, separately bound by Parent."""
    def __init__(self, status=None, stats=None, *, clock=lambda:AT):
        self.board = status if status is not None else board()
        self.stats = stats if stats is not None else [dict(player_id="123",season=2026,week=7,team="AAA",stats=dict(gp=1,rec=0))]
        self.clock = clock; self.calls = []; self.api = {}; self.receipt_change = None; self.payload_change = None
        self.bad_json = False; self.fail = False

    def __call__(self,cache,name,url,*,day,storage):
        self.calls.append(url)
        assert url in {"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?seasontype=2&week=7&dates=2026",
            "https://api.sleeper.app/stats/nfl/2026/7?season_type=regular"}
        if self.fail:
            raise RuntimeError("FICTIONAL HTTP failure; no response body")
        value = self.board if name.startswith("schedule") else self.stats
        raw = b'{"bad-json":' if self.bad_json else state.canonical(value)
        path = storage.live_root/day/(name+".json")
        receipt = dict(name=name+".json",url=url,bytes=len(raw),sha256=store.sha(raw),retrieved_utc=self.clock().isoformat(),
            http_last_modified="Wed, 28 Oct 2026 07:59:59 GMT",etag="fictional",cache_reused=False,original_publication_utc=None,
            status="acquired",raw_redistribution="not authorized by this lab")
        if self.receipt_change:
            self.receipt_change(receipt)
        storage.write_bytes(path,raw);storage.write_bytes(path.with_name(path.name+".receipt.json"),state.canonical(receipt))
        self.api[receipt["sha256"]] = dict(url=url,bytes=len(raw),observed_at=self.clock().isoformat(),http_status=200)
        if self.bad_json:
            raise ValueError("FICTIONAL original decoder failure")
        result = deepcopy(value)
        if self.payload_change:
            self.payload_change(result)
        return result,deepcopy(receipt)


class Parent:
    def __init__(self,storage,transport,expected):
        self.storage,self.transport,self.expected = storage,transport,state.digest(expected)
        self.calls=[];self.reject_kind=None;self.json_authority=False

    def __call__(self,auth):
        self.calls.append(deepcopy(auth))
        assert set(auth)=={"schema_version","kind","inputs","inputs_sha256","at"}
        assert auth["inputs_sha256"]==state.digest(auth["inputs"])
        if self.json_authority:
            return dict(execution_authorized=True)
        if auth["kind"]==self.reject_kind:
            return False
        d=auth["inputs"]
        if auth["kind"]=="AUTHORIZE_REGISTERED_REQUEST":
            ref=d["request"];self.storage.validate_reference(ref["path"],ref["sha256"])
            assert ref["sha256"]==self.expected
        elif auth["kind"]=="AUTHENTICATE_SOURCE_BODY":
            for name in ("body","native_receipt"):
                ref=d[name];self.storage.validate_reference(ref["path"],ref["sha256"])
            body=Path(d["body"]["path"]).read_bytes();native=json.loads(Path(d["native_receipt"]["path"]).read_bytes())
            assert store.sha(body)==native["sha256"]==d["body"]["sha256"]
            actual=self.transport.api[d["body"]["sha256"]]
            assert actual["url"]==d["url"]==native["url"] and actual["http_status"]==200
            assert actual["observed_at"]==d["observed_at"]==native["retrieved_utc"]
            assert d["source_timestamp"] is None and d["http_status"] is None
        else:
            assert auth["kind"]=="COMPLETE_PROVIDER_OBSERVATIONS"
            assert d["fits"]==0 and d["public_release"] is False
        return True


@pytest.fixture
def setup(tmp_path):
    storage=OperationalStorage(tmp_path/"cache",p.POLICY,state=tmp_path/"state")
    def make(req=None,transport=None,at=AT,label="attempt"):
        req = request() if req is None else req
        transport=transport or Transport(clock=lambda:at)
        parent=Parent(storage,transport,req)
        collector=p.Collector(storage=storage,output=tmp_path/label,authenticate=parent,fetch=transport,clock=lambda:at)
        return collector,parent,transport,req
    return storage,make


@pytest.fixture(scope="module")
def original_policy_reference():
    """Execute only metadata code from the unmodified pre-repair Git source."""
    original = "5085bdbe00d56f9a47a057a186b374c1bf839d2b"
    def blob(name):
        return subprocess.check_output(["git", "-C", str(p.ROOT), "show", original+":"+name])
    loader_body = blob("nfl_lab/operational_sources.py")
    provider_body = blob("nfl_lab/audit_weekly_provider_v1.py")
    assert hashlib.sha256(loader_body).hexdigest() == "069c498ebef85fee291f7f9913bebc6d157988d2242de5feb6b066d6ba68e11e"
    assert hashlib.sha256(provider_body).hexdigest() == "911a2690dd1bb418f692e7be5e7b4d9f1c4f31703d791115e748f3a7b21336ec"
    data_tree = ast.parse(blob("nfl_lab/data.py"))
    base = next(ast.literal_eval(n.value) for n in data_tree.body if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "BASE" for t in n.targets))
    checkpoint_tree = ast.parse(blob("nfl_lab/gha_private_checkpoint.py"))
    policy_sha = next(ast.literal_eval(n.value) for n in checkpoint_tree.body if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "POLICY_SHA" for t in n.targets))
    names = {"POLICY_ID", "SCHEDULE_COLUMNS", "SOURCE_SPECS"}
    nodes = [n for n in ast.parse(loader_body).body
        if isinstance(n, ast.FunctionDef) and n.name in {"_json", "_digest", "load_source_policy"}
        or isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in names for t in n.targets)]
    scope = dict(Path=Path, json=json, hashlib=hashlib, data=SimpleNamespace(BASE=base))
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "original-069c-policy", "exec"), scope)
    loader = scope["load_source_policy"]
    original_class = next(n for n in ast.parse(provider_body).body if isinstance(n, ast.ClassDef) and n.name == "Collector")
    init = next(n for n in original_class.body if isinstance(n, ast.FunctionDef) and n.name == "__init__")
    # Substitute only the import seam with the independently compiled original
    # loader. Every original constructor statement and both hash gates execute.
    for i, node in enumerate(init.body):
        if isinstance(node, ast.ImportFrom) and any(a.name == "operational_sources" for a in node.names):
            init.body[i] = ast.copy_location(ast.Assign(targets=[ast.Name(id="sources", ctx=ast.Store())],
                value=ast.Name(id="original_sources", ctx=ast.Load())), node)
    constructor = dict(POLICY=p.POLICY, state=state, cp=SimpleNamespace(POLICY_SHA=policy_sha), require=p.require, OperationalStorage=OperationalStorage,
        store=store, live=p.live, original_sources=SimpleNamespace(load_source_policy=loader))
    exec(compile(ast.fix_missing_locations(ast.Module(body=[init], type_ignores=[])), "original-5085-Collector", "exec"), constructor)
    return SimpleNamespace(load=loader, Collector=type("OriginalCollector", (), {"__init__": constructor["__init__"]}))


_POLICY_CASES = [
    ("path", "ACCEPT"), ("copied_path", "ACCEPT"), ("copied_string", "ACCEPT"),
    ("raw_dict", "UNCHANGED_E7_SOURCE_POLICY_REQUIRED"), ("normalized", "ACCEPT"),
    ("private_metadata", "ACCEPT"), ("changed_file_format", "UNCHANGED_E7_SOURCE_POLICY_REQUIRED"),
    ("policy_id", "unsupported operational source policy"),
    ("missing_source", "source policy whitelist changed"), ("extra_source", "source policy whitelist changed"),
    ("schedule_columns", "schedule metadata columns changed"),
    ("lag", "unsupported availability/season-type policy"), ("season_type", "unsupported availability/season-type policy"),
    ("statistics_predicate", "explicit REG parquet predicates required"), ("roster_predicate", "explicit REG parquet predicates required"),
    ("extra_field", "UNCHANGED_E7_SOURCE_POLICY_REQUIRED"), ("extra_source_field", "UNCHANGED_E7_SOURCE_POLICY_REQUIRED"),
    ("bad_canonical", "normalized operational policy body changed"), ("bad_policy_sha", "UNCHANGED_E7_SOURCE_POLICY_REQUIRED"),
] + [(kind+"_"+field, "source policy URL/name changed: "+kind)
    for kind in ("schedules", "players", "statistics", "rosters", "license") for field in ("name", "url")]


@pytest.mark.parametrize("case,expected", _POLICY_CASES, ids=[v[0] for v in _POLICY_CASES])
def test_metadata_policy_matches_original_loader_and_full_Collector_admission(setup, tmp_path, original_policy_reference, case, expected):
    reference = original_policy_reference
    raw = p.POLICY.read_bytes()
    candidate = deepcopy(reference.load(p.POLICY))
    if case == "path": candidate = p.POLICY
    elif case in {"copied_path", "copied_string", "changed_file_format"}:
        copied = tmp_path/"copied-policy.json"
        copied.write_bytes(raw + (b"\n" if case == "changed_file_format" else b""))
        candidate = str(copied) if case == "copied_string" else copied
    elif case == "raw_dict": candidate = json.loads(raw)
    elif case == "private_metadata": candidate["_ignored_metadata"] = "fictional"
    elif case == "normalized": pass
    else:
        if case == "policy_id": candidate["policy_id"] = "unregistered"
        elif case == "missing_source": del candidate["sources"]["license"]
        elif case == "extra_source": candidate["sources"]["unregistered"] = dict(name="fictional", url="https://example.invalid")
        elif case == "schedule_columns": candidate["sources"]["schedules"]["columns"].reverse()
        elif case == "lag": candidate["history"]["statistics_lag_days"] = 6
        elif case == "season_type": candidate["history"]["season_type"] = "POST"
        elif case == "statistics_predicate": candidate["history"]["parquet_predicates"]["statistics_season_type"] = "season_type == POST"
        elif case == "roster_predicate": candidate["history"]["parquet_predicates"]["roster_season_type"] = "game_type == POST"
        elif case == "extra_field": candidate["fictional_public_extra"] = "é"
        elif case == "extra_source_field": candidate["sources"]["schedules"]["fictional_extra"] = True
        elif case not in {"bad_canonical", "bad_policy_sha"}:
            kind, field = case.rsplit("_", 1)
            candidate["sources"][kind][field] += "-changed"
        clean = {k:v for k,v in candidate.items() if not k.startswith("_")}
        candidate["_canonical_policy_sha256"] = hashlib.sha256(
            (json.dumps(clean, sort_keys=True, separators=(",", ":"), allow_nan=False)+"\n").encode()).hexdigest()
        if case == "bad_canonical": candidate["_canonical_policy_sha256"] = "0"*64
        if case == "bad_policy_sha": candidate["_policy_sha256"] = "0"*64
    def normalized(load):
        try: return load(candidate)
        except ValueError as error: return str(error)
    assert normalized(p._load_source_policy) == normalized(reference.load)
    storage, _ = setup
    def admission(constructor, label):
        try:
            constructor(storage=storage, output=tmp_path/label, authenticate=lambda _auth:True,
                source_policy=candidate, clock=lambda:AT)
        except ValueError as error: return str(error)
        return "ACCEPT"
    assert admission(reference.Collector, "old") == expected
    assert admission(p.Collector, "new") == expected


def test_metadata_policy_canonical_newline_and_both_actual_loads(setup, tmp_path, monkeypatch):
    storage, _ = setup; calls = []; actual = p._load_source_policy
    def load(value):
        calls.append(value)
        return actual(value)
    monkeypatch.setattr(p, "_load_source_policy", load)
    p.Collector(storage=storage, output=tmp_path/"two-policy-loads", authenticate=lambda _:True)
    assert calls == [p.POLICY, p.POLICY]
    policy = actual(p.POLICY)
    assert policy["_policy_sha256"] == p.cp.POLICY_SHA
    assert policy["_canonical_policy_sha256"] == "c3e28c603d7bdaeefed9d9d2c2a2e5e34e0ef45794b34078472b3e6c14239595"
    clean = {k:v for k,v in policy.items() if not k.startswith("_")}
    assert policy["_canonical_policy_sha256"] == hashlib.sha256(
        (json.dumps(clean, sort_keys=True, separators=(",", ":"), allow_nan=False)+"\n").encode()).hexdigest()


def test_metadata_policy_rejects_original_validator_drift_before_policy_decode(setup, tmp_path, monkeypatch):
    storage, _ = setup; actual = store.read_local
    source = p.ROOT/"nfl_lab/operational_sources.py"
    def changed(path, cap):
        body = actual(path, cap)
        return body+b"\n" if Path(path) == source else body
    monkeypatch.setattr(store, "read_local", changed)
    monkeypatch.setattr(p.json, "loads", lambda *_a,**_k:pytest.fail("POLICY_DECODE_BEFORE_ORIGINAL_VALIDATOR_PIN"))
    with pytest.raises(p.ProviderError, match="ORIGINAL_SOURCE_POLICY_VALIDATOR_REQUIRED"):
        p.Collector(storage=storage, output=tmp_path/"drift", authenticate=lambda _:True)
    assert not (tmp_path/"drift").exists()


def test_cold_Collector_policy_admission_imports_no_numerical_loader(tmp_path):
    profile = json.loads((p.ROOT/"config/audit-weekly-numerical-runtime-v1.json").read_bytes())["environment"]
    env = {k:os.environ[k] for k in ("PATH", "LANG", "LC_ALL", "TZ") if k in os.environ}
    env.update(profile)
    script = '''import json,resource,signal,sys
from pathlib import Path
resource.setrlimit(resource.RLIMIT_CPU,(120,120));resource.setrlimit(resource.RLIMIT_AS,(512<<20,512<<20))
signal.alarm(180)
sys.path.insert(0,sys.argv[1])
blocked=('nfl_lab.operational_sources','nfl_lab.features','numpy','pandas','pyarrow','scipy','sklearn','catboost')
class NoNumerics:
 def find_spec(self,name,*_args):
  if any(name==p or name.startswith(p+'.') for p in blocked):raise RuntimeError('NUMERICAL_IMPORT_DURING_POLICY_ADMISSION')
sys.meta_path.insert(0,NoNumerics())
def deny(event,_args):
 if event.startswith(('socket.','subprocess.')):raise RuntimeError('NO_EXTERNAL_EXECUTION_FOR_METADATA_POLICY')
sys.addaudithook(deny)
from nfl_lab import audit_weekly_provider_v1 as p
from nfl_lab.operational_storage import OperationalStorage
root=Path(sys.argv[2]);storage=OperationalStorage(root/'cache',p.POLICY,state=root/'state')
def authenticate(_):raise RuntimeError('NO_AUTHORIZATION_FROM_POLICY_METADATA')
collector=p.Collector(storage=storage,output=root/'unused-output',authenticate=authenticate)
assert collector.capture is None and not collector.output.exists()
assert not any(name==p or name.startswith(p+'.') for name in sys.modules for p in blocked)
print(json.dumps(dict(state='COLD_METADATA_POLICY_ADMITTED',fits=0,provider_calls=0)))
'''
    result = subprocess.run([sys.executable, "-I", "-B", "-c", script, str(p.ROOT), str(tmp_path)],
        cwd=p.ROOT, env=env, capture_output=True, text=True, timeout=185)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == dict(state="COLD_METADATA_POLICY_ADMITTED", fits=0, provider_calls=0)


def test_zero_games_empty_pending_no_HTTP_with_default_transport(setup,tmp_path):
    storage,_=setup;req=request(empty=True);t=Transport();parent=Parent(storage,t,req)
    c=p.Collector(storage=storage,output=tmp_path/"empty",authenticate=parent,clock=lambda:AT)
    result=c(req)
    assert result["observations"]==result["finality"]==[] and t.calls==[]
    assert c.capture.document["state"]=="EMPTY_PENDING_NO_HTTP" and c.capture.document["sources"]==[]
    assert [x["kind"]for x in parent.calls]==["AUTHORIZE_REGISTERED_REQUEST","COMPLETE_PROVIDER_OBSERVATIONS"]


def test_played_zero_retained_with_owned_exact_native_source_pairs(setup):
    _,make=setup;c,parent,t,req=make();doc=c(req)
    assert doc["observations"][0]["actual"]==0 and doc["observations"][0]["participation_state"]=="played"
    assert doc["observations"][0]["source_timestamp"] is None
    assert len(t.calls)==2 and len(c.capture.document["sources"])==4
    assert c.capture.verify() is c.capture
    assert json.loads((c.output/"OBSERVATIONS.json").read_bytes())==doc
    assert len([x for x in parent.calls if x["kind"]=="AUTHENTICATE_SOURCE_BODY"])==2


def test_default_native_live_fetch_downloader_with_fictional_HTTP(setup,tmp_path,monkeypatch):
    storage,_=setup;req=request();t=Transport();parent=Parent(storage,t,req)
    class Response:
        status_code=200
        def __init__(self,url):
            self.url=url;self.value=board() if "scoreboard?" in url else t.stats
            self.body=state.canonical(self.value)
            self.headers={"Content-Length":str(len(self.body)),"Last-Modified":"Wed, 28 Oct 2099 00:00:00 GMT"}
        def __enter__(self):return self
        def __exit__(self,*_):pass
        def raise_for_status(self):pass
        def iter_content(self,_chunk):yield self.body
    def GET(url,*,stream,timeout):
        assert stream is True and timeout==(10,60)
        t.calls.append(url);response=Response(url)
        t.api[store.sha(response.body)]=dict(url=url,bytes=len(response.body),observed_at=AT.isoformat(),http_status=200)
        return response
    monkeypatch.setattr(data.requests,"get",GET)
    monkeypatch.setattr(data,"_utc_now",lambda:AT.isoformat())
    c=p.Collector(storage=storage,output=tmp_path/"original-default-fetch",authenticate=parent,clock=lambda:AT)
    assert c.fetch is p.live.fetch
    doc=c(req)
    assert len(t.calls)==2 and doc["observations"][0]["actual"]==0
    assert doc["observations"][0]["source_timestamp"] is None
    assert c.capture.verify().document["resolved_numeric_rows"]==1


def test_lossless_numeric_source_ID_is_exact_frozen_binding(setup):
    _,make=setup;c,_,_,r=make(transport=Transport(stats=[dict(player_id=123,stats=dict(gp=1,rec=0))]))
    assert c(r)["observations"][0]["actual"]==0


@pytest.mark.parametrize("stats",[[],[dict(player_id="123",stats=dict(gp=0,rec=0),status="INA")],
    [dict(player_id="123",stats=dict(gp=0),status="DNP")],[dict(player_id="123",stats=dict(gp=True,rec=0))]])
def test_absence_zero_roster_DNP_bool_never_establish_played_zero(setup,stats):
    _,make=setup;c,_,_,req=make(transport=Transport(stats=stats));r=c(req)["observations"][0]
    assert (r["participation_state"],r["actual"])==("unknown",None)
    assert c.capture.document["explicit_DNP_source_unavailable"] is True


def test_played_missing_statistic_is_not_zero(setup):
    _,make=setup;c,_,_,req=make(transport=Transport(stats=[dict(player_id="123",stats=dict(gp=1))]))
    r=c(req)["observations"][0];assert (r["participation_state"],r["actual"])==("played",None)


def test_existing_parser_signed_combined_missing_and_TD_event(setup):
    _,make=setup;req=request(("rush_yd","rec_yd","rush_rec_yd","anytime_td","rec"))
    t=Transport(stats=[dict(player_id="123",stats=dict(off_snp=1,rush_yd=-2,rec_yd=4,rush_td=1,rec=0))])
    c,_,_,req=make(req,t);rows={r["target"]:r["actual"]for r in c(req)["observations"]}
    assert rows==dict(rush_yd=-2,rec_yd=4,rush_rec_yd=2,anytime_td=1,rec=0)
    pure=p.project_statistics([dict(player_id="123",stats=dict(gp=1,rush_yd=3,rush_td=0))],req["opportunities"],
        source_receipt=dict(sha256="a"*64,retrieved_utc=AT.isoformat()),status_receipt=dict(sha256="b"*64))
    values={r["target"]:r["actual"]for r in pure}
    assert values["rush_rec_yd"] is None and values["anytime_td"] is None


def test_all_eleven_targets_exact_hand_calculable_values_and_fantasy_blocked(setup):
    _,make=setup;req=request(tuple(sorted(p.grading.TARGETS)))
    stats=dict(gp=1,pass_yd=-1,pass_att=2,pass_cmp=0,pass_td=0,pass_int=0,rush_yd=-2,rush_att=0,rec=0,rec_yd=0,rush_td=0,rec_td=0)
    c,_,_,r=make(req,Transport(stats=[dict(player_id="123",stats=stats)]))
    actual={r["target"]:r["actual"]for r in c(r)["observations"]}
    assert actual==dict(pass_yd=-1,pass_att=2,pass_cmp=0,pass_td=0,pass_int=0,rush_yd=-2,rush_att=0,rec=0,rec_yd=0,rush_rec_yd=-2,anytime_td=0)
    req=request(("fantasy_ppr",));c,_,t,r=make(req,label="fantasy-blocked")
    with pytest.raises(p.ProviderError):c(r)
    assert t.calls==[]


@pytest.mark.parametrize("value",[-1,1.5,True])
def test_invalid_count_is_played_missing_not_fabricated_zero(setup,value):
    _,make=setup;c,_,_,r=make(transport=Transport(stats=[dict(player_id="123",stats=dict(gp=1,rec=value))]))
    row=c(r)["observations"][0]
    assert row["participation_state"]=="played" and row["actual"] is None


@pytest.mark.parametrize("final,game_state,name",[(False,"in","STATUS_IN_PROGRESS"),(True,"post","STATUS_CANCELED"),(True,"pre","STATUS_FINAL")])
def test_nonfinal_canceled_incoherent_never_collects_statistics(setup,final,game_state,name):
    _,make=setup;c,_,t,req=make(transport=Transport(status=board(final=final,state_name=game_state,status_name=name)))
    doc=c(req);assert doc["observations"]==[] and doc["finality"][0]["games"][0]["final"] is False
    assert len(t.calls)==1


def test_conflicting_top_level_ESPN_status_does_not_override_finality(setup):
    _,make=setup;b=board();b["events"][0]["status"]["type"]["completed"]=False
    c,_,t,req=make(transport=Transport(status=b));doc=c(req)
    assert doc["observations"]==[] and len(t.calls)==1


def test_only_registered_games_projected_and_missing_status_pending(setup):
    _,make=setup;c,_,_,req=make(transport=Transport(status=board(extra=True)))
    assert [r["game_id"]for r in c(req)["finality"][0]["games"]]==["espn:112"]
    b=board();b["events"]=[];c,_,t,req=make(transport=Transport(status=b),label="missing")
    assert c(req)["observations"]==[] and c.capture.document["missing_game_status"]==["espn:112"] and len(t.calls)==1


@pytest.mark.parametrize("field,value",[("source_policy_sha256","0"*64),("retries",True),("fits",1),("research_or_tuning",True),("execution_authorized",True)])
def test_unqualified_JSON_authority_rejected_before_HTTP(setup,field,value):
    _,make=setup;r=request();r[field]=value;c,_,t,r=make(r)
    with pytest.raises(p.ProviderError):c(r)
    assert t.calls==[] and not c.output.exists()


def test_future_game_orphan_and_tampered_bridge_rejected_before_HTTP(setup):
    _,make=setup
    changes=(lambda r:r["games"][0].update(kickoff_utc="2026-11-01T17:00:00Z"),
        lambda r:r["opportunities"][0].update(player_id="00-9999999"),lambda r:r["opportunities"][0]["bridge"].update(sleeper_id="999"))
    for i,change in enumerate(changes):
        r=request();change(r);c,_,t,r=make(r,label="bad"+str(i))
        with pytest.raises(p.ProviderError):c(r)
        assert t.calls==[]


def test_actual_native_bridge_and_minimal_grade_bridge_both_exact(setup):
    _,make=setup;r=request();assert set(r["opportunities"][0]["bridge"])==p.NATIVE_BRIDGE_KEYS
    assert p.validate_request(r,at=AT)==r
    row=r["opportunities"][0];b=row["bridge"]
    for key in ("identity_bridge_kind","actual_visible_board_compatibility","identity_binding_sha256"):
        del b[key]
    b["identity_binding_sha256"]=state.digest(b);row["identity_binding_sha256"]=b["identity_binding_sha256"]
    c,_,_,r=make(r);assert c(r)["observations"][0]["actual"]==0


def test_native_name_match_identity_claim_rejected_before_source_reads(setup):
    _,make=setup;r=request();row=r["opportunities"][0];b=row["bridge"]
    b["identity_bridge_kind"]="NAME_MATCH";b["identity_binding_sha256"]=state.digest({k:v for k,v in b.items()if k!="identity_binding_sha256"})
    row["identity_binding_sha256"]=b["identity_binding_sha256"]
    c,_,t,r=make(r)
    with pytest.raises(p.ProviderError,match="EXACT_NATIVE_IDENTITY_BRIDGE_METADATA"):c(r)
    assert t.calls==[]


def test_exact_game_context_and_returned_payload_binding(setup):
    _,make=setup;b=board();b["events"][0]["date"]="2026-10-25T18:00:00Z"
    c,_,t,r=make(transport=Transport(status=b))
    with pytest.raises(p.ProviderError,match="PROVIDER_GAME_IDENTITY_MISMATCH"):c(r)
    assert len(t.calls)==1 and c.capture is None
    t=Transport();t.payload_change=lambda d:d.update(fictional_unretained_field=True) if type(d) is dict else None
    c,_,_,r=make(transport=t,label="changed-payload")
    with pytest.raises(p.ProviderError,match="FETCH_PAYLOAD_MUST_EQUAL_OWNED_SOURCE_BYTES"):c(r)


@pytest.mark.parametrize("change",[dict(gsis_id="00-9999999"),dict(team="BBB"),dict(game_id="999")])
def test_source_identity_contradictions_quarantine_player_rows(setup,change):
    _,make=setup;entry=dict(player_id="123",stats=dict(gp=1,rec=4),**change)
    c,_,_,r=make(transport=Transport(stats=[entry]));row=c(r)["observations"][0]
    assert row["identity_quarantined"] is True and row["actual"] is None and row["participation_state"]=="unknown"


def test_duplicate_source_ID_and_period_mismatch_not_last_write_wins(setup):
    _,make=setup
    for i,stats in enumerate(([dict(player_id="123",stats=dict(gp=1,rec=0))]*2,[dict(player_id="123",week=8,stats=dict(gp=1,rec=1))])):
        c,_,_,r=make(transport=Transport(stats=stats),label="duplicate"+str(i))
        with pytest.raises(p.ProviderError):c(r)
        assert c.capture is None


def test_live_parent_rejection_and_saved_JSON_boolean_never_authorize(setup):
    _,make=setup
    for i,kind in enumerate(("AUTHORIZE_REGISTERED_REQUEST","AUTHENTICATE_SOURCE_BODY","COMPLETE_PROVIDER_OBSERVATIONS","JSON")):
        c,parent,t,r=make(label="reject"+str(i))
        if kind=="JSON":parent.json_authority=True
        else:parent.reject_kind=kind
        with pytest.raises(p.ProviderError,match="LIVE_PARENT_SOURCE_AUTHENTICATION_REJECTED"):c(r)
        assert c.capture is None and not (c.output/"COMPLETION.json").exists()
        assert any(json.loads(x.read_bytes())["kind"]=="ATTEMPT_FAILED"for x in (c.output/"events").glob("*.json"))


def test_bad_native_JSON_and_transport_failure_preserve_attempt(setup):
    _,make=setup;t=Transport();t.bad_json=True;c,_,_,r=make(transport=t)
    with pytest.raises(ValueError):c(r)
    assert len(list((c.output/"sources").glob("*")))==2 and c.capture is None
    assert (c.output/"sources/schedule-2026-7.json").read_bytes()==b'{"bad-json":'
    t=Transport();t.fail=True;c,_,_,r=make(transport=t,label="HTTP-failure")
    with pytest.raises(RuntimeError):c(r)
    assert (c.output/"REQUEST.json").exists() and c.capture is None
    assert "ATTEMPT_FAILED" in [json.loads(x.read_bytes())["kind"]for x in (c.output/"events").glob("*.json")]


@pytest.mark.parametrize("kind",["stale","old-clock","invented-publication"])
def test_stale_backdated_fake_publication_receipt_cannot_qualify(setup,kind):
    _,make=setup;t=Transport()
    t.receipt_change=lambda r:r.update(**({"stale":True,"status":"stale_cache"}if kind=="stale" else
        {"retrieved_utc":"2026-10-26T00:00:00Z"}if kind=="old-clock" else {"original_publication_utc":AT.isoformat()}))
    c,_,_,r=make(transport=t)
    with pytest.raises(p.ProviderError,match="GENUINE_FRESH_E7_BODY_AND_HONEST_CLOCK_REQUIRED"):c(r)
    assert c.capture is None and len(list((c.output/"sources").glob("*")))==2


def test_unknown_publication_revisions_quarantined_by_unchanged_resolver(setup,tmp_path):
    storage,make=setup;rows=[]
    for i,value in enumerate((1,2)):
        at=AT+timedelta(hours=i)
        t=Transport(stats=[dict(player_id="123",stats=dict(gp=1,rec=value))],clock=lambda at=at:at)
        c,_,_,r=make(transport=t,at=at,label="revision"+str(i));rows.extend(c(r)["observations"])
    assert all(r["source_timestamp"] is None for r in rows)
    with operational_io(storage):state.append_outcomes(tmp_path/"state/fictional-resolver",rows)
    assert state.resolved_outcomes(tmp_path/"state/fictional-resolver")[("00-0000001","espn:112","rec")] == dict(state="unresolved_numeric_conflict",actual=None)


def test_independent_explicit_DNP_fact_and_played_zero_stay_distinct(setup,tmp_path):
    storage,make=setup;c,_,_,r=make();played=c(r)["observations"][0]
    # Independent hypothetical final-provider DNP, NOT inferred or claimed by
    # this adapter. The unchanged resolver must not collapse it to played zero.
    known_dnp=dict(played,source="fictional-independent-authoritative-DNP",actual=None,participation_state="DNP")
    with operational_io(storage):state.append_outcomes(tmp_path/"state/DNP-control",[known_dnp])
    assert state.resolved_outcomes(tmp_path/"state/DNP-control")[("00-0000001","espn:112","rec")]==dict(state="DNP",actual=None)
    with operational_io(storage):state.append_outcomes(tmp_path/"state/DNP-control",[played])
    assert state.resolved_outcomes(tmp_path/"state/DNP-control")[("00-0000001","espn:112","rec")]["state"]=="unresolved_participation_conflict"


def test_actual_grade_acquire_accepts_closed_document_without_new_gate_logic(setup):
    _,make=setup;c,parent,_,r=make()
    # Fictional sealed input for the existing acquire API; no real archive,
    # forecast, model or provider authority is asserted by this unit fixture.
    capture=g.Capture(dict(schedule=r["games"],opportunities=r["opportunities"]),g._KEY)
    def authenticate(auth):
        return auth["kind"]=="COMPLETED_GAME_PROVIDER_OBSERVATIONS" and auth["inputs_sha256"]==state.digest(
            dict(request=g.provider_request([capture],at=AT),observations=json.loads((c.output/"OBSERVATIONS.json").read_bytes())))
    accepted=g.acquire([capture],collect=c,authenticate=authenticate,clock=lambda:AT)
    assert type(accepted) is g.Observations and accepted.document["observations"][0]["actual"]==0


def test_one_attempt_and_live_capture_unserializable_and_integrity_bound(setup):
    _,make=setup;c,_,_,r=make();c(r)
    with pytest.raises(p.ProviderError,match="ONE_PROVIDER_ATTEMPT_ONLY_NO_RETRY"):c(r)
    with pytest.raises(p.ProviderError,match="LIVE_PROVIDER_CAPTURE_CANNOT_BE_SERIALIZED"):pickle.dumps(c.capture)
    c.capture.document["fits"]=1
    with pytest.raises(p.ProviderError,match="PROVIDER_CAPTURE_CHANGED"):c.capture.verify()


def test_late_native_response_retained_but_never_qualified_as_success(setup,tmp_path):
    storage,_=setup;r=request();t=Transport();parent=Parent(storage,t,r);current=[AT]
    def delayed(*args,**kwargs):
        result=t(*args,**kwargs);current[0]=AT+timedelta(seconds=181);return result
    c=p.Collector(storage=storage,output=tmp_path/"late-native",authenticate=parent,fetch=delayed,clock=lambda:current[0])
    with pytest.raises(p.ProviderError,match="PROVIDER_WALL_BUDGET_EXCEEDED_PARENT_NATIVE_GUARD_REQUIRED"):c(r)
    assert c.capture is None and not (c.output/"COMPLETION.json").exists()
    assert len(t.calls)==1 and len(list((c.output/"sources").glob("*")))==2


def test_CLI_contract_cannot_execute_JSON_or_touch_provider(monkeypatch,tmp_path):
    monkeypatch.setattr(p.live,"fetch",lambda *_a,**_k:pytest.fail("CLI_MUST_NOT_ACQUIRE"))
    out=tmp_path/"contract.json"
    assert cli.main(["contract","--output",str(out)])==0
    doc=json.loads(out.read_bytes())
    assert doc["state"]=="PREPARED_UNREGISTERED" and len(doc["targets"])==11 and doc["source_timestamp"] is None
    assert cli.main(["execute"])==2
