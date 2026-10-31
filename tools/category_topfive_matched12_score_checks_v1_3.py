"""Final root-authorized fictional run, exact new worker binding before execution."""
from pathlib import Path
import hashlib
root=Path(__file__).resolve().parents[1]
new=root/'tools/category_topfive_matched12_score_v1_2.py'
assert hashlib.sha256(new.read_bytes()).hexdigest()=='ab7775aae5a9178ed82d28217510f328d9903ef20633614c9a2c6bed02c67228'
p=root/'tools/category_topfive_matched12_score_checks_v1_1.py'
prefix=p.read_text().split('exec(compile')[0]
prefix=prefix.replace('category_topfive_matched12_score_v1.py','tools/category_topfive_matched12_score_v1.py').replace('category_topfive_matched12_score_v1_1.py','tools/category_topfive_matched12_score_v1_2.py')
ns={'__file__':__file__};exec(compile(prefix,str(p),'exec'),ns)
source=ns['source'].replace('FICTIONAL_RESULT_V2.json','FICTIONAL_RESULT_V3.json').replace('matched12-score-fictional-v1.1','matched12-score-fictional-v1.2')
assert "'tools/category_topfive_matched12_score_v1_2.py'" in source and "'tools/category_topfive_matched12_score_v1.py'" not in source
exec(compile(source,str(p),'exec'),{'__name__':'__main__','__file__':__file__})
