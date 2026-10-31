"""Runtime-binding correction only; prior failed wrapper remains unchanged."""
from pathlib import Path
import hashlib
root=Path(__file__).resolve().parents[1]
new=root/'tools/category_topfive_matched12_score_v1_1.py'
assert hashlib.sha256(new.read_bytes()).hexdigest()=='26a83d90463146bc689e4595d28a34b794d1aec7733f4fdd37a9b8cd42703fcb'
p=root/'tools/category_topfive_matched12_score_checks_v1_1.py'
prefix=p.read_text().split('exec(compile')[0]
for name in ['category_topfive_matched12_score_v1.py','category_topfive_matched12_score_v1_1.py']:prefix=prefix.replace(name,'tools/'+name)
ns={'__file__':__file__};exec(compile(prefix,str(p),'exec'),ns)
source=ns['source'].replace('FICTIONAL_RESULT_V2.json','FICTIONAL_RESULT_V2_1.json')
assert "'tools/category_topfive_matched12_score_v1_1.py'" in source and "'tools/category_topfive_matched12_score_v1.py'" not in source
exec(compile(source,str(p),'exec'),{'__name__':'__main__','__file__':__file__})
