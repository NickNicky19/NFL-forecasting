"""Byte-derived pure chart contracts; no HTTP/source/model imports."""

from pathlib import Path

import hashlib,json,math

import numpy as np

import pandas as pd

ROLES=['QB','RB','FB','WR','TE']

STATS=['pass_yd','pass_td','pass_att','pass_int','rush_yd','rush_att','rec','rec_yd','rush_td','rec_td','rec_tgt']

FEATURES=[f'f_player_{s}_mean{w}' for s in STATS for w in (3,8)]+[
    'f_player_games_prior','f_player_play_rate8','f_player_known_participation_n8','f_player_pass_ypa3',
    'f_player_comp_rate3','f_player_rush_ypa3','f_player_rec_ypt3','f_player_rec_catch_rate3','f_rest_days','f_is_home']

KEYS=['game_id','team','player_id']

class NumericToken(str):
    """A JSON numeric lexeme; no target outcome conversion before freeze."""

def normalized_team(value):
    return {'LA':'LAR','STL':'LAR','SD':'LAC','OAK':'LV'}.get(value,value)

def key(row):
    return row['game_id'], normalized_team(row['team']), row['player_id']

def require_identity(label,source):
    identity=label['identity']
    if (int(identity['season'])!=int(source['season']) or int(identity['week'])!=int(source['week'])
        or normalized_team(identity['opponent'])!=normalized_team(source['opponent'])):
        raise ValueError('feature/label season-week-opponent identity conflict')

def finite(value):
    return value is not None and math.isfinite(float(value))

def aware(value,allow_missing=False):
    if pd.isna(value):
        if allow_missing:return pd.NaT
        raise ValueError('unknown required timing value')
    stamp=pd.Timestamp(value)
    if stamp.tzinfo is None:raise ValueError('explicit source timing must include timezone')
    return stamp.tz_convert('UTC')

def assert_chronology(frame):
    cutoff=frame['cutoff_utc'].map(aware)
    kickoff=frame['kickoff_utc'].map(aware)
    maximum=frame['feature_max_source_available_utc'].map(lambda v:aware(v,True))
    if cutoff.isna().any() or kickoff.isna().any() or (cutoff>kickoff).any() or (maximum.notna()&(maximum>=cutoff)).any():
        raise ValueError('source feature cutoff chronology failed; no subset retry')

def metric(y,p):
    e=np.asarray(p)-np.asarray(y);a=np.abs(e)
    return {'n':len(e),'MAE':float(a.mean()),'MSE':float(np.mean(e*e)),'RMSE':float(np.sqrt(np.mean(e*e))),
        'bias':float(e.mean()),'p90_absolute_error':float(np.quantile(a,.90,method='linear')),
        'p95_absolute_error':float(np.quantile(a,.95,method='linear')),'max_absolute_error':float(a.max()),
        'error_strict_lt1':float(np.mean(a<1)),'error_inclusive_le1':float(np.mean(a<=1)),
        'error_strict_lt5':float(np.mean(a<5)),'error_inclusive_le5':float(np.mean(a<=5))}

def sha(body):
    return hashlib.sha256(body).hexdigest()

def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()

def stamp(path):
    s = path.stat()
    return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns

def authenticate(ref):
    path = Path(ref["path"])
    if not path.is_absolute() or path.resolve() != path or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("canonical immutable source path required")
    before = stamp(path)
    if before[2] != ref["bytes"]:
        raise ValueError("source size differs before decode")
    body = path.read_bytes()
    if stamp(path) != before or sha(body) != ref["sha256"]:
        raise ValueError("source hash/stamp differs before decode")
    return body, before
