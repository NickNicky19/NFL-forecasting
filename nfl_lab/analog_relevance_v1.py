"""Fixed chronological analog distributions for a separately registered pilot.

The two recipes share prior-only training context and features. They are
conditional-on-played marginal laws, not calibrated prop or market probabilities.
"""
from dataclasses import dataclass
import numpy as np
import pandas as pd
from .cdf_engine import MixtureBatch, SupportPrior, numeric, strings, valid_support

VERSION = 'chronological-analog-relevance-v1-20261029'
NEIGHBORS = 64
PRIOR_WEIGHT = .05
RELEVANCE_UNIFORM_WEIGHT = .5
KEYS = ['season','week','game_id','player_id']


@dataclass
class AnalogContext:
    category: dict
    features: list
    medians: np.ndarray
    scales: np.ndarray
    x: np.ndarray
    y: np.ndarray
    roles: np.ndarray
    keys: list
    support: np.ndarray
    codes: np.ndarray
    priors: dict
    global_prior: SupportPrior
    maximum_available: pd.Timestamp
    maximum_kickoff: pd.Timestamp
    source_audit: dict

    @classmethod
    def prepare(cls, train, category, features, cdf_audit, fit_cutoff):
        """One training-only transformation/context preparation per target."""
        if category['support'] != 'count' or len(features) != len(set(features)) or features != category['panels']['base']:
            raise ValueError('this finite pilot admits count targets and fixed features only')
        cutoff = pd.Timestamp(fit_cutoff)
        own_cutoff=pd.to_datetime(train.cutoff_utc,utc=True,errors='coerce')
        feature_clock=pd.to_datetime(train.feature_max_source_available_utc,utc=True,errors='coerce')
        warm=numeric(train,'f_player_games_prior')>0
        if (not own_cutoff.notna().all() or (feature_clock.notna() & (feature_clock>=own_cutoff)).any() or (feature_clock.isna() & warm).any()):
            raise ValueError('training features are not qualified at their own historical cutoff')
        available = pd.to_datetime(train.outcome_available_utc,utc=True,errors='coerce')
        kickoff = pd.to_datetime(train.kickoff_utc,utc=True,errors='coerce')
        if (not available.notna().all() or not kickoff.notna().all()
                or not (available < cutoff).all() or not (kickoff < available).all() or (own_cutoff>kickoff).any()
                or train.duplicated(KEYS).any()):
            raise ValueError('unqualified/duplicate training context')
        y = numeric(train, category['target'])
        supported = strings(train,'participation_state') == 'played'
        supported &= valid_support(y, 'count')
        selected = train.loc[supported & train.position.isin(category['modeled_roles'])].copy()
        selected = selected.sort_values(['kickoff_utc','season','week','game_id','player_id'],kind='stable')
        y = numeric(selected, category['target'])
        if len(selected) != cdf_audit['modeled_training_rows']:raise ValueError('CDF modeled training population differs')
        if len(selected) < 64:
            raise ValueError('insufficient fixed analog training context')
        priors = {str(k):SupportPrior(**v) for k,v in cdf_audit['role_priors'].items()}
        global_prior = SupportPrior(**cdf_audit['global_prior'])
        if global_prior.n != int(supported.sum()):
            raise ValueError('CDF prior was not trained on this exact supported population')
        for role,prior in priors.items():
            if prior.n != int((supported & train.position.eq(role)).sum()):
                raise ValueError('CDF role-prior population differs')
        medians,scales=[],[]
        for name in features:
            z=numeric(selected,name);finite=z[np.isfinite(z)]
            median=float(np.median(finite)) if len(finite) else 0.
            width=float(np.quantile(finite,.75)-np.quantile(finite,.25)) if len(finite) else 0.
            medians.append(median);scales.append(width if width>0 else 1.)
        medians=np.array(medians,dtype=np.float64);scales=np.array(scales,dtype=np.float64)
        matrix=cls.transform(selected,features,medians,scales)
        support,codes=np.unique(y,return_inverse=True)
        keys=[tuple(str(z) for z in row) for row in selected[KEYS].itertuples(index=False,name=None)]
        return cls(category,list(features),medians,scales,matrix,y,
                   strings(selected,'position'),keys,support,codes,priors,global_prior,
                   available.max(),kickoff.max(),
                   {'context_rows':len(selected),'supported_all_role_training_rows':int(supported.sum()),
                    'features':list(features),'neighbors':NEIGHBORS,'prior_weight':PRIOR_WEIGHT,
                    'relevance_uniform_weight':RELEVANCE_UNIFORM_WEIGHT,
                    'source_cdf_prior_audit':cdf_audit,
                    'timing':'all training outcomes qualified before fixed fit cutoff; original7day current-vintage lane',
                    'fit_cutoff':str(cutoff),'new_transform_context_fits':1,'new_CDF_fits_or_model_loads':0})

    @staticmethod
    def transform(frame,features,medians,scales):
        columns=[]
        for name,median,scale in zip(features,medians,scales):
            value=numeric(frame,name);missing=~np.isfinite(value)
            # The missing indicator is a real feature; unknown statistics stay unknown.
            columns.extend([(np.where(missing,median,value)-median)/scale,missing.astype(float)])
        x=np.asarray(np.column_stack(columns),dtype=np.float64)
        if not np.isfinite(x).all():raise ValueError('nonfinite transformed analog features')
        return x

    def predict(self, query):
        """Yield the two full laws and neighbor evidence without reading outcomes."""
        if query.duplicated(KEYS).any():raise ValueError('duplicate query identity')
        cutoffs=pd.to_datetime(query.cutoff_utc,utc=True,errors='coerce')
        kicks=pd.to_datetime(query.kickoff_utc,utc=True,errors='coerce')
        source=pd.to_datetime(query.feature_max_source_available_utc,utc=True,errors='coerce')
        history=numeric(query,'f_player_games_prior')
        if (not cutoffs.notna().all() or not kicks.notna().all() or (cutoffs>kicks).any()
                or (source.notna() & (source>=cutoffs)).any()
                or (source.isna() & (history>0)).any()
                or not (cutoffs>self.maximum_available).all()
                or not (kicks>self.maximum_kickoff).all()):
            raise ValueError('historical query/source/context clock differs')
        training_games={key[2] for key in self.keys}
        if training_games.intersection(set(query.game_id.astype(str))):
            raise ValueError('same-game retrieval forbidden')
        qx=self.transform(query,self.features,self.medians,self.scales)
        roles=strings(query,'position')
        for i,role in enumerate(roles):
            prior=self.priors.get(str(role),self.global_prior)
            reason=''
            eligible=np.flatnonzero(self.roles==role)
            if str(role) not in self.category['modeled_roles']:reason='nonmodeled_role_prior'
            elif str(role) not in self.priors:reason='global_prior_unknown_role'
            elif not np.isfinite(history[i]) or history[i]<=0:reason='cold_start_role_prior'
            elif not len(eligible):reason='no_same_role_context_prior'
            if reason:
                law=MixtureBatch(np.array([0.]),np.ones((1,1)),prior,prior_weight=1.)
                yield i,{'ANALOG_UNIFORM':law,'ANALOG_RELEVANCE':law},reason,{'neighbors':[], 'uniform_weights':[], 'relevance_weights':[], 'distances':[], 'kernel_bandwidth':None, 'uniform_ESS':None, 'relevance_ESS':None, 'training_maximum_available':str(self.maximum_available)}
                continue
            # Direct squared differences avoid cancellation in zero-distance ties.
            delta=self.x[eligible]-qx[i]
            squared=np.einsum('ij,ij->i',delta,delta,optimize=False)/self.x.shape[1]
            if not np.isfinite(squared).all():raise ValueError('nonfinite distance')
            k=min(NEIGHBORS,len(eligible))
            boundary=np.partition(squared,k-1)[k-1]
            tied=np.flatnonzero(squared<=boundary)
            chosen=tied[np.lexsort((eligible[tied],squared[tied]))[:k]]
            neighbors=eligible[chosen];distances=np.sqrt(np.maximum(squared[chosen],0.))
            uniform=np.full(k,1./k)
            bandwidth=max(float(distances[-1]),1e-6)
            kernel=np.exp(-.5*(distances/bandwidth)**2);kernel/=kernel.sum()
            relevant=RELEVANCE_UNIFORM_WEIGHT*uniform+(1-RELEVANCE_UNIFORM_WEIGHT)*kernel
            laws={}
            for method,weights in [('ANALOG_UNIFORM',uniform),('ANALOG_RELEVANCE',relevant)]:
                histogram=np.bincount(self.codes[neighbors],weights=weights,minlength=len(self.support))
                laws[method]=MixtureBatch(self.support,histogram,prior,prior_weight=PRIOR_WEIGHT)
            evidence={'neighbors':[self.keys[n] for n in neighbors],
                      'uniform_weights':uniform.tolist(),'relevance_weights':relevant.tolist(),
                      'distances':distances.tolist(),'kernel_bandwidth':bandwidth,
                      'uniform_ESS':float(1./np.sum(uniform**2)),
                      'relevance_ESS':float(1./np.sum(relevant**2)),
                      'training_maximum_available':str(self.maximum_available)}
            yield i,laws,'',evidence
