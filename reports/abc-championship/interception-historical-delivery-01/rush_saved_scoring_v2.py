"""Final zero-fit namespace correction; retain both failed source versions."""
from pathlib import Path
import hashlib,json
HERE=Path(__file__).resolve().parent
def main():
 go=json.loads((HERE/'RUSH_FINAL_SAVED_SCORING_GO_V1.json').read_bytes())
 assert go['state'].startswith('GO')and go['root']=='/root'
 p=HERE/'rush_saved_scoring_v1.py';raw=p.read_bytes()
 assert hashlib.sha256(raw).hexdigest()=='aee69c0b45e945e2898eee74111e79e58c9cba4341bb6512553c2e9a3a74beaf'
 replacements={
  "'RUSH_SAVED_SCORING_GO_V1.json'":"'RUSH_FINAL_SAVED_SCORING_GO_V1.json'",
  "'RUSH_SAVED_SCORING_STARTED_V1.json'":"'RUSH_SAVED_SCORING_STARTED_V2.json'",
  "'RUSH_SAVED_SCORING_FAILED_V1.json'":"'RUSH_SAVED_SCORING_FAILED_V2.json'",
  "'RUSH_FAILED_V1.json'":"'RUSH_SAVED_SCORING_FAILED_V1.json'",
  '(108,109)':'(80,81)',"'remaining_CPU_seconds':108":"'remaining_CPU_seconds':80",
  "'remaining_wall_seconds':228":"'remaining_wall_seconds':200",'signal.alarm(218)':'signal.alarm(190)',
  "prior['CPU_seconds']<132 and prior['wall_seconds']<132":"prior['CPU_seconds']<160 and prior['wall_seconds']<161",
  ".rename(columns={'side':'source_offered_side'})":".rename(columns={'side':'source_offered_side','M_point':'source_market_point','M_probability':'source_market_probability'})"}
 text=raw.decode()
 for old,new in replacements.items():
  expected=2 if old in ["'RUSH_SAVED_SCORING_GO_V1.json'","'RUSH_SAVED_SCORING_STARTED_V1.json'"]else 1
  assert text.count(old)==expected,(old,text.count(old));text=text.replace(old,new)
 exec(compile(text,'<exact retained scoring adapter plus root-approved namespace/remaining-budget changes>','exec'),{'__file__':str(Path(__file__).resolve()),'__name__':'__main__'})
if __name__=='__main__':main()
