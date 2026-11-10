"""Plain aggregate projection of frozen C03-on-A scores; no row/model access."""
from __future__ import annotations
import csv,gzip,hashlib,io,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'reports/abc-championship/profile-increment-to-release-01/closure-next-02'
SOURCE=BASE/'C03_RECEPTION_SCORES_V1.json.gz'
DEST=BASE/'c03-public-v1'
SOURCE_SHA='f50f710c41de70e6ff4998f701e259ef532a5cf3c99d3ac7f3be9bfb6e1035e8'
LIMIT=61440

def sha(b):return hashlib.sha256(b).hexdigest()
def val(x):return json.dumps(x,sort_keys=True,separators=(',',':'))if isinstance(x,(list,dict))else x
def render(rows,fields):
 out=io.StringIO(newline='');w=csv.DictWriter(out,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows([{k:val(r.get(k))for k in fields}for r in rows]);return out.getvalue().encode()

def main():
 raw=SOURCE.read_bytes();assert sha(raw)==SOURCE_SHA
 result=json.loads(gzip.decompress(raw));assert result['state']=='SAVED_NEW_C03_RECEPTION_POINTS_SCORED'
 assert not DEST.exists();DEST.mkdir();files=[]
 def emit(stem,rows):
  assert rows;fields=list(rows[0]);chunk=[];part=1
  def write(rr,n):
   b=render(rr,fields);assert len(b)<=LIMIT;name=f'{stem}_{n:03}.csv';(DEST/name).write_bytes(b);files.append(dict(path=name,rows=len(rr),bytes=len(b),sha256=sha(b)))
  for r in rows:
   if chunk and len(render(chunk+[r],fields))>LIMIT:write(chunk,part);part+=1;chunk=[]
   chunk.append(r)
  if chunk:write(chunk,part)
 ss=result['summaries'];annual={(r['candidate_id'],r['view'],str(r['week_view'])):r for r in ss if r['source_panel']=='ANNUAL_NAMED_NJ'}
 def summary(r):
  actual=annual[r['candidate_id'],r['view'],str(r['week_view'])]['actual_scored_weeks']if r['source_panel']!='SITE_RECORDED_DK_JURISDICTION_UNKNOWN'else[]
  z=dict(category='rec',roles='WR_TE',requested_period='2026_W1_W8',view=r['view'],source_panel=r['source_panel'],week_view=r['week_view'],procedure=r['candidate_id'],all_graded_weeks=r['actual_scored_weeks'],actual_retained_threshold_weeks=actual,eligible=r['eligible'],selected=r['COMBINED']['selected'],unavailable=r['unavailable'],abstained=r['abstentions'],unknown_participation=r['states'].get('UNKNOWN_PARTICIPATION',0),missing_actual=r['states'].get('MISSING_ACTUAL',0),pending=r['states'].get('PENDING',0),DNP=r['states'].get('DNP',0),push=r['states'].get('PUSH',0),games=r['games'],player_games=r['player_games'],fallback_outputs=r['fallback_outputs'],profile_covered=r.get('profile_covered_outputs'),any_imputed=r.get('any_imputed_outputs'))
  for side in ['OVER','UNDER','COMBINED']:
   for k in ['selected','wins','losses','decided','rate']:z[side.lower()+'_'+k]=r[side][k]
  for k in ['scored','MAE','MSE','RMSE','bias','absolute_error_p90_nearest_rank','max_absolute_error']:z['numerical_'+k]=r['numerical'].get(k)
  z['unavailability_reasons']=r['unavailable_reasons'];z['probabilities']='N/A_SAVED_POINTS_ONLY';z['evidence']='CURRENT_VINTAGE_7DAY_QUOTE_TIME_UNVERIFIED'if r['source_panel']=='ANNUAL_NAMED_NJ'else'SITE_OFFER_STATUS_UNQUALIFIED_DIAGNOSTIC'if r['source_panel']=='SITE_RECORDED_DK_JURISDICTION_UNKNOWN'else'MIXED_DIAGNOSTIC_SEPARATE_SOURCE_TABLES';return z
 cumulative=[r for r in ss if r['week_view']=='ALL'];newweekly=[r for r in ss if r['week_view']!='ALL'and r['candidate_id'].startswith('C-RECEIVING-PROFILE-INCREMENT-v2::')]
 assert len(cumulative)==132 and len(newweekly)==252
 emit('CUMULATIVE_ALL_PROCEDURES',[summary(r)for r in cumulative]);emit('WEEKLY_NEW_C03',[summary(r)for r in newweekly])
 def pair(r):
  n=r['numerical_paired'];return dict(category='rec',view=r['view'],source_panel=r['source_panel'],left=r['left'],right=r['right'],common_decided=r['common_decided'],left_wins=r['left_wins'],right_wins=r['right_wins'],win_change=r['win_change'],side_disagreements=r['side_disagreements'],game_clusters=r['game_clusters'],week_clusters=r['week_clusters'],common_mask_sha256=r['common_mask_sha256'],accuracy_game_interval95=r['paired_accuracy_change_interval95'],accuracy_week_interval95=r['paired_accuracy_week_interval95'],common_numerical=n['common_cases'],MAE_change=n['MAE_change'],MAE_game_interval95=n['game_interval95'],numeric_mask_sha256=n['common_mask_sha256'])
 assert len(result['paired'])==600;emit('MATCHED_NEW_PAIRS',[pair(r)for r in result['paired']])
 manifest=dict(id='A-NEXT02-C03-PLAINTEXT-AGGREGATES-v1',source_score_sha256=SOURCE_SHA,source_score_compressed_bytes=len(raw),source_summary_cells=1056,published_cumulative_summary_cells=132,published_new_weekly_summary_cells=252,reused_old_weekly_not_republished=672,source_new_pair_cells=600,published_new_pair_cells=600,candidates=22,new_C03_point_products=6,old_procedure_products=16,source_reused_old_summary_cells=768,new_summary_cells=288,files=files,private_rows_or_player_ids=0,new_scores_by_exporter=0,no_omission_based_on_outcomes=True,older_weekly_scope='Unchanged672oldweeklycells remain in full retained score and prior own exports. This projection publishes every newC03weekly cell and every newpair; no losses filtered.',limits=['No probabilities/EV/TopPicks inferred from mean or median points','W1-5annual actual thresholds retain unverified quote clocks; W6-7site offers unqualified anddiagnostic','C03 point7week replay cannot inherit probability/currentquery/rankedproduct qualification','Full733 preserves55unavailable plus11selectedunknown; constants/A have66unknown and0unavailable, notdifferentdecidedoutcomes','Repeatedviews overlap; do notpool weekly/source/full/fixed masks twice'])
 (DEST/'MANIFEST_V1.json').write_text(json.dumps(manifest,indent=2)+'\n')
 (DEST/'README.md').write_text('# C03 saved points on A reception offers\n\nUnchanged C baseline and new R1/R2/R3 own mean/median products scored on the original A733 WR/TE board, with fixed667 common cases retained. Rates are fractions; empty cells are N/A and explicit zero is numeric0.\n\nAnnual source W1–5 and site W6–7 diagnostics are separate. Quote timing is unverified; no original issued-pick, executable price, venue settlement, ROI or current release claim. New point-direction weeks do not establish probability or Top Picks history.\n\nAll22 procedures appear in cumulative tables, every newC03 weekly cell and every registered newpair are exported including losses. The unchanged672olderweeklycells are retained in the exact full private score and referenced prior exports. No player identity, raw row or private locator is published. Complete hashes and coverage are in MANIFEST_V1.json. File splitting is size-only, never score-based.\n')
 print(json.dumps(dict(files=len(files),rows=sum(r['rows']for r in files),bytes=sum(r['bytes']for r in files),manifest_sha256=sha((DEST/'MANIFEST_V1.json').read_bytes()))))

if __name__=='__main__':main()
