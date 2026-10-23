"""Bounded offline text view for integrator assessment; no HTTP or writes."""
import hashlib, html.parser, json, resource, signal, time
from pathlib import Path
start=time.monotonic()
resource.setrlimit(resource.RLIMIT_CPU,(10,10))
signal.signal(signal.SIGALRM,lambda *_: (_ for _ in ()).throw(TimeoutError('10s wall')))
signal.alarm(10)
base=Path('/workspace/website-methods-research/resumed/participation-qualification-probe-v1-20261023/capture')
result=(base/'result.json').read_bytes()
assert hashlib.sha256(result).hexdigest()=='3223ea02ac786a874b86368b041a067040036744bdd234032437f3b537ebefbb'
path=base/'private/http/002/body.bin'
assert path.stat().st_size==351280
body=path.read_bytes()
assert hashlib.sha256(body).hexdigest()=='ae4f622e9524157641cef047a8b07b255564f85ee988f1dcefccdc038d57a559'
class Text(html.parser.HTMLParser):
    def __init__(self):super().__init__();self.skip=0;self.parts=[]
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style'):self.skip+=1
        if tag in ('p','div','li','h1','h2','h3','br'):self.parts.append('\n')
    def handle_endtag(self,tag):
        if tag in ('script','style'):self.skip=max(0,self.skip-1)
    def handle_data(self,data):
        if not self.skip:self.parts.append(data)
p=Text();p.feed(body.decode('utf-8'));text=' '.join(' '.join(p.parts).split())
terms=('automated','robot','scrap','non-commercial','personal use','license','download','data mining','commercial')
hits=[]
for term in terms:
    pos=0
    for _ in range(4):
        found=text.lower().find(term,pos)
        if found<0:break
        hits.append({'term':term,'offset':found,'context':text[max(0,found-250):found+550]});pos=found+len(term)
# Private tool output only; never copied to a public report or raw-source feed.
hits.sort(key=lambda x:x['offset']);kept=[];size=0
for hit in hits:
    if size+len(hit['context'])>12000:break
    kept.append(hit);size+=len(hit['context'])
usage=resource.getrusage(resource.RUSAGE_SELF)
assert usage.ru_maxrss*1024<134217728
print(json.dumps({'scope':'PRIVATE legal excerpts for integrator only, no public redistribution','hits':kept,'text_characters':len(text),'usage':{'wall_seconds':time.monotonic()-start,'CPU_seconds':usage.ru_utime+usage.ru_stime,'peak_RSS_bytes':usage.ru_maxrss*1024},'HTTP':0}))
