"""Plaintext projection of completed A point-pair aggregates; never NFL scoring.

Input is the exact completed aggregate result only. No source vectors, native
stores, models, evaluators, inference adapters or network tools are imported.
All rows survive, including losses, unknowns, unavailable and empty week cells.
"""
from pathlib import Path
import argparse,collections,csv,datetime,gzip,hashlib,io,json,os,resource,sys,time
VERSION='A-CATEGORY-DECISION-POINT-PAIRS-PUBLIC-v1'
LIMIT=60*1024
PACKAGE_LIMIT=5*1024**2

def sha(b):return hashlib.sha256(b).hexdigest()
def enc(v):return(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def check(v,m):
 if not v:raise ValueError(m)
def safe(v):
 if isinstance(v,str):check(not any(t in v for t in ['/'+'tmp/','/'+'workspace/','file://','s3://']),'private locator in public projection')
 elif isinstance(v,dict):
  for k,x in v.items():safe(k);safe(x)
 elif isinstance(v,list):
  for x in v:safe(x)
def project_summary(r):
 z={k:v for k,v in r.items()if k not in ['OVER','UNDER','COMBINED']}
 for side in ['OVER','UNDER','COMBINED']:
  for k,v in r[side].items():z[side.lower()+'_'+k]=v
 z['available']=r['eligible']-r['unavailable']
 z['probability_confidence']='N/A_POINT_ONLY;NO_INFERRED_PROBABILITY_OR_EV'
 z['fallback_interpretation']='RECORDED_STATES_ONLY;None_IS_UNSPECIFIED_NOT_A_LEARNED_ONLY_CLAIM'
 safe(z);return z
def project_pair(r):
 z=dict(r);z['probability_confidence']='N/A_POINT_ONLY;NO_INFERRED_PROBABILITY_OR_EV';safe(z);return z
def textcell(v):
 if isinstance(v,(dict,list,bool)):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False)
 if v is None:return''
 check(v!='','empty text needs explicit encoding; cannot conflate with null')
 return str(v)
def render(rows,fields):
 s=io.StringIO(newline='');w=csv.DictWriter(s,fieldnames=fields,lineterminator='\n');w.writeheader()
 for r in rows:w.writerow({k:textcell(r.get(k))for k in fields})
 return s.getvalue().encode()
def shards(stem,rows):
 fields=list(rows[0]);out=[];chunk=[]
 for r in rows:
  check(list(r)==fields,'projection schema varies across rows')
  if chunk and len(render(chunk+[r],fields))>LIMIT:
   out.append((stem+'_%03d.csv'%(len(out)+1),render(chunk,fields),len(chunk)));chunk=[]
  chunk.append(r)
 if chunk:out.append((stem+'_%03d.csv'%(len(out)+1),render(chunk,fields),len(chunk)))
 check(all(len(b)<=LIMIT for _,b,_ in out),'single aggregate row exceeds file cap');return out

def own(r):
 fields=['category','candidate_id','view','source_panel','week_view','eligible','unavailable','abstentions','coverage','games','player_games','weeks','actual_scored_weeks','states','fallback_states','unavailable_reasons','eligible_mask_sha256','decided_mask_sha256','numerical','uncertainty']
 z={k:r.get(k)for k in fields};z.update({k:r[k]for k in ['OVER','UNDER','COMBINED']});return z

def leaders(rows,side):
 valid=[r for r in rows if r[side]['rate']is not None]
 best=max((r[side]['rate']for r in valid),default=None)
 return[own(r)for r in valid if r[side]['rate']==best]

def headline(data):
 out=[]
 for cat in sorted({r['category']for r in data['summaries']}):
  for view in ['FULL_ELIGIBLE_ANNUAL_BOARD','ORIGINAL_QUERY_INTERSECTION']:
   s=[r for r in data['summaries']if r['category']==cat and r['view']==view and r['week_view']=='ALL']
   nonconstant=[r for r in s if not r['candidate_id'].startswith('ALWAYS_')];groups=collections.defaultdict(list)
   for r in s:groups[r['decided_mask_sha256']].append(r)
   leading=leaders(nonconstant,'COMBINED');ids={r['candidate_id']for r in leading}
   pairs=[r for r in data['paired']if r['category']==cat and r['view']==view and r['left']in ids]
   numeric=[r for r in nonconstant if r['numerical']['MAE']is not None];bestmae=min((r['numerical']['MAE']for r in numeric),default=None)
   out.append(dict(category=cat,view=view,highest_observed_nonconstant_complete_procedure=leading,complete_constant_controls=[own(r)for r in s if r['candidate_id'].startswith('ALWAYS_')],leaders_on_identical_decided_masks=[dict(decided_mask_sha256=k,combined_leaders=leaders(v,'COMBINED'))for k,v in sorted(groups.items())],raw_Over_maxima_own_sample=leaders(s,'OVER'),raw_Under_maxima_own_sample=leaders(s,'UNDER'),own_population_lowest_MAE=[own(r)for r in numeric if r['numerical']['MAE']==bestmae],leading_procedure_registered_paired_comparisons=pairs,warning='Raw side subsets are different; never splice. Own-pool maxima and different mask groups are not universal paired superiority. Existing incumbent/earlier prevalence absent unless separately bound.'))
 return dict(id=VERSION+'-HEADLINE',source_aggregate_sha256=data.get('_source_sha256'),panels=out,probability='NONE_PROVIDED_OR_INFERRED',scope='Existing aggregate projection only; no new NFL forecasts, labels, grades or independent fit evidence.')

def main(a):
 start=time.monotonic();cpu=time.process_time();resource.setrlimit(resource.RLIMIT_CPU,(55,60));resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,)*2)
 check(not a.output_dir.exists()and not a.headline_output.exists(),'immutable projection destination exists')
 raw=a.score.read_bytes();check(sha(raw)==a.score_sha256 and len(raw)<=1048576,'exact completed aggregate bytes differ or exceed bound')
 decoded=gzip.decompress(raw);check(len(decoded)<=32*1024**2,'decoded aggregate size exceeds envelope');data=json.loads(decoded)
 check(data['state']=='COMPLETED_A_SAVED_POINT_ANNUAL_COMMON_COMPARISONS','result has not completed')
 check(data['summary_cells']==1782==len(data['summaries'])and data['paired_cells']==768==len(data['paired']),'registered finite aggregate counts differ')
 check(data['counts']==dict(new_fits=0,new_model_inference=0,new_source_collection=0,native_writes=0,production_writes=0),'source comparison scope differs')
 check(len(data['aggregate_parity'])==474 and all(x['match']for x in data['aggregate_parity']),'original weekly and annual parity did not pass')
 data['_source_sha256']=sha(raw);summaries=[project_summary(r)for r in data['summaries']];pairs=[project_pair(r)for r in data['paired']]
 payloads=shards('OWN_RECORDS_WEEKLY_AND_CUMULATIVE',summaries)+shards('REGISTERED_MATCHED_PAIRS',pairs)
 files=[dict(path=n,rows=count,bytes=len(b),sha256=sha(b))for n,b,count in payloads]
 manifest=dict(id=VERSION,state='EXACT_LOSSLESS_AGGREGATE_PROJECTION_NO_SCORING',source=dict(filename=a.score.name,compressed_bytes=len(raw),compressed_sha256=sha(raw),decoded_bytes=len(decoded),decoded_sha256=sha(decoded),root_protocol_sha256=data['root_protocol_sha256']),exporter=dict(path='tools/category_decision_public_aggregate_export_v1.py',bytes=Path(__file__).stat().st_size,sha256=sha(Path(__file__).read_bytes())),source_member_sha256=data['source_member_sha256'],source_membership_sha256=data['membership_sha256'],source_inventory=data['source_inventory'],source_original_point_products=data['original_point_products'],source_counts=data['counts'],source_runtime=data['runtime'],source_resource_cost=data['resources'],summary_rows=len(summaries),paired_rows=len(pairs),old_annual_and_weekly_parity_checks=474,files=files,max_csv_bytes=LIMIT,cell_encoding='Strings remain literal; integers/floats use round-trip scalar representation; nested dict/list/bool use canonical JSON. Empty scalar cell is explicit null/N/A, never zero. Empty text is rejected to avoid conflation.',omission_policy='All1782summary/768pairedcells retained without outcome-based filtering, including W6-8emptycells. No opaque aggregate ZIP/gzip, original source rows, player vectors, model bytes or private locators published.',population_scope='FULL_ELIGIBLE preserves actual source board and unavailable forecasts; ORIGINAL_QUERY_INTERSECTION is the predeclared historical reconstructed query universe. EXPECTED_POPULATION filename does not authenticate historical roster availability.',evidence_tier='2026W1-5retainedactual-line quote/decisiontimeunverified current-vintage seven-day reconstruction/exposed development; actualscoredweekslistedpercell. W6-8empty means absent from this exact annual panel, not absent everywhere.',product_scope='Point direction and matched numerical metrics only. No probability/confidence/EV/TopPicks inferred. None fallback states remain unspecified; no learned-only claim.',rights='Public aggregate code and manifests only; public receipt does not grant private raw rows, models or source clocks. No C admission, website delivery or release implied.')
 safe(manifest);mb=enc(manifest);index=render(files,['path','rows','bytes','sha256']);hb=enc(headline(data));safe(json.loads(hb))
 readme='''# A original saved-point comparisons — public aggregate projection

This package retains every weekly/cumulative own-side and registered paired comparison from the completed saved-output result. It performs no scoring, model inference, fit, original-source retrieval or native-store access. Exact input/output hashes and file bindings are in MANIFEST_V1.json and INDEX.csv.

The ten categories have 79 original point products and two constant controls per category. The full eligible source board and original registered query intersection remain separate. The historical query universe is current-vintage reconstruction; its filename does not authenticate pregame roster availability. Source quote/decision clocks remain unverified.

W1–5 actual retained lines are the only scored weeks here. Empty W6–8 cells preserve the requested window; they do not claim every other source panel is unavailable. Unknown participation, missing actuals, missing forecasts, abstentions and recorded fallback states remain explicit. A null/None fallback flag is unspecified, not an independent claim that every output was learned.

Direction, numerical accuracy, probability quality and complete Top Picks are different products. There are no inferred probabilities or EV estimates. The exact incumbent and an earlier-only prevalence rule are unavailable on these exact rows unless separately bound. Constant controls are diagnostics, not automatically admitted live strategies.

Raw maxima retain their own side counts. Do not splice separate Over and Under leaders, pool overlapping masks, transplant intervals to another population, or call the exposed retrospective winner a live selector. Five scored weeks establish duration only under this evidence tier; operational and scientific admission remain separate.
'''.encode()
 payloads += [('MANIFEST_V1.json',mb,0),('INDEX.csv',index,0),('README.md',readme,0)]
 total=sum(len(b)for _,b,_ in payloads)+len(hb);planned=a.already_planned_public_bytes+total
 cost=dict(new_package_bytes=total,already_planned_public_bytes=a.already_planned_public_bytes,total_planned_public_bytes=planned,maximum_total_public_bytes=PACKAGE_LIMIT,data_CSV_files=len(files),max_CSV_bytes=max(r['bytes']for r in files),headline_bytes=len(hb),manifest_bytes=len(mb),CPU_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-start,RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
 if planned>PACKAGE_LIMIT:
  print(json.dumps(dict(state='MEASURED_PUBLIC_BUDGET_EXCESS_NO_FILES_WRITTEN',cost=cost)));return 2
 a.output_dir.mkdir()
 for name,b,_ in payloads:
  with(a.output_dir/name).open('xb')as f:f.write(b);f.flush();os.fsync(f.fileno())
 with a.headline_output.open('xb')as f:f.write(hb);f.flush();os.fsync(f.fileno())
 # Verify every CSV row round trip against its completed source projection.
 actual=[]
 for name,b,count in payloads:
  if name.startswith('OWN_RECORDS_')or name.startswith('REGISTERED_MATCHED_'):
   rows=list(csv.DictReader(io.StringIO((a.output_dir/name).read_text())));check(len(rows)==count,'CSV row count mismatch');actual.extend(rows)
 expected=summaries+pairs;check(len(actual)==len(expected),'aggregate projection lost rows')
 for got,want in zip(actual,expected):check(got=={k:textcell(v)for k,v in want.items()},'CSV cell differs from source projection')
 print(json.dumps(dict(state='PASS_ALL2550AGGREGATES_EXACT_PROJECTION_READBACK',cost=cost,manifest_sha256=sha(mb),activity=dict(new_fits=0,new_inference=0,new_grades=0,native_reads=0,native_writes=0,model_loads=0,source_HTTP=0))))
 return 0
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--score',type=Path,required=True);p.add_argument('--score-sha256',required=True);p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--headline-output',type=Path,required=True);p.add_argument('--already-planned-public-bytes',type=int,required=True);a=p.parse_args();sys.exit(main(a))
