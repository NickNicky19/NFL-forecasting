"""Typed chart points observed from genuine laws at the existing owned seam.

No source acquisition, fitting, pickle loading, forecast persistence or website
mutation occurs here. The retained producer loads the reviewed model, admits
current sources, freezes candidate bytes, then supplies its independent capture
receipt. Historical API and its original guard remain unchanged.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json

import numpy as np

from . import next_checkpoint_chart_cdf_inference as chart
from .next_checkpoint_median_policy_v2_view import (
    VERSION as POINT_VERSION, FUNCTIONAL_VERSION, consumer_view, full_law_functionals,
)

VERSION = 'nick-chart-ppr-mae-future-adapter-v1'
TARGET = 'nick-chart-ppr-v1'
KEYS = ('season', 'week', 'game_id', 'player_id')
BINDING_KEYS = frozenset({'adapter_version', 'target', 'model_sha256',
    'procedure_sha256', 'source_policy_sha256', 'feature_schema_sha256',
    'source_availability_policy'})


def _require(ok, message):
    if not ok:
        raise ValueError(message)


def _hash(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def _plain(value):
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value


def _digest(value):
    return hashlib.sha256(json.dumps(_plain(value), sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def feature_schema_sha256():
    return _digest({'target': TARGET, 'scale': 50, 'roles': chart.ROLES,
        'identity': chart.IDENTITY, 'clocks': chart.CLOCKS, 'features': chart.FEATURES})


def validate_binding(binding, *, trusted_binding):
    _require(binding == trusted_binding and set(binding) == BINDING_KEYS,
             'independently admitted exact chart binding required')
    _require(binding['adapter_version'] == VERSION and binding['target'] == TARGET,
             'separate chart target and adapter required')
    for name in ['model_sha256', 'procedure_sha256', 'source_policy_sha256', 'feature_schema_sha256']:
        _require(_hash(binding[name]), 'actual complete artifact/source/procedure identities required')
    _require(binding['feature_schema_sha256'] == feature_schema_sha256(), 'exact chart feature schema required')
    _require(isinstance(binding['source_availability_policy'], str) and bool(binding['source_availability_policy']),
             'truthful source-availability policy required')


def _key(row):
    return tuple(str(row[k]) for k in KEYS)


def predict_chart_candidates(model, queries, *, binding, trusted_binding, trusted_model_sha256):
    """Observe real laws during ONE unchanged chart prediction traversal.

    `model` must come from chart.load_reviewed_model with the approved artifact
    digest. `trusted_model_sha256` is the retained producer's restoration result,
    not a hash copied out of an incoming query. This call does not attest source
    publication truth or durable issuance. Each returned candidate needs capture.
    """
    validate_binding(binding, trusted_binding=trusted_binding)
    _require(trusted_model_sha256 == binding['model_sha256'], 'restored artifact binding differs')
    _require(isinstance(model, chart.engine.LeafCDFModel) and model.panel == 'base'
             and model.category['target'] == 'chart_lattice_002_v1'
             and model.category['support'] == 'signed_integer'
             and model.category['panels']['base'] == chart.FEATURES
             and model.category['modeled_roles'] == chart.ROLES
             and model.forest is not None and len(model.forest.estimators_) == 32
             and model.global_prior is not None, 'exact reviewed chart model/schema required')
    proofs = {}

    class ObservedModel:
        priors = model.priors

        def predict_batches(self, subset, **kwargs):
            for positions, law, reasons in model.predict_batches(subset, **kwargs):
                pos = np.asarray(positions)
                _require(pos.ndim == 1 and np.issubdtype(pos.dtype, np.integer)
                         and len(pos) == len(reasons)
                         and all(0 <= int(i) < len(subset) for i in pos),
                         'complete valid chart batch positions required')
                _require(law is not None, 'missing chart law cannot acquire a median proof')
                values = full_law_functionals(law, target=TARGET)
                _require(len(values['median']) == len(pos), 'law and query census differ')
                for j, i in enumerate(pos):
                    key = _key(subset.iloc[int(i)])
                    _require(key not in proofs, 'duplicate chart inference position')
                    proofs[key] = {'median': values['median'][j], 'mean': values['expected_mean'][j],
                        'functional_proof': {'extractor_version': FUNCTIONAL_VERSION,
                            'cdf_below': values['cdf_below_median'][j], 'cdf_at': values['cdf_at_median'][j]}}
                yield positions, law, reasons

    original = chart.predict_reviewed(ObservedModel(), queries,
        source_policy_sha256=binding['source_policy_sha256'],
        expected_source_policy_sha256=trusted_binding['source_policy_sha256'])
    _require(len(original) == len(queries) and set(proofs) == {_key(row) for row in queries.to_dict('records')},
             'complete original chart query population required')
    candidates = []
    for row in original:
        proof = proofs[_key(row['identity'])]
        _require(row['median'] == proof['median'] and row['mean'] == proof['mean'],
                 'chart scalar output and original law functional differ')
        value = _plain(deepcopy(row))
        value.update(candidate_schema=VERSION, binding=deepcopy(binding),
                     functional_proof=proof['functional_proof'])
        value['candidate_sha256'] = _digest(value)
        candidates.append(value)
    return candidates


def captured_chart_point(candidate, *, trusted_binding, capture_receipt, trusted_capture_receipt):
    """Build the MAE consumer view only after independent frozen-byte readback.

    The trusted receipt is obtained through the existing owned persistence route.
    A request cannot self-authenticate by providing its own hash as the expected
    receipt. Actual means, probabilities and original chart API are unchanged.
    """
    value = deepcopy(candidate)
    digest = value.pop('candidate_sha256', None)
    _require(_hash(digest) and digest == _digest(value), 'captured chart candidate changed')
    _require(value['candidate_schema'] == VERSION, 'exact candidate contract required')
    binding = value['binding']; validate_binding(binding, trusted_binding=trusted_binding)
    _require(value['target'] == TARGET and value['contract'] == chart.VERSION
             and value['conditional_on'] == 'played'
             and value['source_policy_sha256'] == binding['source_policy_sha256'],
             'original chart target/source/conditioning must remain explicit')
    _require(capture_receipt == trusted_capture_receipt, 'independent trusted capture receipt required')
    receipt = capture_receipt
    _require(receipt.get('candidate_sha256') == digest and receipt.get('identity') == value['identity'],
             'capture does not identify these frozen candidate bytes/opportunity')
    _require(receipt.get('target') == TARGET
             and receipt.get('information_cutoff_utc') == value['cutoff_utc']
             and receipt.get('kickoff_utc') == value['kickoff_utc'], 'capture target/cutoff differs')
    for name in ['model_sha256', 'procedure_sha256', 'source_policy_sha256']:
        _require(receipt.get(name) == binding[name], 'capture artifact/source/procedure differs')
    fallback = bool(value['fallback'])
    typed = {'schema_version': POINT_VERSION, 'target': TARGET, 'scoring_target': TARGET,
        'selection_product': 'stat_point_mae_v2', 'selection_metric': 'MAE',
        'consumer_contract_version': POINT_VERSION,
        'game_id': str(value['identity']['game_id']), 'player_id': str(value['identity']['player_id']),
        'horizon': receipt['horizon'], 'model_version': binding['model_sha256'],
        'procedure_version': binding['procedure_sha256'], 'source_policy_sha256': binding['source_policy_sha256'],
        'capture_receipt_sha256': receipt['capture_receipt_sha256'],
        'information_cutoff_utc': value['cutoff_utc'], 'issued_at': receipt['issued_at'],
        'issue_deadline_utc': receipt['issue_deadline_utc'], 'kickoff_utc': value['kickoff_utc'],
        'feature_max_source_available_utc': value['feature_max_source_available_utc'],
        'trained_prior_only': fallback, 'forecast_value': value['median'],
        'forecast_product': 'point_median', 'prediction_functional': 'full_cdf_lower_median',
        'functional_proof': value['functional_proof'], 'separate_expected_mean': value['mean'],
        'fallback': fallback, 'fallback_reason': value['fallback'],
        'original_contract_version': chart.VERSION}
    view = consumer_view(typed)
    view.update(chart_adapter_version=VERSION, original_contract_version=chart.VERSION,
        candidate_sha256=digest, capture_receipt_sha256=receipt['capture_receipt_sha256'],
        game_id=typed['game_id'], player_id=typed['player_id'], horizon=typed['horizon'],
        issued_at=typed['issued_at'], information_cutoff_utc=typed['information_cutoff_utc'],
        issue_deadline_utc=typed['issue_deadline_utc'], kickoff_utc=typed['kickoff_utc'])
    return view
