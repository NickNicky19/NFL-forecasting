"""Project independently checked aggregate scores to public CSV; no NFL grading.

Only the two exact completed aggregate files and existing public manifests are
read. No native store, private row source, model, grader or network is used.
"""
from pathlib import Path
import argparse,collections,csv,gzip,hashlib,io,json

ROOT=Path(__file__).resolve().parents[1]
LIMIT=60*1024
SOURCES={
 'B':dict(name='B_TIMING_COMPLETION_RESULTS_V1.json.gz',sha256='841d874dd4eb15d7aca10195464ba54a6200d1ee0639e89df12885bf23707cf0',bytes=358620,prefix='B-QB-ALIGNED-FRESHNESS-v1:',directory='b-timing-public-v1',category='pass_cmp',old_manifest='reports/abc-championship/profile-increment-to-release-01/closure-next-02/b-completion-public-v2/MANIFEST.json'),
 'C04':dict(name='C04_RECEPTION_RESULTS_V1.json.gz',sha256='787ad98445bb56063fed86a95cfed360e939e2a041b0ef9efe5c8f6921e9e91a',bytes=143263,prefix='C-RECEIVING-ALIGNED-TIMING-v1::',directory='c04-public-v1',category='rec',old_manifest='reports/abc-championship/profile-increment-to-release-01/closure-next-02/c03-public-v1/MANIFEST_V1.json')}
SUMMARY_KEYS=['candidate_id','view','source_panel','week_view','eligible','coverage','unavailable','abstentions','games','player_games','weeks','states','unavailable_reasons','uncertainty','numerical','actual_retained_threshold_scored_weeks','diagnostic_scored_weeks','five_actual_week_duration_only','fallback_states','no_own_history_queries','forecast_outcome_cross_counts','eligible_mask_sha256','decided_mask_sha256','actual_scored_weeks','outer_appearance_states','fallback_outputs','profile_covered_outputs','any_imputed_outputs','unknown_fallback_flags','fallback_flag_state','exact_output_alias_of','view_reuse']
B_PAIR_KEYS=['view','source_panel','left','right','common_decided','left_wins','right_wins','accuracy_change','side_disagreements','game_clusters','week_clusters','game_interval95','week_interval95','decided_mask_sha256','common_numerical','MAE_change','MAE_game_interval95','MAE_week_interval95','numerical_mask_sha256','common_law_events','Brier_change','Brier_game_interval95','Brier_week_interval95','law_mask_sha256']
C_PAIR_KEYS=['view','source_panel','left','right','common_decided','left_wins','right_wins','win_change','side_disagreements','game_clusters','week_clusters','common_mask_sha256','paired_accuracy_change_interval95','paired_accuracy_week_interval95','numerical_paired','fallback_attribution']
PROB_KEYS=['events','Brier','three_state_log_loss','infinite_log_loss_cases','neutral_binary_half_Brier','Over_event_AUC','conditioning','reliability_fixed_bins']
def sha(b):return hashlib.sha256(b).hexdigest()
def enc(v):return(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def safe(v):
 if isinstance(v,str):assert not any(t in v for t in ['/'+'tmp/','/'+'workspace/','file://','s3://']),'Private locator rejected'
 elif isinstance(v,dict):
  for k,x in v.items():safe(k);safe(x)
 elif isinstance(v,list):
  for x in v:safe(x)
def project_summary(r,kind):
 z={k:r.get(k)for k in SUMMARY_KEYS}
 z['category']=SOURCES[kind]['category'];z['role']='QB'if kind=='B'else'WR_TE';z['requested_period']='2026_W1_W8'
 for side in ['OVER','UNDER','COMBINED']:
  for k in ['selected','wins','losses','decided','rate']:z[side.lower()+'_'+k]=r[side][k]
 if kind=='B':z['probability']={k:r['probability'].get(k)for k in PROB_KEYS}
 else:z['probability']='N/A_TYPED_POINTS_ONLY;NO_PROBABILITY_LAW_OR_CONFIDENCE_INFERRED'
 z['evidence']='QUOTE_TIME_UNVERIFIED_RECONSTRUCTED_ACTUAL_LINES'if r['source_panel']=='ANNUAL_NAMED_NJ'else'OFFER_STATUS_UNQUALIFIED_SITE_THRESHOLD_DIAGNOSTIC'if r['source_panel']=='SITE_RECORDED_DK_JURISDICTION_UNKNOWN'else'MIXED_DIAGNOSTIC;SEE_SEPARATE_SOURCE_PANELS'
 safe(z);return z
def project_pair(r,kind):
 z={k:r[k]for k in(B_PAIR_KEYS if kind=='B'else C_PAIR_KEYS)};z['category']=SOURCES[kind]['category'];safe(z);return z
def render(rows,fields):
 out=io.StringIO(newline='');w=csv.DictWriter(out,fieldnames=fields,lineterminator='\n');w.writeheader()
 for r in rows:w.writerow({k:json.dumps(r[k],sort_keys=True,separators=(',',':'),allow_nan=False)if isinstance(r[k],(dict,list))else r[k]for k in fields})
 return out.getvalue().encode()
def emit(dest,stem,rows):
 assert rows;fields=list(rows[0]);files=[];chunk=[]
 def write(rr):
  body=render(rr,fields);assert len(body)<=LIMIT;name=f'{stem}_{len(files)+1:03d}.csv'
  with(dest/name).open('xb')as f:f.write(body)
  files.append(dict(path=name,rows=len(rr),bytes=len(body),sha256=sha(body)))
 for r in rows:
  assert list(r)==fields
  if chunk and len(render(chunk+[r],fields))>LIMIT:write(chunk);chunk=[]
  chunk.append(r)
 if chunk:write(chunk)
 return files
def own(r):
 z={k:r.get(k)for k in ['candidate_id','view','source_panel','week_view','eligible','coverage','unavailable','abstentions','games','player_games','states','numerical','actual_retained_threshold_scored_weeks','diagnostic_scored_weeks','actual_scored_weeks','fallback_states','fallback_outputs','unknown_fallback_flags','eligible_mask_sha256','decided_mask_sha256']}
 z.update({s:r[s]for s in ['OVER','UNDER','COMBINED']});safe(z);return z
def leaders(rows,side):
 eligible=[r for r in rows if r[side]['rate']is not None]
 if not eligible:return[]
 maximum=max(r[side]['rate']for r in eligible)
 return[own(r)for r in eligible if r[side]['rate']==maximum]
def headline(data,kind):
 prefix=SOURCES[kind]['prefix'];view='FULL_A_BOARD'if kind=='B'else'FULL_A733';out={}
 for panel in ['ANNUAL_NAMED_NJ','SITE_RECORDED_DK_JURISDICTION_UNKNOWN']:
  ss=[r for r in data['summaries']if r['view']==view and r['source_panel']==panel and r['week_view']=='ALL'];controls=[r for r in ss if not r['candidate_id'].startswith(prefix)]
  numeric=[r for r in controls if r['numerical']['MAE']is not None];minimum=min((r['numerical']['MAE']for r in numeric),default=None)
  pp=[r for r in data['paired']if r['view']==view and r['source_panel']==panel]
  contrasts=[]
  for a,b in [('F1','F0'),('F2','F0'),('F3','F2'),('F3','F1')]:
   for p in(['mean','lower_median','P2']if kind=='B'else['MEAN','MEDIAN']):
    left=f'{prefix}{a}::{p}';right=f'{prefix}{b}::{p}';found=[r for r in pp if r['left']==left and r['right']==right];assert len(found)==1;contrasts.append(project_pair(found[0],kind))
  out[panel]=dict(exact_new_procedure_own_records=[own(r)for r in ss if r['candidate_id'].startswith(prefix)],four_own_contrasts_by_product=contrasts,strongest_retained_control_combined_own_population=leaders(controls,'COMBINED'),lowest_retained_control_MAE_own_population=[own(r)for r in numeric if r['numerical']['MAE']==minimum],raw_over_maxima_with_own_sample=leaders(ss,'OVER'),raw_under_maxima_with_own_sample=leaders(ss,'UNDER'),warning='Own-population maxima are not paired superiority or a tested side-spliced policy. Separate source panels must not be pooled. Tiny maxima retain their sample.')
 return out
def export(data,kind,raw,base):
 cfg=SOURCES[kind];prefix=cfg['prefix'];ss=data['summaries'];new=[r for r in ss if r['candidate_id'].startswith(prefix)];old=[r for r in ss if not r['candidate_id'].startswith(prefix)and r['week_view']=='ALL'];pairs=[r for r in data['paired']if r['left'].startswith(prefix)or r['right'].startswith(prefix)]
 assert(len(new),len(old),len(pairs))==((972,198,2484)if kind=='B'else(384,132,588))
 omitted_old_weekly=sum(not r['candidate_id'].startswith(prefix)and r['week_view']!='ALL'for r in ss)
 assert omitted_old_weekly==(1584 if kind=='B' else 924)
 dest=base/cfg['directory'];assert not dest.exists();dest.mkdir();files=[]
 files+=emit(dest,'ALL_NEW_TIMING_WEEKLY_AND_CUMULATIVE',[project_summary(r,kind)for r in new])
 files+=emit(dest,'RETAINED_CONTROLS_CUMULATIVE',[project_summary(r,kind)for r in old])
 files+=emit(dest,'ALL_NEW_TIMING_MATCHED_PAIRS',[project_pair(r,kind)for r in pairs])
 old_path=ROOT/cfg['old_manifest'];old_raw=old_path.read_bytes()
 manifest=dict(id='A-TIMING-CONFIRM-'+kind+'-PUBLIC-AGGREGATES-v1',state='EXACT_PROJECTION_OF_COMPLETED_INDEPENDENTLY_CHECKED_AGGREGATES',source_score=dict(path=cfg['name'],compressed_bytes=len(raw),compressed_sha256=cfg['sha256'],decoded_bytes=len(gzip.decompress(raw)),decoded_sha256=sha(gzip.decompress(raw))),exporter=dict(path='tools/timing_confirm_public_aggregates_v1.py',sha256=sha(Path(__file__).read_bytes())),old_public_manifest=dict(path=cfg['old_manifest'],bytes=len(old_raw),sha256=sha(old_raw)),source_summary_cells=len(ss),new_namespace_summary_cells_published=len(new),retained_control_cumulative_cells_published=len(old),unchanged_old_weekly_cells_not_republished=omitted_old_weekly,source_pair_cells=len(data['paired']),new_namespace_pair_cells_published=len(pairs),old_old_pair_cells_not_republished=len(data['paired'])-len(pairs),files=files,data_files=len(files),aggregate_rows=sum(r['rows']for r in files),max_csv_bytes=LIMIT,player_or_offer_rows=0,private_locators=0,new_fits=0,new_inference=0,new_grades=0,omission_policy='Every new namespace summary, weekly/ALL/source panel/view, is retained, including empty/loss/unknown/fallback cells. All old controls are retained cumulatively. Unchanged old weekly and old-old pairs remain authoritative in full completed score and prior export; no outcome-based omission. F0/F1 aliases are explicitly reused and not extra learners or weeks.',limits=['Full protected compressed score remains authoritative; this is a whitelisted aggregate projection.','W1-5 retained actual lines have unverified quote timing; W6-7 site-threshold diagnostics remain separate; exact A board has noW8 rows.','No original issuance, verified settlement, price/EV/profitability, current delivery, peer admission or release established by export.','C04 points do not imply laws; newF2/F3 fallback/profile/imputation flags remain explicitly unprovided. B valid saved-law scores remain separate from direction.','All source/view/common masks overlap; no double-counting. Five historical source weeks establish duration only under actual evidence/admission tier.'])
 safe(manifest);mb=enc(manifest);assert len(mb)<=LIMIT
 with(dest/'MANIFEST_V1.json').open('xb')as f:f.write(mb)
 index=render(files,['path','rows','bytes','sha256']);assert len(index)<=LIMIT
 with(dest/'INDEX.csv').open('xb')as f:f.write(index)
 text=f'''# {kind} exact timing products on A's retained board

This is an aggregate projection of the completed, independently checked score. It performs no scoring, inference, fitting or private-row retrieval. The full compressed score remains authoritative; exact bindings and file hashes are in MANIFEST_V1.json and INDEX.csv.

All new F0–F3 products appear for every saved week, panel and view, including empty cells, losses, unavailable predictions and unknown outcomes. Retained controls appear cumulatively. Unchanged older weekly cells and old-old pairs stay linked through the prior manifest; they were not rerun. F0/F1 are exact retained baseline aliases, not new independent learners or football observations.

Annual W1–5 actual lines retain unverified quote timing. Site W6–7 thresholds are separate unqualified diagnostics. ALL is a mixed diagnostic, not seven qualified actual-offer weeks. There are no W8 rows in this A board. Repeated views overlap and must not be added.

Rates are fractions. Empty CSV cells represent null/N/A, never a replacement zero. Nested states, numerical masks, own-side counts, fallback provenance and paired uncertainty remain explicit. C04 supplies typed points only, with new F2/F3 row-level fallback/profile/imputation flags unknown. B supplies its explicit saved laws where eligible; point-only controls have no inferred confidence.

Numerical, direction, probability and ranked-selection products have different evidence. This export establishes no current packet, consumer admission, served website use, profitability or release. Five retained source weeks satisfy duration only at the disclosed retrospective tier and do not confer probability or Top Picks qualification.
'''
 with(dest/'README.md').open('x')as f:f.write(text)
 return dict(directory=cfg['directory'],data_files=len(files),aggregate_rows=manifest['aggregate_rows'],data_bytes=sum(r['bytes']for r in files),manifest_sha256=sha(mb),manifest_bytes=len(mb),new_summary_cells=len(new),old_cumulative_cells=len(old),new_pair_cells=len(pairs),all_files_within_limit=True)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',type=Path,required=True);p.add_argument('--headline-output',type=Path,required=True);a=p.parse_args();data={};raws={}
 for kind,cfg in SOURCES.items():
  raw=(a.base/cfg['name']).read_bytes();assert len(raw)==cfg['bytes']and sha(raw)==cfg['sha256'];raws[kind]=raw;data[kind]=json.loads(gzip.decompress(raw))
 out={kind:export(data[kind],kind,raws[kind],a.base)for kind in SOURCES}
 head=dict(id='A-TIMING-CONFIRM-HEADLINE-EXTRACT-v1',source_scores={kind:cfg['sha256']for kind,cfg in SOURCES.items()},source_scope='Existing completed aggregate records only; no new scores. Strongest controls and raw maxima retain their own population, coverage and sample. Annual and site-diagnostic panels separate.',panels={kind:headline(data[kind],kind)for kind in SOURCES});safe(head)
 with a.headline_output.open('xb')as f:f.write(enc(head))
 print(json.dumps(out,sort_keys=True))
if __name__=='__main__':main()
