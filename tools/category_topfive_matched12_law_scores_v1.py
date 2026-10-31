"""Pure existing-law scores; caller owns frozen inputs and GO. No fits, I/O or point-to-law guess."""
import numpy as np
from decimal import Decimal,ROUND_FLOOR,ROUND_CEILING
VERSION='matched12-existing-law-scores-v1.1'
TOL=1e-10
def log1mexp(x):
 x=np.asarray(x,float)
 if np.isnan(x).any() or (x>0).any():raise ValueError('log complement domain')
 with np.errstate(divide='ignore',invalid='ignore'):
  return np.where(x < -np.log(2),np.log1p(-np.exp(x)),np.log(-np.expm1(x)))
def _log(x):
 with np.errstate(divide='ignore'):return np.log(x)
def _prior(prior):
 s=prior.support
 if s not in ['count','signed_integer','bernoulli']:raise ValueError('unknown prior law')
 v=float(prior.p if s=='bernoulli' else prior.q)
 if not np.isfinite(v) or not 0<=v<=1 or (s!='bernoulli' and v==1):raise ValueError('invalid prior parameter')
 if s=='signed_integer' and (not np.isfinite(prior.center) or prior.center!=int(prior.center)):raise ValueError('noninteger prior center')
 return s,v
def prior_logtails(prior,threshold):
 s,v=_prior(prior);x=np.floor(np.asarray(threshold,float))
 if np.isnan(x).any():raise ValueError('unknown threshold')
 lo=np.full(x.shape,-np.inf);hi=np.zeros(x.shape)
 if s=='bernoulli':
  mid=(x>=0)&(x<1);lo[mid]=np.log1p(-v) if v<1 else -np.inf;hi[mid]=_log(v)
  lo[x>=1]=0;hi[x>=1]=-np.inf
 elif s=='count':
  use=x>=0;hi[use]=(x[use]+1)*_log(v);lo[use]=log1mexp(hi[use])
 else:
  left=x<prior.center;right=~left
  lo[left]=(prior.center-x[left])*_log(v)-np.log1p(v);hi[left]=log1mexp(lo[left])
  hi[right]=(x[right]-prior.center+1)*_log(v)-np.log1p(v);lo[right]=log1mexp(hi[right])
 lo[np.isneginf(x)]=-np.inf;hi[np.isneginf(x)]=0
 lo[np.isposinf(x)]=0;hi[np.isposinf(x)]=-np.inf
 return lo,hi
def prior_logpmf(prior,value):
 s,v=_prior(prior);x=np.asarray(value,float);valid=np.isfinite(x)&(x==np.floor(x));out=np.full(x.shape,-np.inf)
 if s=='bernoulli':
  out[valid&(x==0)]=np.log1p(-v) if v<1 else -np.inf;out[valid&(x==1)]=_log(v)
 else:
  if s=='count':valid&=x>=0
  d=x if s=='count' else np.abs(x-prior.center)
  if v==0:out[valid&(d==0)]=0
  else:out[valid]=np.log1p(-v)-(np.log1p(v) if s=='signed_integer' else 0)+d[valid]*np.log(v)
 return out
def _law(law):
 if any(not hasattr(law,k) for k in ['support','weights','prior','a','b','crps','quantile']):raise ValueError('outcome law required, not a point')
 support=np.asarray(law.support,float);w=np.asarray(law.weights,float);s,_=_prior(law.prior)
 if w.ndim!=2 or w.shape[1]!=len(support) or not len(support) or not np.isfinite(w).all() or (w<0).any():raise ValueError('invalid empirical mass')
 valid=np.isfinite(support)&(support==np.floor(support))
 if s=='count':valid&=support>=0
 if s=='bernoulli':valid&=np.isin(support,[0,1])
 if not valid.all() or not (np.diff(support)>0).all() or not np.allclose(w.sum(1),1,atol=1e-12,rtol=0):raise ValueError('invalid support/normalization')
 if not np.isfinite([law.a,law.b]).all() or not 0<=law.a<=1 or not 0<=law.b<=1 or abs(law.a+law.b-1)>1e-12:raise ValueError('invalid mixture weights')
 return support,w
def law_logtails(law,threshold):
 support,w=_law(law);x=np.broadcast_to(np.floor(np.asarray(threshold,float)),(len(w),))
 if np.isnan(x).any():raise ValueError('unknown threshold')
 mask=support[None,:]<=x[:,None]
 elo=_log(np.where(mask,w,0).sum(1));ehi=_log(np.where(~mask,w,0).sum(1))
 elo[mask.all(1)]=0;ehi[(~mask).all(1)]=0
 plo,phi=prior_logtails(law.prior,x)
 return np.logaddexp(_log(law.a)+elo,_log(law.b)+plo),np.logaddexp(_log(law.a)+ehi,_log(law.b)+phi)
def law_logpmf(law,value):
 support,w=_law(law);x=np.broadcast_to(np.asarray(value,float),(len(w),))
 empirical=np.where(support[None,:]==x[:,None],w,0).sum(1)
 return np.logaddexp(_log(law.a)+_log(empirical),_log(law.b)+prior_logpmf(law.prior,x))
def _lattice(value,scale,contract):
 if scale not in [1,50] or (scale==50 and contract!='nick-chart-ppr-v1'):raise ValueError('integer/chart50 contract required')
 z=np.asarray(value,float)*scale
 if not np.isfinite(z).all() or (np.abs(z-np.rint(z))>1e-8).any():raise ValueError('outcome outside lattice')
 return np.rint(z)
def numeric_scores(law,actual,*,scale=1,contract=None):
 _law(law)
 if law.prior.support=='bernoulli':raise ValueError('use binary ATD score')
 z=_lattice(actual,scale,contract)
 if law.prior.support=='count' and (z<0).any():raise ValueError('negative actual count')
 return {'primary':'CRPS','CRPS':law.crps(z)/scale,'negative_log_pmf':-law_logpmf(law,z),
  'mean':np.asarray(law.mean)/scale,'median':law.quantile(.5)/scale,'scale':scale}
def threshold_probabilities(law,line,*,scale=1,contract=None):
 _law(law)
 if law.prior.support=='bernoulli':raise ValueError('ATD is not a numeric prop')
 if scale not in [1,50] or (scale==50 and contract!='nick-chart-ppr-v1'):raise ValueError('native-unit contract required')
 L=np.asarray([Decimal(str(v))*scale for v in np.broadcast_to(np.asarray(line,dtype=object),(len(law.weights),))],dtype=object)
 if not all(v.is_finite() for v in L):raise ValueError('finite original line required')
 floor=np.asarray([int(v.to_integral_value(rounding=ROUND_FLOOR)) for v in L],float)
 ceil=np.asarray([int(v.to_integral_value(rounding=ROUND_CEILING)) for v in L],float)
 _,over=law_logtails(law,floor);under,_=law_logtails(law,ceil-1)
 push=np.full(len(L),-np.inf);integer=np.asarray([v==int(v) for v in L])
 mass=law_logpmf(law,floor);push[integer]=mass[integer]
 logs=np.column_stack([under,push,over]);p=np.exp(logs)
 if np.isnan(logs).any() or (logs>TOL).any() or np.max(np.abs(p.sum(1)-1),initial=0)>TOL:raise ValueError('incoherent event probabilities')
 return {'probabilities':p,'log_probabilities':logs,'order':['under','push','over'],
  'line_ticks':L,'scale':scale,'contract':contract,'support':law.prior.support,'conditioning':'played; venue rules separate',
  'max_sum_roundoff':float(np.max(np.abs(p.sum(1)-1),initial=0)),
  'max_above_one_roundoff':float(np.max(p-1,initial=0)),'arithmetic':'direct_logtails_no_floor'}
def threshold_scores(events,actual):
 p=events['probabilities'];logs=events['log_probabilities'];z=_lattice(actual,events['scale'],events['contract'])
 z=np.broadcast_to(z,(len(p),));L=events['line_ticks'];y=np.where(z<L,0,np.where(z>L,2,1));one=np.eye(3)[y]
 if events['support']=='count' and (z<0).any():raise ValueError('negative actual count')
 primary=.5*np.sum((p-one)**2,axis=1);loss=-logs[np.arange(len(p)),y]
 decisive=np.logaddexp(logs[:,0],logs[:,2]);available=(y!=1)&np.isfinite(decisive)
 conditional=np.full(len(p),np.nan);conditional[available]=np.exp(logs[available,2]-decisive[available])
 brier=np.full(len(p),np.nan);brier[available]=(conditional[available]-(y[available]==2))**2
 ll=np.full(len(p),np.nan);ll[available]=-(logs[np.arange(len(p))[available],y[available]]-decisive[available])
 return {'primary':'HALF_THREE_OUTCOME_BRIER','Brier':primary,'log_loss':loss,'event_index':y,
  'decisive_conditional_available':available,'decisive_conditional_Brier':brier,'decisive_conditional_log_loss':ll,
  'conditional_missing_reason':'Push outcome or zero decisive mass.'}
def select_sides(events,*,minimum_confidence=0):
 if events.get('support') not in ['count','signed_integer']:raise ValueError('numeric prop only; Bernoulli/ATD forbidden')
 if minimum_confidence not in [0,.55]:raise ValueError('only P2/confidence0.55 registered')
 logs=events['log_probabilities'];u,o=logs[:,0],logs[:,2];d=np.logaddexp(u,o);valid=np.isfinite(d)
 confidence=np.full(len(d),np.nan);confidence[valid]=np.exp(np.maximum(u[valid],o[valid])-d[valid])
 side=np.full(len(d),'abstain',dtype=object);reason=np.full(len(d),'TIE',dtype=object);reason[~valid]='ALL_PUSH'
 choose=valid&(u!=o)&(confidence>=minimum_confidence);side[choose&(o>u)]='over';side[choose&(u>o)]='under';reason[choose]=''
 reason[valid&(u!=o)&~choose]='BELOW_FROZEN_CONFIDENCE'
 return {'side':side,'decisive_confidence':confidence,'abstention_reason':reason,'minimum_confidence':minimum_confidence}
def shrink_control(events):
 """Numeric control .5F+.5(U=.5,P=0,O=.5); monotone events, not a full CDF or ATD rule."""
 if events.get('support') not in ['count','signed_integer']:raise ValueError('numeric prop only; Bernoulli/ATD forbidden')
 f=events['log_probabilities'];logs=np.column_stack([np.logaddexp(f[:,0]-np.log(2),np.log(.25)),f[:,1]-np.log(2),np.logaddexp(f[:,2]-np.log(2),np.log(.25))])
 return {**events,'probabilities':np.exp(logs),'log_probabilities':logs,'arithmetic':'numeric_shrink0.5; push0.5F; notCDF'}
def binary_event_scores(law,actual):
 _law(law)
 if law.prior.support!='bernoulli':raise ValueError('binary law required')
 y=np.broadcast_to(np.asarray(actual,float),(len(law.weights),))
 if not np.isin(y,[0,1]).all():raise ValueError('binary outcomes only')
 l1=law_logpmf(law,np.ones(len(y)));l0=law_logpmf(law,np.zeros(len(y)));p=np.exp(l1)
 return {'primary':'Brier','Brier':(p-y)**2,'log_loss':-np.where(y==1,l1,l0),'probability':p,'conditioning':'played; no implied No offer'}
def loss_summary(loss):
 x=np.asarray(loss,float)
 if x.ndim!=1 or np.isnan(x).any() or np.isneginf(x).any():raise ValueError('undefined score rows cannot be dropped')
 inf=int(np.isposinf(x).sum())
 return {'n':len(x),'state':'UNAVAILABLE' if not len(x) else 'POSITIVE_INFINITY' if inf else 'FINITE','value':None if inf or not len(x) else float(x.mean()),'positive_infinite_rows':inf}
def paired_summary(candidate,control):
 a,b=np.asarray(candidate,float),np.asarray(control,float)
 if a.shape!=b.shape:raise ValueError('paired shapes differ')
 sa,sb=loss_summary(a),loss_summary(b)
 if not len(a):state,value='UNAVAILABLE',None
 elif sa['positive_infinite_rows'] and sb['positive_infinite_rows']:state,value='UNDEFINED_BOTH_MEANS_INFINITE',None
 elif sa['positive_infinite_rows']:state,value='POSITIVE_INFINITY',None
 elif sb['positive_infinite_rows']:state,value='NEGATIVE_INFINITY',None
 else:state,value='FINITE',float((a-b).mean())
 return {'paired_rows':len(a),'candidate':sa,'control':sb,'candidate_minus_control':{'state':state,'value':value},'no_rows_dropped':True}

def fictional_checks():
 from nfl_lab.cdf_engine import SupportPrior,MixtureBatch
 checks=[]
 def ok(name,test):
  if not test:raise AssertionError(name)
  checks.append(name)
 def law(s,w,prior,b=0):return MixtureBatch(s,[w],prior,prior_weight=b)
 geom=SupportPrior('count',q=.5,n=1);delta=SupportPrior('count',q=0,n=1)
 for y in [0,1,2,3]:
  f=law([y],[1.],geom);e=threshold_probabilities(f,1.5);s=threshold_scores(e,[y])
  ok('count1.5_actual'+str(y),e['probabilities'][0,2]==float(y>=2) and e['probabilities'][0,1]==0 and s['Brier'][0]==0)
 f=law([1,2],[.12,.88],geom);e=threshold_probabilities(f,1.5)
 ok('mean1.88_vs_p',np.isclose(f.mean[0],1.88) and np.isclose(e['probabilities'][0,2],.88))
 e=threshold_probabilities(law([5],[1.],delta),5);r=select_sides(e)
 ok('push_abstains',e['probabilities'][0,1]==1 and r['abstention_reason'][0]=='ALL_PUSH')
 e=threshold_probabilities(law([-2],[1.],SupportPrior('signed_integer',center=-2,q=0,n=1)),-1.5)
 lower,_=prior_logtails(SupportPrior('signed_integer',q=.5,n=1),[-2])
 ok('signed_yards',e['probabilities'][0,0]==1 and np.isclose(lower[0],-np.log(6)))
 f=law([29],[1.],SupportPrior('signed_integer',q=0,n=1));e=threshold_probabilities(f,.58,scale=50,contract='nick-chart-ppr-v1')
 ok('chart_tick_push',e['probabilities'][0,1]==1 and threshold_scores(e,[.58])['event_index'][0]==1 and numeric_scores(f,.58,scale=50,contract='nick-chart-ppr-v1')['CRPS'][0]==0)
 ok('q0_no_nan',prior_logpmf(delta,[0,1]).tolist()==[0.,-np.inf])
 f=law([0],[1.],geom,1);e=threshold_probabilities(f,2000.5)
 ok('geometric_CRPS',np.isclose(numeric_scores(f,[0])['CRPS'][0],1/3))
 ok('tail_log_finite',e['probabilities'][0,2]==0 and np.isfinite(e['log_probabilities'][0,2]))
 loss=threshold_scores(e,[2001])['log_loss'];ok('tail_loss_finite',np.isfinite(loss[0]) and loss[0]>1000)
 impossible=threshold_scores(threshold_probabilities(law([0],[1.],delta),.5),[1])['log_loss']
 ok('infinity_kept',loss_summary(impossible)['state']=='POSITIVE_INFINITY' and paired_summary(impossible,impossible)['candidate_minus_control']['state']=='UNDEFINED_BOTH_MEANS_INFINITE')
 e=threshold_probabilities(law([0,1],[.5,.5],geom),.5);shr=shrink_control(e)
 soft=threshold_probabilities(law([0,1],[.46,.54],geom),.5)
 ok('tie_shrink_Brier',select_sides(e)['side'][0]=='abstain' and select_sides(soft,minimum_confidence=.55)['side'][0]=='abstain' and np.isclose(threshold_scores(e,[1])['Brier'][0],.25) and np.allclose(shr['probabilities'].sum(1),1))
 f=law([0,1],[.3,.7],SupportPrior('bernoulli',p=0,n=1));b=binary_event_scores(f,[1]);ok('ATD_Brier',np.isclose(b['Brier'][0],.09))
 return {'state':'PASS_FICTIONAL_ONLY','cases':len(checks),'checks':checks,'NFL_labels_models_fits_inference':0}
