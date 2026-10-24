"""Annual priors and indexed request caching for the single dynamic backend.

No independent I/O route, evaluator, storage or execution entry point. The
already authenticated ProjectionSource owns every actual source projection.
Preparation is code-only until the combined backend receives its own freeze/GO.
"""
from collections import defaultdict
import math

from . import dynamic_opportunity_core as core
from . import dynamic_opportunity_source as source
from . import dynamic_opportunity_study as study
from .state import digest, utc

VERSION = "dynamic-opportunity-source-helpers-v2-20261024"


def _key(row, *, player_field="player_id"):
    return (row["season"], row["week"], source.canonical_team(row["team"]), row.get(player_field))


class AnnualInputs:
    """Same-source role priors and once-per-year/task/cutoff request batches.

    Backend calls prepare once/year in chronological order. Both tasks are
    prepared together while source cutoffs advance, so the second task never
    rewinds a shared source cache. Nonmodeled offers remain fallback requests.
    """
    def __init__(self, projection, calendar, plan, replay_policy):
        self.projection=projection; self.calendar=calendar; self.plan=plan; self.replay_policy=replay_policy
        self.season_calendars={year:[g for g in calendar if g["season"]==year] for year in source.YEARS}
        self.request_cache={}; self.year_metadata={}; self.efficiency_cache={}
        self.indexed=dict(statistics=0,rosters=0,qualified_history=0)
        self.raw_by_year=defaultdict(list); self.history_by_year=defaultdict(list)
        self.roster_by_player=defaultdict(list); self.history_by_player=defaultdict(list)
        self.raw_by_key=defaultdict(list); self.history_by_key=defaultdict(list)
        self.audits={}; self.prior_vectors={}; self.prepared_years=[]

    def _advance(self, cutoff):
        cache=self.projection.advance(self.calendar,cutoff)
        for kind in self.indexed:
            records=cache[kind]
            source.require(len(records)>=self.indexed[kind],"source cache may not shrink or replace admitted rows")
            for row in records[self.indexed[kind]:]:
                if kind=='statistics':
                    self.raw_by_year[row['season']].append(row); self.raw_by_key[_key(row)].append(row)
                elif kind=='rosters':
                    # All teams/statuses for the exact requested player remain;
                    # conflicting assignments are never filtered away.
                    self.roster_by_player[row.get('gsis_id')].append(row)
                else:
                    self.history_by_year[row['season']].append(row)
                    self.history_by_player[row['player_id']].append(row); self.history_by_key[_key(row)].append(row)
            self.indexed[kind]=len(records)

    def _prior(self, year, task, earliest):
        from .dynamic_opportunity_history import build_recorded_proxy_panel
        calendar=[g for g in self.calendar if g['season']<year]
        raw=[r for y,rows in self.raw_by_year.items() if y<year for r in rows]
        history=[r for y,rows in self.history_by_year.items() if y<year for r in rows]
        # Priors are repeated individual game exposures; no continuity or
        # transaction inference is needed to identify an individual source row.
        binding=source.seal_source_binding(self.plan,calendar,dict(kind='prior_row_context_only',year=year,task=task))
        credits,unmapped=source.credit_rows(raw,calendar,task=task,cutoff=earliest,
            statistics_sha256_by_season=binding['statistics_sha256_by_season'])
        panel=build_recorded_proxy_panel(calendar,credits,task=task,source_binding=binding,asof_utc=earliest)
        totals={(g['game_id'],g['team']):g for g in panel['groups']}
        players=source.qualified_player_rows(raw,history,calendar,task=task,cutoff=earliest)
        roles={}; means={}; receipts={}
        for role in core.TASK_ROLES[task]:
            records=[]; counts=[]
            for row in players:
                if row['position']!=role:
                    continue
                group=totals[row['game_id'],row['team']]
                total=group['count'] if group['state']=='RECORDED_PROXY_ONLY' else None
                records.append(core.Slot(row['player_id'],row['team'],row['season'],
                    digest(dict(kind='source_row_game_context_not_continuity',player=row['player_id'],team=row['team'],season=row['season'])),
                    task,role,row['game_id'],row['kickoff_utc'],row['available_utc'],row['participation_state'],
                    row['source_qualified'],row['count'],total))
                if row['source_qualified'] and row['participation_state']=='played' and source.finite_count(row['count']):
                    counts.append(row['count'])
            try:
                prior=core.form_prior(records,task=task,role=role,query_season=year,training_before_utc=earliest)
                roles[role]=prior; receipts[role]=prior.manifest()
            except (ValueError,TypeError,OverflowError) as error:
                # Invalid global prior is not repaired or replaced with defaults.
                roles[role]=core.Prior(task,role,year,earliest,'FALLBACK_REQUIRED',
                    'missing_or_boundary_prior_baseline_fallback',None,0,0,len(records),0,0)
                receipts[role]=dict(state='FALLBACK_REQUIRED',reason='invalid_global_prior',
                    admitted_prior_rows=0,source_rows=len(records),error_type=type(error).__name__,
                    no_numeric_prior_or_zero_outcomes_imputed=True)
            means[role]=math.fsum(counts)/len(counts) if counts else None
        return roles,means,dict(role_priors=receipts,unmapped_credit_rows=unmapped,
            source_binding_sha256=digest(binding),all_nfl_credits_complete=False,training_before_utc=earliest,
            training_seasons=list(range(2019,year)))

    def _efficiency_row(self, history):
        """Only already-qualified played, explicit equal raw/normalized fields."""
        matches=self.raw_by_key.get(_key(history),[])
        row=dict(source_qualified=False,participation_state=history['participation_state'],
                 targets=None,receptions=None,receiving_yards=None)
        if history['participation_state']!='played' or len(matches)!=1:
            return row
        raw=matches[0]
        for rawfield,normalized in (('targets','rec_tgt'),('receptions','rec'),('receiving_yards','rec_yd')):
            value=raw.get(rawfield); qualified=history.get(normalized)
            for present in (value, qualified):
                if source.missing_value(present):
                    continue
                valid=(type(present) in (int,float) and math.isfinite(present))
                if rawfield!='receiving_yards':valid &= source.finite_count(present)
                source.require(valid,'efficiency raw/qualified field conflict')
            if source.missing_value(value) or source.missing_value(qualified):
                continue
            source.require(value==qualified,'efficiency raw/qualified field conflict')
            row[rawfield]=value
        if row['targets'] is not None and row['receptions'] is not None:
            source.require(row['receptions']<=row['targets'],'incompatible explicit catch/target fields')
        row['source_qualified']=True
        return row

    def _efficiency_priors(self, year, earliest):
        result={}; audit={}
        for role in core.TASK_ROLES['rec_tgt']:
            catches=targets_c=yards=targets_y=0.; supported_c=supported_y=0; invalid=False
            for prior_year,records in self.history_by_year.items():
                if prior_year>=year:continue
                for history in records:
                    if history['position']!=role or utc(history['outcome_available_utc'])>=utc(earliest):continue
                    try:row=self._efficiency_row(history)
                    except ValueError:invalid=True;continue
                    if not row['source_qualified'] or row['targets'] is None:continue
                    if row['receptions'] is not None:
                        catches+=row['receptions']; targets_c+=row['targets']; supported_c+=1
                    if row['receiving_yards'] is not None:
                        yards+=row['receiving_yards']; targets_y+=row['targets']; supported_y+=1
            ready=not invalid and targets_c>0 and targets_y>0
            result[role]=dict(state='READY' if ready else 'FALLBACK_REQUIRED',
                reason='fixed_earlier_training_role_efficiency' if ready else 'missing_or_invalid_global_efficiency_prior',
                catch_rate=catches/targets_c if ready else None,YPT=yards/targets_y if ready else None,
                training_before_utc=earliest,training_seasons=list(range(2019,year)))
            audit[role]=dict(supported_catch_pairs=supported_c,supported_yard_pairs=supported_y,
                invalid_global_field=invalid,zero_target_lateral_yards_retained=True)
        return result,audit

    def prepare(self, year, query_rows, query_reference, prior_kinds):
        source.require(year in (2020,2021,2022,2023,2024) and year not in self.prepared_years,
                       'one registered annual preparation only')
        source.require(set(prior_kinds)==({'rush_att','rec_tgt'} if year<2022 else {'rush_att','rec_tgt','fixed_efficiency'}),
                       'exact declared annual prior vectors required')
        source.require(query_rows and all(r['season']==year for r in query_rows),'exact original annual queries required')
        earliest=min(utc(r['cutoff_utc']) for r in query_rows).isoformat()
        self._advance(earliest)
        priors={}; simple_means={}; audits={}
        for task in ('rush_att','rec_tgt'):
            priors[task],means,audits[task]=self._prior(year,task,earliest)
            simple_means[task]=means
        efficiency,effaudit=self._efficiency_priors(year,earliest) if 'fixed_efficiency' in prior_kinds else ({},{})
        self.prior_vectors[year]=dict(priors=priors,efficiency_priors=efficiency,simple_role_means=simple_means,
            training_before_utc=earliest,source_prior_audits=audits,efficiency_prior_audit=effaudit)
        self.year_metadata[year]=dict(query_reference=query_reference,query_rows=len(query_rows),earliest_cutoff=earliest)
        by_cutoff={}; offers={}
        for task in ('rush_att','rec_tgt'):
            # Generate once over the complete original ordered context. Group-
            # local enumeration must never impersonate original row ordinals.
            offers[task]=source.offer_contexts(query_rows,self.season_calendars[year],query_reference=query_reference,task=task)
            grouped=defaultdict(list)
            for offer in offers[task]:grouped[offer['cutoff_utc']].append(offer)
            by_cutoff[task]=grouped; self.request_cache[year,task]=[None]*len(query_rows)
        for cutoff in sorted(by_cutoff['rush_att'],key=utc):
            self._advance(cutoff)
            for task in ('rush_att','rec_tgt'):
                batch=by_cutoff[task][cutoff]; wanted={o['player_id'] for o in batch}
                # Index only the individual membership/history lookup. Recorded
                # proxy raw counts still include ALL positions and ALL players.
                roster=[r for pid in wanted for r in self.roster_by_player.get(pid,[]) if r['season']==year]
                history=[r for pid in wanted for r in self.history_by_player.get(pid,[]) if r['season']==year]
                packet=source.historical_requests(batch,self.season_calendars[year],self.raw_by_year[year],roster,history,
                    task=task,plan=self.plan,replay_policy=self.replay_policy)
                for request in packet['results']:
                    ordinal=request['offer']['original_query_reference']['row_ordinal']
                    source.require(self.request_cache[year,task][ordinal] is None,'duplicate original request ordinal')
                    self.request_cache[year,task][ordinal]=request
                self.audits[year,task,cutoff]=dict(source_binding=packet['source_binding'],
                    source_binding_sha256=digest(packet['source_binding']),
                    membership_manifest_sha256=packet['membership_manifest_sha256'],
                    offer_ordinals=[o['original_query_reference']['row_ordinal'] for o in batch],
                    cutoff_utc=cutoff,individual_index_filter='all available same-player rows across every team/status',
                    all_position_proxy_filter='NONE; every recorded source row retained')
        source.require(all(all(r is not None for r in self.request_cache[year,t]) for t in ('rush_att','rec_tgt')),
                       'every original annual offer needs its retained request/fallback')
        self.prepared_years.append(year)
        return self.prior_vectors[year]

    def requests_for_year(self, year, task):
        return self.request_cache[year,task]

    def efficiency_for_request(self, year, request):
        ordinal=request['offer']['original_query_reference']['row_ordinal'];key=(year,ordinal)
        if key in self.efficiency_cache:return self.efficiency_cache[key]
        if request.get('state')!='READY_CORE_REQUEST':
            result=dict(state='FALLBACK_REQUIRED',reason='target_request_not_ready',catch_rate=None,YPT=None)
        else:
            selected=[]
            for slot in request['history']:
                records=[r for r in self.history_by_player.get(slot['player_id'],[])
                         if r['season']==year and r['game_id']==slot['game_id'] and r['team']==slot['team']]
                if len(records)!=1 or utc(records[0]['outcome_available_utc'])>=utc(request['offer']['cutoff_utc']):
                    selected.append(dict(source_qualified=False,participation_state='unknown'))
                else:
                    try:selected.append(self._efficiency_row(records[0]))
                    except ValueError:
                        result=dict(state='FALLBACK_REQUIRED',reason='incompatible_fixed_efficiency_fields',catch_rate=None,YPT=None)
                        self.efficiency_cache[key]=result;return result
            role=request['offer']['position'];prior=self.prior_vectors[year]['efficiency_priors'].get(role)
            result=study.fixed_efficiency(prior,selected)
        self.efficiency_cache[key]=result
        return result

    def factored_requests(self, year, task):
        """Lossless flat tables/integer references; no repeated hash-heavy JSON.

        Backend may persist each table with its unchanged managed Parquet writer.
        The small manifest binds table hashes. No forecast/source is recomputed
        to restore the original request, including fallback and missing fields.
        """
        tables={name:[] for name in ('offers','spells','query_references','history_slots','core_queries',
                                     'proxies','slot_audits','request_tails')}
        indices={name:{} for name in tables};rows=[]
        def intern(name,value):
            if value is None:return -1
            sha=digest(value)
            if sha not in indices[name]:
                indices[name][sha]=len(tables[name]);tables[name].append(value)
            return indices[name][sha]
        for ordinal,original in enumerate(self.requests_for_year(year,task)):
            offer=dict(original['offer']);spell=offer.pop('spell');reference=dict(offer.pop('original_query_reference'))
            source.require(reference.pop('row_ordinal')==ordinal,'factored original row ordinal changed')
            offer.update(spell_index=intern('spells',spell),query_reference_index=intern('query_references',reference),
                         original_row_ordinal=ordinal)
            offer_index=intern('offers',offer)
            history=[intern('history_slots',s) for s in original['history']];audits=[]
            for item in original.get('slot_audit',[]):
                audit={k:v for k,v in item.items() if k!='proxy_partial_receipt'}
                audit['proxy_index']=intern('proxies',item.get('proxy_partial_receipt'))
                audits.append(intern('slot_audits',audit))
            excluded={'offer','offer_id','history','slot_audit','core_query','static_control_request'}
            tail={k:v for k,v in original.items() if k not in excluded}
            rows.append(dict(ordinal=ordinal,offer_index=offer_index,history_indices=history,slot_audit_indices=audits,
                core_query_index=intern('core_queries',original['core_query']),request_tail_index=intern('request_tails',tail),
                static_control_present=original['static_control_request'] is not None))
        return dict(schema_version=VERSION+'-factored-requests',year=year,task=task,original_rows=len(rows),
            records=rows,tables=tables,
            batch_replay_manifests=[audit for (y,t,_),audit in self.audits.items() if y==year and t==task],
            source_plan_sha256=digest(self.plan),no_dropped_rows=True,
            restore_entry='nfl_lab.dynamic_opportunity_source_helpers.restore_factored_requests')

    def release_requests(self, year):
        """Only in-memory copies; never deletes private evidence or source data."""
        for task in ('rush_att','rec_tgt'):self.request_cache.pop((year,task),None)
        self.efficiency_cache={key:value for key,value in self.efficiency_cache.items() if key[0]!=year}


def restore_factored_requests(packet):
    """Pure codec inverse, no source/model/prediction/scoring or inferred data."""
    source.require(packet['schema_version']==VERSION+'-factored-requests' and packet['no_dropped_rows'] is True,
                   'exact factored-request codec required')
    tables=packet['tables'];result=[]
    def item(table,index):
        if index==-1:return None
        source.require(type(index) is int and 0<=index<len(tables[table]),'factored reference outside exact table')
        return dict(tables[table][index])
    source.require(len(packet['records'])==packet['original_rows'],'factored request population changed')
    for ordinal,row in enumerate(packet['records']):
        source.require(row['ordinal']==ordinal,'factored request order changed')
        offer=item('offers',row['offer_index']);spell_index=offer.pop('spell_index')
        reference_index=offer.pop('query_reference_index')
        source.require(offer.pop('original_row_ordinal')==ordinal,'original ordinal changed')
        offer.update(spell=item('spells',spell_index),
                     original_query_reference={**item('query_references',reference_index),'row_ordinal':ordinal})
        history=[item('history_slots',i) for i in row['history_indices']]
        query=item('core_queries',row['core_query_index']);audits=[]
        for index in row['slot_audit_indices']:
            audit=item('slot_audits',index);proxy=item('proxies',audit.pop('proxy_index'))
            audits.append(dict(audit,proxy_partial_receipt=proxy))
        request=item('request_tails',row['request_tail_index'])
        static=None
        if row['static_control_present']:
            source.require(query is not None,'static control cannot lose its core query')
            static=dict(history_sha256=digest(history),core_query_sha256=digest(query),volume=request['volume'],
                prior='EXACT_SAME_TRAINING_PRIOR_REQUIRED',kappa='EXACT_SAME_SELECTED_SETTING_REQUIRED',
                new_fit=False,numeric_distribution='NONE')
        request.update(offer=offer,offer_id=offer['offer_id'],history=history,slot_audit=audits,
                       core_query=query,static_control_request=static)
        result.append(request)
    return result
