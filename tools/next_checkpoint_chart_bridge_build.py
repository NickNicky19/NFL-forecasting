"""New current-vintage 2026 PBP bridge; never changes the original label capsule.

Only exact positive actor evidence or reconciled rare-event classifications can
change a label.  Absent actors do not prove DNP or zero.  No predictive scoring.
"""
from __future__ import annotations
from collections import Counter
import copy
import gzip
import io
import json
import math
import resource
import time

import pyarrow.parquet as pq

from next_checkpoint_chart_ppr_labels import authenticate, encoded, sha, pbp_inventory, rare_classification, participation, PBP_COLUMNS
from nfl_lab.next_checkpoint_chart_ppr import NFL_FIELDS, nflverse_components, label_observation

VERSION = 'next-checkpoint-chart-2026-retained-PBP-bridge-v1'


def json_evidence(value):
    """Preserve nonfinite source states explicitly rather than inventing zeros."""
    if isinstance(value, float) and not math.isfinite(value):
        return {'source_state': 'nonfinite', 'representation': repr(value)}
    if isinstance(value, dict):
        return {k: json_evidence(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_evidence(v) for v in value]
    return value


def build_result(plan_bytes, go):
    start_cpu, start_wall = time.process_time(), time.monotonic()
    plan = json.loads(plan_bytes)
    if (plan['version'] != VERSION or plan['state'] != 'ROOT_AND_INDEPENDENT_SEALED'
        or plan['execution_authorized'] is not True
        or plan['root_registration']['registered_by'] != '/root'
        or plan['independent_review'] != 'PASS'
        or go['state'] != 'ROOT_AND_INDEPENDENT_GO'
        or go['plan_sha256'] != sha(plan_bytes)
        or go['registered_by'] != '/root' or go['independent_review'] != 'PASS'):
        raise ValueError('exact root and independent bridge plan/GO required')
    caps=plan['resources']
    if any(caps[k] != 0 for k in ('fits','forecast_inference','accuracy_comparisons','HTTP','retries')):
        raise ValueError('zero predictive work and zero acquisition lane required')
    bodies={}
    for name, ref in plan['inputs'].items():
        bodies[name], _=authenticate(ref)
    if sum(len(b) for b in bodies.values()) > caps['maximum_input_bytes']:
        raise ValueError('aggregate source byte cap')
    private=json.loads(gzip.decompress(bodies['original_label_capsule']))
    if (private['target'] != 'nick-chart-ppr-v1'
        or private['plan_sha256'] != plan['original_label_plan_sha256']
        or len(private['labels']) != 14160):
        raise ValueError('exact original complete population required')
    original_labels=private['labels']
    if len({(r['identity']['game_id'],r['identity']['team'],r['identity']['player_id']) for r in original_labels}) != 14160:
        raise ValueError('original planned identities are not unique')
    original_keys={(r['identity']['game_id'],r['identity']['team'],r['identity']['player_id']) for r in original_labels if r['identity']['season']==2026}
    if len(original_keys) != 2117:
        raise ValueError('complete original2026 population required')
    pbp_file=pq.ParquetFile(io.BytesIO(bodies['PBP2026']))
    if pbp_file.metadata.num_rows != 16380 or pbp_file.metadata.num_rows > caps['maximum_PBP_source_rows']:
        raise ValueError('retained source footer row envelope differs')
    # Materialization is restricted by source season/week predicate.  Never read
    # later confirmation games and discard them after decoding.
    pcols=['season','week','season_type',*PBP_COLUMNS]
    pbp=pq.read_table(io.BytesIO(bodies['PBP2026']),columns=pcols,
        filters=[('season','==',2026),('season_type','==','REG'),('week','<=',6)])
    touchdowns,actors=pbp_inventory(pbp)
    games=set(pbp.column('game_id').to_pylist())
    del pbp
    wcols=list(dict.fromkeys(['player_id','game_id','team','opponent_team','position','season','week','season_type',
        *NFL_FIELDS.values(),'fumble_recovery_tds','special_teams_tds','attempts','completions','carries','targets','punt_returns','kickoff_returns']))
    weekly=pq.read_table(io.BytesIO(bodies['weekly2026']),columns=wcols,
        filters=[('season','==',2026),('season_type','==','REG'),('week','<=',6),('position','in',['QB','RB','FB','WR','TE'])]).to_pylist()
    stats={}
    for r in weekly:
        key=r['game_id'],r['team'],r['player_id']
        if key in stats: raise ValueError('duplicate source weekly key')
        stats[key]=r
    if set(stats) != original_keys:
        raise ValueError('full original2026 vs source population mismatch; no subset acceptance')
    zero_contract={'version':'nflverse-chart-broad-zero-v1','qualification_id':'generator-'+plan['generator_sha256'],
        'present_group_complete':True,'return_superset_contains_all_three_classes':True,
        'recovery_superset_includes_lateral_td_recipients':True}
    labels=[]; transitions=Counter(); classifications=Counter(); rare=Counter(); changed=0; rare_manifest=[]
    for old in original_labels:
        if old['identity']['season'] != 2026:
            labels.append(copy.deepcopy(old)); continue
        identity=old['identity']; key=identity['game_id'],identity['team'],identity['player_id']; row=stats[key]
        if any(identity[k] != row[k] for k in ['game_id','team','player_id','season','week','season_type']) or identity['opponent'] != row['opponent_team']:
            raise ValueError('weekly/label exact identity mismatch')
        event_components,diagnostics=rare_classification(row,touchdowns.get(key,[]))
        # The original function's event logic is reused unchanged.  Its old
        # qualification string is reidentified only after exact identical-column
        # source/dictionary admission; never assert this2026 inventory is2024.
        for ev in event_components.values():
            ev['qualification_id']=ev['qualification_id'].replace('PBP2024-','PBP2026-retained-bridge-v1-')
        bundle=nflverse_components(row,source_ref={'sha256':plan['inputs']['weekly2026']['sha256'],
            'qualification_id':'nflverse-explicit-weekly-current-vintage-chart-v1'},
            broad_zero_contract=zero_contract,event_components=event_components)
        state,witness=participation(row,key in actors)
        new=label_observation(bundle,identity=identity,participation=state,participation_evidence=witness)
        new['rare_classification_diagnostics']=diagnostics
        # Never degrade, change or overwrite a previously qualified numeric score.
        if old['value'] is not None and new['value'] != old['value']:
            raise ValueError('new bridge conflicts with prior numeric chart label')
        if old['state'] != new['state'] or old['value'] != new['value']: changed+=1
        transitions[(old['state'],new['state'])]+=1
        classifications.update(diagnostics)
        is_rare=any(isinstance(row[k],(int,float)) and row[k]>0 for k in ['fumble_recovery_tds','special_teams_tds'])
        if is_rare:
            rare['planned']+=1;rare['numeric_before']+=old['value'] is not None;rare['numeric_after']+=new['value'] is not None
            rare_manifest.append({'identity':identity,'broad_totals':{k:row[k] for k in ['fumble_recovery_tds','special_teams_tds']},
                'source_events':json_evidence(touchdowns.get(key,[])),'classified_components':event_components,'diagnostics':diagnostics})
        labels.append(new)
    if len(labels)!=len(original_labels) or {tuple(r['identity'].items()) for r in labels}!={tuple(r['identity'].items()) for r in original_labels}:
        raise ValueError('complete output population differs')
    seasons={}
    for season in (2024,2025,2026):
        old=[r for r in original_labels if r['identity']['season']==season];new=[r for r in labels if r['identity']['season']==season]
        if season !=2026 and new!=old:raise ValueError('earlier seasons must be exact preserved labels')
        seasons[str(season)]={'planned':len(new),'numeric_before':sum(r['value'] is not None for r in old),
            'numeric_after':sum(r['value'] is not None for r in new),'states_before':dict(Counter(r['state'] for r in old)),
            'states_after':dict(Counter(r['state'] for r in new))}
    result=copy.deepcopy(private)
    result['version']=VERSION;result['plan_sha256']=sha(plan_bytes);result['labels']=labels
    result['original_label_capsule_sha256']=plan['inputs']['original_label_capsule']['sha256']
    result['bridge']={'source_sha256':plan['inputs']['PBP2026']['sha256'],'rare_manifest':rare_manifest,
        'transitions':[{'before':k[0],'after':k[1],'n':v} for k,v in sorted(transitions.items())],
        'limitations':'source-listed population only; no absent-row or event-absence participation zeros; no scientific/source-publication timing claim'}
    payload=gzip.compress(encoded(result),mtime=0)
    if len(payload)>caps['private_label_bytes']:raise ValueError('full preserved-label bridge capsule exceeds cap')
    summary={'version':VERSION,'target':'nick-chart-ppr-v1','state':'SOURCE_LABEL_CONTINUATION_COMPLETE_NO_PREDICTIVE_COMPARISON',
        'plan_sha256':sha(plan_bytes),'original_label_capsule_sha256':plan['inputs']['original_label_capsule']['sha256'],
        'seasons':seasons,'newly_qualified_or_state_changed_2026_rows':changed,'rare_2026':dict(rare),
        'classification_diagnostics':dict(classifications),'source_game_coverage':{'weekly2026_games':len({k[0] for k in original_keys}),
            'PBP_through_W6_games':len(games),'weekly2026_games_missing_PBP':len({k[0] for k in original_keys}-games)},
        'transitions':[{'before':k[0],'after':k[1],'n':v} for k,v in sorted(transitions.items())],
        'private_capsule_bytes':len(payload),'private_capsule_sha256':sha(payload),'fits':0,'forecasts':0,'accuracy_comparisons':0,'HTTP':0,
        'full_population_preserved':True,'original_capsule_unchanged':True,'predictive_population_admissible':False,
        'remaining':'2025rare classes and unresolved participation still require evidence; no event-free-only predictive sample',
        'resources':{'CPU_seconds':time.process_time()-start_cpu,'wall_seconds':time.monotonic()-start_wall,
            'peak_RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}}
    return payload,summary
