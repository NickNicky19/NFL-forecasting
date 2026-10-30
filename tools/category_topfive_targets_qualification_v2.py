"""One new raw-weekly target join qualification, preserving prior blank-query finding.

Restricted bindings arrive through CLI plan. No player rows or fitted models
are written; the terminal result contains only safe qualification aggregates.
"""
from pathlib import Path
import argparse
import datetime
import hashlib
import importlib.util
import io
import json
import os
import resource
import signal
import sys
import time

VERSION='rec-tgt-raw-label-qualification-v2-20261029'
KEYS=['season','week','game_id','player_id']
CONTEXT=['team','opponent','position','kickoff_utc','cutoff_utc']


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--plan',required=True)
    parser.add_argument('--sha256',required=True)
    parser.add_argument('--go',required=True)
    args=parser.parse_args()
    body=Path(args.plan).read_bytes()
    assert hashlib.sha256(body).hexdigest()==args.sha256
    plan=json.loads(body)
    assert plan['version']==VERSION and plan['resources']['attempts']==1
    assert json.loads(Path(args.go).read_bytes())=={'state':'GO','root':'/root','scope':VERSION,'plan_sha256':args.sha256}
    out=Path(plan['output'])
    assert not out.exists()
    out.mkdir(parents=True)
    start,cpu=time.monotonic(),time.process_time()
    resource.setrlimit(resource.RLIMIT_CPU,(60,61))
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('90second rawlabel qualification')))
    signal.alarm(90)
    for name in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:
        os.environ[name]='1'
    def deny(event,unused):
        if event.startswith('socket.') or event in ['subprocess.Popen','os.fork','os.system','os.posix_spawn','pickle.find_class']:
            raise RuntimeError('offline childfree qualification without models')
    sys.addaudithook(deny)
    result={'version':VERSION,'state':'FAILED_RETAINED','models_fits_forecasts_HTTP_CAS':0,'automatic_retry':False}
    (out/'CONSUMED.json').write_text(json.dumps({'state':'ONE_NEW_RAW_LABEL_QUALIFICATION_ATTEMPT_CONSUMED','at_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'plan_sha256':args.sha256,'prior_attempt_not_refunded':True})+'\n')
    try:
        import numpy as np
        import pandas as pd
        import pyarrow as pa
        import pyarrow.parquet as pq
        import pyarrow.dataset as ds
        pa.set_cpu_count(1)
        pa.set_io_thread_count(1)
        def auth(ref):
            value=Path(ref['path']).read_bytes()
            assert len(value)==ref['bytes'] and hashlib.sha256(value).hexdigest()==ref['sha256']
            return value
        for ref in plan['source_pins'].values():
            auth(ref)
        inputs={name:auth(ref) for name,ref in plan['inputs'].items()}
        source=plan['source_pins']['label_module']['path']
        spec=importlib.util.spec_from_file_location('raw_target_qualification_labels',source)
        labels_module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(labels_module)
        result['fictional_source_checks']=labels_module.check_fictional()
        prior=json.loads(inputs['prior_qualification'])
        assert prior['state']=='PROVIDER_REPORTED_TARGET_LABEL_QUALIFICATION_COMPLETE'
        assert prior['evaluation']['all_role']['supported']==0
        receipt=json.loads(inputs['raw_weekly_receipt'])
        assert receipt['sha256']==plan['inputs']['raw_weekly']['sha256'] and receipt.get('status') in ['acquired','stale_cache']
        query=pq.read_table(pa.BufferReader(inputs['query']),columns=KEYS+CONTEXT,use_threads=False).to_pandas()
        assert len(query)==2999 and query.season.eq(2026).all() and query.week.between(1,6).all() and not query.duplicated(KEYS).any()
        schedule=pd.read_csv(io.BytesIO(inputs['schedule']),usecols=['season','week','game_id','game_type','home_team','away_team'])
        data=ds.dataset(plan['inputs']['raw_weekly']['path'],format='parquet')
        names=data.schema.names
        projected=list(dict.fromkeys(KEYS+['season_type','team','opponent_team','position','targets']+[n for n in plan['physical_count_fields']+plan['physical_signed_fields'] if n in names]))
        raw=data.to_table(columns=projected,filter=(ds.field('season')==2026)&(ds.field('week')>=1)&(ds.field('week')<=7)&(ds.field('season_type')=='REG'),use_threads=False).to_pandas()
        labels,audit=labels_module.qualify(raw,query,schedule,count_fields=plan['physical_count_fields'],yard_fields=plan['physical_signed_fields'])
        all_summary=labels_module.summarize(labels)
        primary=labels.loc[labels.position.isin(['RB','WR','TE'])]
        primary_summary=labels_module.summarize(primary)
        weekly={}
        for week in range(1,8):
            rows=labels.loc[labels.week.eq(week)]
            scheduled=schedule.loc[schedule.season.eq(2026)&schedule.week.eq(week)&schedule.game_type.eq('REG')]
            weekly[str(week)]={'all_role':labels_module.summarize(rows),'primary_RB_WR_TE':labels_module.summarize(rows.loc[rows.position.isin(['RB','WR','TE'])]),'scheduled_REG_games':len(scheduled),'query_games':int(rows.game_id.nunique()),'raw_stat_games':int(raw.loc[raw.week.eq(week),'game_id'].nunique()),'missing_query_games':int((~scheduled.game_id.isin(rows.game_id)).sum()),'state':'SUPPORTED_MATCHED_LABELS' if len(rows) and rows.actual.notna().any() else 'MISSING_COMPATIBLE_QUERY_OR_TARGET_LABEL_SOURCE'}
        assert all_summary['supported']>0 and primary_summary['supported']>0, 'qualification cannot admit a label-empty pilot'
        result.update(state='RAW_WEEKLY_TARGET_JOIN_QUALIFICATION_COMPLETE',product='rec_tgt_nflverse_weekly_v1',prior_blank_query_finding={'state':prior['state'],'query_target_supported':0,'preserved':True,'refit_or_budget_refund':False},training=prior['training'],evaluation={'all_role':all_summary,'primary_RB_WR_TE':primary_summary,'weekly':weekly,'intended_weeks':list(range(1,8)),'supported_weeks':[week for week in range(1,8) if weekly[str(week)]['primary_RB_WR_TE']['supported']>0]},source_join=audit,source_field='Officialweekly provider targets; field mapped unchanged, no zero-fill',participation_definition='Exact retained positive official physical-count or signed-production predicate; stats-row existence, roster status and unknown zeros do not establish played',nonfocus_credits='Only used as existing appearance witness for active target played-zero qualification; not fitted/predicted/scored as new nonfocus outputs',source_clocks='Original historical feature seven-day assumption unchanged; raw outcome receipt/capture is not original pregame publication',event_credit_exceptions='CONTEXTUAL_CODE_INSPECTION_REUSED: currentpublic aggregation usesstat115. This qualification run doesnot authenticate exacthistoricalbuilder/nullified/two-point target exclusions.',operational_target_contract='NOT_ADMITTED_CURRENT_SOURCE_CREDIT_EXCEPTION_WRAPPER_RESTORE_CONSUMER_PENDING',public_rows_exported=0,predictive_fits_forecasts_completed=0)
        assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024<=plan['resources']['RSS_bytes']
    except BaseException as exc:
        result.update(error_type=type(exc).__name__,error=str(exc))
        raise
    finally:
        signal.alarm(0)
        result['terminal_at_UTC']=datetime.datetime.now(datetime.timezone.utc).isoformat()
        result['actual']={'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}
        value=(json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
        assert len(value)<=65536
        with (out/'RESULT.json').open('xb') as handle:
            handle.write(value)
        print(json.dumps({'state':result['state'],'actual':result['actual']}))


if __name__=='__main__':
    main()
