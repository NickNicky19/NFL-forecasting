"""Exploratory retained-price M/H ingredients; not authenticated market forecasts.

No action on import. Root GO is required before prices are decoded. No football
forecasts/models, outcomes, calibration, fitting, scoring, EV, HTTP or release.
"""
from __future__ import annotations
import hashlib,io,json,math,numbers,sys,time,resource,zipfile
from decimal import Decimal,InvalidOperation
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
VERSION='matched12-exploratory-excluded-book-price-packet-v1'
KEY=['season','week','game_id','player_id','target','horizon_id']
ID=KEY+['team','opponent','position','kickoff_utc','cutoff_utc','opportunity_key','source_stream','source_sha256']
PRICE=['book_id','source_collection_naive','american_over_raw','american_under_raw','valid_two_sided_prices','source_pair_fair_over','source_line','source_row_number','over_source_row_number','under_source_row_number','source_member']
FORBIDDEN={'actual','actual_value','outcome','result','win_loss','roi','prediction','point','mean','median','selected_projection','original_recorded_lean'}
BOOKS=(68,69,79)
def need(ok,msg):
 if not ok:raise ValueError(msg)
def sha(b):return hashlib.sha256(b).hexdigest()
def enc(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def known(x):
 try:return x is not None and bool(x==x)
 except (TypeError,ValueError):return False
def american(x):
 if isinstance(x,bool) or not isinstance(x,numbers.Real) or not math.isfinite(float(x)) or not float(x).is_integer() or not 100<=abs(float(x))<10000:return None
 return 1+float(x)/100 if x>0 else 1+100/abs(float(x))
def line(x):
 try:d=Decimal(str(x));return d if d.is_finite() else None
 except (InvalidOperation,ValueError,TypeError):return None
def price_q(row):
 a=american(row.get('american_over_raw'));b=american(row.get('american_under_raw'))
 if a is None or b is None:return None,'MISSING_OR_INVALID_MATCHED_PRICE_SIDE'
 if row.get('valid_two_sided_prices') is not True and row.get('valid_two_sided_prices')!=True:return None,'ORIGINAL_TWO_SIDED_PAIR_NOT_QUALIFIED'
 q0=row.get('source_pair_fair_over')
 if not isinstance(q0,numbers.Real) or not math.isfinite(float(q0)):return None,'ORIGINAL_SOURCE_MONOTONICITY_OR_PAIR_SUPPRESSION_RETAINED'
 q=(1/a)/((1/a)+(1/b))
 need(abs(q-float(q0))<=1e-12,'frozen source pair arithmetic differs')
 return q,'EXPLORATORY_PROPORTIONAL_MARGIN_Q_CONDITIONAL_DECISIVE'
def hybrid(football_over,football_under,market_q):
 v=[football_over,football_under,market_q]
 if any(isinstance(x,bool) or not isinstance(x,numbers.Real) or not math.isfinite(float(x)) or not 0<=x<=1 for x in v):return None,'SUPPORTED_PROBABILITIES_UNAVAILABLE'
 decisive=football_over+football_under
 if decisive==0:return None,'FOOTBALL_DECISIVE_PROBABILITY_ZERO_UNDEFINED'
 need(decisive<=1+1e-12,'incoherent football event probabilities')
 return .5*market_q+.5*football_over/decisive,'FIXED_HALF_COMBINATION_CONDITIONAL_DECISIVE_ONLY'
def assemble(primary,quotes):
 import pandas as pd
 need(not (FORBIDDEN&set(primary)) and not (FORBIDDEN&set(quotes)),'forecast/outcome/selection columns forbidden')
 need(set(ID+['line','book_id','source_collection_naive'])<=set(primary),'primary identity/price context incomplete')
 need(set(KEY+['source_sha256']+PRICE)<=set(quotes),'quote provenance/pair schema incomplete')
 need(not primary.duplicated(KEY).any(),'one model-independent primary opportunity required')
 need(primary.season.eq(2026).all() and primary.week.between(1,7).all(),'fixed W1-7 primary scope')
 lookup={}
 for r in quotes.to_dict('records'):
  if r['book_id'] not in BOOKS or not known(r['source_collection_naive']) or line(r['source_line']) is None:continue
  k=tuple(r[x] for x in KEY)+(int(r['book_id']),line(r['source_line']),str(r['source_collection_naive']))
  lookup.setdefault(k,[]).append(r)
 rows=[]
 for r in primary.to_dict('records'):
  out={k:r[k] for k in ID};out['line_exact']=str(line(r['line']));out['source_collection_naive']=r['source_collection_naive'] if known(r['source_collection_naive']) else None
  out.update(offering_american_over=r.get('american_over_raw'),offering_american_under=r.get('american_under_raw'),offering_source_row_number=r.get('source_row_number'),offering_source_member=r.get('source_member'),offering_book_id=int(r['book_id']) if known(r['book_id']) and r['book_id'] in BOOKS else None,reference_book_id=None,reference_source_row_number=None,reference_over_source_row_number=None,reference_under_source_row_number=None,reference_source_sha256=None,reference_source_member=None,reference_american_over=None,reference_american_under=None,market_q_over_given_decisive=None,market_q_under_given_decisive=None,market_push_probability=None,hybrid_q_weight=.5,hybrid_football_weight=.5,hybrid_probability=None,hybrid_status='PENDING_MATCHED_SUPPORTED_FOOTBALL_CONDITIONAL_PROBABILITY',samebook_q_over_given_decisive=None,samebook_control_status='NOT_AVAILABLE',statistical_conditioning='SUPPORTED_PARTICIPATION_AND_DECISIVE_THRESHOLD_RESULT;NOT_AUTHENTICATED_VENUE_CONTRACT',evidence_tier='TIMING_UNVERIFIED_EXPOSED_HISTORICAL_PRICE_RECONSTRUCTION',source_quote_time=None,quote_timing_status='NAIVE_COLLECTION_CLOCK_NOT_BOOKMAKER_QUOTE_TIME',venue_settlement_status='UNQUALIFIED_SOURCE_RULES',authentic_pregame=False,EV_or_return_supported=False)
  if out['offering_book_id'] is None:out['market_status']='UNKNOWN_OFFERING_BOOK_EXCLUSION_UNAVAILABLE'
  elif line(r['line']) is None:out['market_status']='INVALID_PRIMARY_THRESHOLD'
  elif not known(r['source_collection_naive']):out['market_status']='MISSING_PRIMARY_COLLECTION_CLOCK'
  else:
   reasons=[];out['market_status']='NO_COMPATIBLE_INDEPENDENT_TWO_SIDED_REFERENCE'
   for book in BOOKS:
    if book==out['offering_book_id']:continue
    k=tuple(r[x] for x in KEY)+(book,line(r['line']),str(r['source_collection_naive']));members=lookup.get(k,[])
    if not members:continue
    if len(members)!=1:reasons.append('AMBIGUOUS_REFERENCE_BOOK_'+str(book));continue
    q,why=price_q(members[0])
    if q is None:reasons.append(str(book)+':'+why);continue
    a=members[0];out.update(reference_book_id=book,reference_source_row_number=a['source_row_number'],reference_over_source_row_number=a['over_source_row_number'],reference_under_source_row_number=a['under_source_row_number'],reference_source_sha256=a['source_sha256'],reference_source_member=a['source_member'],reference_american_over=a['american_over_raw'],reference_american_under=a['american_under_raw'],market_q_over_given_decisive=q,market_q_under_given_decisive=1-q,market_status='SUPPORTED_EXPLORATORY_PRICE_PAIR');break
   out['reference_rejections']=';'.join(reasons)
  # Offering-book prices never enter the independent reference pipeline. This
  # separately identified arm is a non-independent mathematical control only.
  q,why=price_q(r) if out['offering_book_id'] is not None else (None,'OFFERING_BOOK_UNKNOWN');out['samebook_q_over_given_decisive']=q;out['samebook_control_status']=why
  rows.append(out)
 result=pd.DataFrame(rows);need(len(result)==len(primary) and not result.duplicated(KEY).any(),'coverage/key change')
 audit={'version':VERSION,'state':'DERIVED_PRICE_PACKET_NOT_SCORED','primary_opportunities':len(primary),'source_quote_rows':len(quotes),'independent_reference_available':int(result.market_q_over_given_decisive.notna().sum()),'samebook_control_available':int(result.samebook_q_over_given_decisive.notna().sum()),'reference_book_counts':{str(k):int(v) for k,v in result.reference_book_id.dropna().value_counts().items()},'market_status':result.market_status.value_counts().to_dict(),'by_week_target':[{'week':int(w),'target':t,'opportunities':len(g),'independent_reference_available':int(g.market_q_over_given_decisive.notna().sum()),'samebook_control_available':int(g.samebook_q_over_given_decisive.notna().sum())} for (w,t),g in result.groupby(['week','target'])],'football_values_or_models_read':0,'outcomes_scoring_fits_HTTP':0,'authentic_pregame_or_venue_EV_rows':0,'hybrid':'FROZEN.5RULE_ONLY; football conditional probability not accessed','limitations':'Collection clocks unqualified; no true fair-probability, historical execution, profitability, fullCDF or release claim. Integer-line q only conditional decisive; push/void mass unknown. Original suppressions retained.'}
 return result,audit

def materialize(config,go):
 need(go.get('state')=='ROOT_AND_INDEPENDENT_GO' and go.get('registered_by')=='/root','root and independent GO required before prices')
 need(go.get('worker_sha256')==sha(Path(__file__).read_bytes()) and go.get('config_sha256')==sha(enc(config)),'exact worker/config binding required')
 start=time.monotonic();cpu=time.process_time()
 sys.path.insert(0,str(ROOT));import nfl_lab
 need(Path(nfl_lab.__file__).resolve().parent==ROOT/'nfl_lab','root package binding')
 from tools import category_topfive_matched12_offer_driver_v1 as source,category_topfive_matched12_storage_v1 as storage
 from nfl_lab.owned_reference_batch import validate_owned_references
 for r in config['source_pins'].values():source.read_exact(r)
 store,_=storage.open_store(ROOT,allocation_sha256=config['allocation_sha256'],root_go=storage.GO,readonly=True)
 refs=[config['prepared_offers'],config['annual_container']];seen=set();batches=[]
 for owner in [store,store.complete_peer,store.complete_peer.prior_forward,store.complete_peer.legacy]:
  b={r['path']:r['sha256'] for r in refs if any(Path(r['path']).is_relative_to(Path(x)) for x in owner._roots)}
  if b:
   got,a=validate_owned_references(owner,b);seen.update(got);batches.append({'references':len(got),'full_scans':a['full_scan_calls']})
 need(seen=={r['path'] for r in refs},'all private data must authenticate original managed owner')
 import pyarrow as pa,pyarrow.parquet as pq,pandas as pd
 pa.set_cpu_count(1);pa.set_io_thread_count(1)
 with zipfile.ZipFile(io.BytesIO(source.read_exact(config['prepared_offers']))) as z:
  names=z.namelist();need(len(names)==len(set(names))<=64,'ambiguous/oversized prepared packet')
  manifest=json.loads(z.read('MANIFEST.json'))['frames'];origin=json.loads(z.read('SOURCE_CONFIG.json'))['annual']
  need(origin['container']==config['annual_container'] and origin['sha256']==config['normalized_member_sha256'],'original normalized source lineage differs')
  def read(n,columns):
   b=z.read(n);m=manifest[n];need(len(b)==m['bytes'] and sha(b)==m['sha256'],'frozen frame member changed')
   f=pq.read_table(io.BytesIO(b),columns=columns,use_threads=False).to_pandas(use_threads=False);need(len(f)==m['rows'],'source frame row count differs');return f
  primary=read('PRIMARY_FULL.parquet',list(dict.fromkeys(ID+['line']+PRICE)))
  quotes=read('ANNUAL_all_quotes.parquet',list(dict.fromkeys(KEY+['source_sha256']+PRICE)))
 need(len(primary)==config['expected_primary_rows']==3998 and len(quotes)==config['expected_quote_rows']==9896,'registered input population changed')
 result,audit=assemble(primary,quotes);buf=io.BytesIO();pq.write_table(pa.Table.from_pandas(result,preserve_index=False,nthreads=1),buf,compression='zstd');body=buf.getvalue()
 need(len(body)<=config['resources']['private_bytes'],'complete price packet exceeds registered bound')
 audit.update(source_prepared_sha256=config['prepared_offers']['sha256'],source_annual_container_sha256=config['annual_container']['sha256'],configuration_sha256=sha(enc(config)),packet_bytes=len(body),packet_sha256=sha(body),owned_reference_batches=batches,actual={'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024})
 for k in ['CPU_seconds','wall_seconds','RSS_bytes']:need(audit['actual'][k]<=config['resources'][k],'resource bound exceeded; preserve failed attempt')
 return body,audit
