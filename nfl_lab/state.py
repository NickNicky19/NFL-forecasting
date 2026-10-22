"""Single-writer, immutable forecast and append-only grading storage."""
from __future__ import annotations

import contextlib
import fcntl
import gzip
import hashlib
import json
import math
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def utc(value):
    dt=datetime.fromisoformat(str(value).replace("Z","+00:00")) if not isinstance(value,datetime) else value
    if dt.tzinfo is None:raise ValueError("timezone required")
    return dt.astimezone(timezone.utc)


def now_utc():return datetime.now(timezone.utc)


def canonical(obj):return json.dumps(obj,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()


def digest(obj):return hashlib.sha256(canonical(obj)).hexdigest()


def source_tree_digest(root):
    files=sorted(list((Path(root)/"nfl_lab").glob("*.py"))+list((Path(root)/"config").glob("*.json")))
    return digest({str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files})


@contextlib.contextmanager
def writer(root):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    with (root/".writer.lock").open("a") as f:
        fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield


def records(root,kind):
    for p in sorted((Path(root)/kind).glob("*.json.gz")):
        doc=json.loads(gzip.decompress(p.read_bytes()))
        if digest(doc)!=p.name.removesuffix(".json.gz"): raise ValueError(f"immutable record hash mismatch: {p}")
        yield doc


def save(root,kind,doc,max_bytes=200*1024*1024):
    root=Path(root);body=canonical(doc);key=digest(doc);path=root/kind/f"{key}.json.gz"
    if path.exists():return key
    size=sum(p.stat().st_size for p in root.rglob("*") if p.is_file() and p.name!=".writer.lock")
    compressed=gzip.compress(body,mtime=0)
    if size+len(compressed)>max_bytes:raise RuntimeError("durable evidence cap reached; no evidence deleted")
    path.parent.mkdir(parents=True,exist_ok=True)
    # Publish a complete fsynced file atomically. Interrupted temporary files
    # never match the immutable-record glob, and link refuses replacement.
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent,prefix=".pending-",delete=False) as f:
            temporary=Path(f.name);f.write(compressed);f.flush();os.fsync(f.fileno())
        try:os.link(temporary,path)
        except FileExistsError:
            if gzip.decompress(path.read_bytes())!=body:raise ValueError("conflicting immutable record")
        directory=os.open(path.parent,os.O_RDONLY)
        try:os.fsync(directory)
        finally:os.close(directory)
    finally:
        if temporary is not None:temporary.unlink(missing_ok=True)
    return key


def validate_forecast(row):
    for key in ["player_id","game_id","team","opponent","target","model_id","scoring_id","input_sha256","code_sha256","kickoff_utc","issued_at"]:
        if not row.get(key):raise ValueError(f"missing {key}")
    if utc(row["issued_at"])>=utc(row["kickoff_utc"]):raise ValueError("late forecast")
    value=row.get("mean")
    if value is None or not isinstance(value,(int,float)) or isinstance(value,bool) or not math.isfinite(value):raise ValueError("invalid mean")
    if row["target"] in ["rec","pass_cmp","pass_att","pass_td","pass_int","rush_att"] and value<0:raise ValueError("negative count mean")
    if row["target"]=="anytime_td" and not 0<=value<=1:raise ValueError("invalid TD probability")


def capture(root,rows,clock=now_utc):
    with writer(root):
        old={tuple(r[k] for k in ["player_id","game_id","target","model_id"]) for doc in records(root,"forecasts") for r in doc["rows"]}
        accepted=[];late=[];duplicates=0
        for original in rows:
            row=dict(original);key=tuple(row[k] for k in ["player_id","game_id","target","model_id"])
            if key in old:duplicates+=1;continue
            row["issued_at"]=clock().isoformat()
            if utc(row["issued_at"])>=utc(row["kickoff_utc"]):late.append({"key":key,"reason":"MISSED_NOT_BACKFILLED"});continue
            validate_forecast(row);accepted.append(row);old.add(key)
        # Verify the actual persistence start clock too, after all calculation/validation.
        persist=clock()
        surviving=[r for r in accepted if utc(r["kickoff_utc"])>persist]
        late.extend({"key":[r[k] for k in ["player_id","game_id","target","model_id"]],"reason":"MISSED_DURING_CALCULATION"} for r in accepted if utc(r["kickoff_utc"])<=persist)
        receipt={"schema_version":"lab-forecast-batch-v1","persist_started_at":persist.isoformat(),"durability":"LOCAL_PERSISTENCE_REMOTE_PUBLICATION_SEPARATELY_VERIFIED","rows":surviving,"missed":late}
        key=save(root,"forecasts",receipt) if surviving or late else None
        # Completion evidence is separate from immutable forecasts.
        completion=clock()
        completed_late=[r["game_id"] for r in surviving if utc(r["kickoff_utc"])<=completion]
        if key:save(root,"persistence",{"batch":key,"completed_at":completion.isoformat(),"late_games":sorted(set(completed_late))})
        return {"batch":key,"recorded":len(surviving),"duplicates":duplicates,"missed":len(late),"completed_late_games":completed_late}


def append_outcomes(root,observations):
    with writer(root):
        def version_key(row):return digest({k:v for k,v in row.items() if k!="observed_at"})
        def content_key(row):
            # Feed/status hashes identify entire snapshots, not a change to this
            # player-game target. Keep its first receipt and source-body hash.
            value=row.get("actual")
            if value is not None:value=int(value) if float(value).is_integer() else float(value)
            return digest({"player_id":row["player_id"],"game_id":row["game_id"],"target":row["target"],
                           "participation_state":row["participation_state"],"actual":value,"source":row.get("source"),
                           "scoring_id":row.get("scoring_id"),"period":row.get("period")})
        existing_versions=set();existing_content=set()
        for old in records(root,"outcomes"):
            existing_versions.add(version_key(old));existing_content.add(content_key(old))
        added=0
        for row in observations:
            if row["participation_state"] not in ["played","DNP","unknown"]:raise ValueError("bad participation")
            if row["participation_state"]!="played" and row.get("actual") is not None:raise ValueError("nonparticipant numeric outcome")
            if row.get("actual") is not None and (isinstance(row["actual"],bool) or not math.isfinite(row["actual"])):raise ValueError("invalid outcome")
            if not row.get("source_sha256") or not row.get("observed_at"):raise ValueError("unattributed outcome")
            version=version_key(row);content=content_key(row)
            # A real publication clock can order corrections/reversions even
            # when values repeat or versions arrive out of order. Preserve all
            # distinct known-clock evidence under the existing version rule.
            known_clock=bool(row.get("source_timestamp"))
            duplicate=version in existing_versions if known_clock else content in existing_content
            if not duplicate:
                save(root,"outcomes",row);added+=1
                existing_versions.add(version);existing_content.add(content)
        return {"appended":added}


def resolved_outcomes(root):
    by={}
    for r in records(root,"outcomes"):by.setdefault((r["player_id"],r["game_id"],r["target"]),[]).append(r)
    out={}
    for key,rs in by.items():
        terminal=[r for r in rs if r["participation_state"] in ["played","DNP"]]
        played={r["participation_state"] for r in terminal}
        values={r["actual"] for r in terminal if r.get("actual") is not None}
        if len(played)>1:out[key]={"state":"unresolved_participation_conflict","actual":None};continue
        if len(values)>1:
            # A source publication clock + same origin can establish a numeric correction.
            source={r.get("source") for r in terminal}
            if len(source)==1 and all(r.get("source_timestamp") for r in terminal):
                latest=max(utc(r["source_timestamp"]) for r in terminal)
                final=[r for r in terminal if utc(r["source_timestamp"])==latest]
                v={r.get("actual") for r in final}
                if len(v)==1:out[key]={"state":"played_corrected","actual":v.pop()};continue
            out[key]={"state":"unresolved_numeric_conflict","actual":None};continue
        out[key]={"state":next(iter(played)) if played else "unknown","actual":next(iter(values)) if values else None}
    return out
