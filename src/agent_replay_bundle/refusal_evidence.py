"""Strict, non-authorizing preservation of the c7f122ba bounded evidence fields."""
from copy import deepcopy
from typing import Literal
import re

from pydantic import BaseModel, ConfigDict, ValidationError


class Evidence(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class Horizon(Evidence):
    source: Literal['runtime_proposal']
    proposal_commitment: str
    not_before: str | None
    expires_at: str | None


class Input(Evidence):
    input_type: Literal['manifest','authority_context','grant','policy','approval','evidence','role_mapping','identity','mandate','conflict']
    input_id: str
    expected: dict[str,str]
    observed: dict[str,str]
    record_commitment: str | None
    missing: bool
    previous_observed_at: str | None


class Changed(Evidence):
    input_type: Literal['grant','policy','approval','evidence','role_mapping']
    input_id: str
    expected_version: str
    observed_version: str


class Refusal(Evidence):
    refusal_id: str
    decision_id: str
    effect_id: str
    recorded_at: str
    time_source: Literal['unrecorded','control_plane','test_override']
    original_operation_horizon: Horizon | None
    operation_horizon: Horizon | None
    stage: Literal['effect_time_revalidation']
    reasons: list[str]
    changed_inputs: list[Changed]
    resolution_inputs: list[Input]


class Check(Evidence):
    check_id: str
    stage: Literal['decision','effect','claim']
    evaluated_at: str
    time_source: Literal['control_plane','test_override']
    inputs: list[Input]
    reasons: list[str]


class Closeout(Evidence):
    attempt_id: str
    effect_id: str
    original_status: str
    observed_state: Literal['applied','partial']
    observed_at: str
    reconciled_at: str


EXTENDED = {'refusals':'effect_time_refusal', 'resolution_checks':'resolution_check',
            'closeouts':'attempt_closeout', 'input_time_floors':'input_time_floors'}


def validate_run(cp, proposal):
    from .importers import ImportContractError, _aware_time
    def require(ok, reason):
        if not ok: raise ImportContractError('typed refusal profile: '+reason)
    def inputs(values):
        for x in values:
            require(bool(x.input_id), 'empty input identity')
            require(x.record_commitment is None or re.fullmatch(r'sha256:[0-9a-f]{64}',x.record_commitment), 'invalid input commitment')
            require(not x.missing or x.record_commitment is None, 'missing input claims a record commitment')
            if x.previous_observed_at is not None: _aware_time(x.previous_observed_at)
    def horizon(value, binding=None):
        if value is None: return None
        x=Horizon.model_validate(value)
        require(re.fullmatch(r'sha256:[0-9a-f]{64}', x.proposal_commitment), 'invalid horizon commitment')
        for stamp in (x.not_before, x.expires_at):
            if stamp is not None: _aware_time(stamp)
        if isinstance(binding, dict):
            require(x.proposal_commitment==binding.get('proposal_commitment'), 'original horizon commitment differs from original binding')
        return x
    try:
        require(set(EXTENDED) <= cp.keys(), 'required evidence collection missing')
        require(isinstance(cp['input_time_floors'],dict), 'time floors must be an object')
        for key,stamp in cp['input_time_floors'].items():
            require(isinstance(key,str) and bool(key), 'empty time-floor identity'); _aware_time(stamp)
        decisions={d['decision_id']:d for d in cp['decisions']}
        for d in cp['decisions']:
            inputs([Input.model_validate(x) for x in d['resolution_inputs']])
            horizon(d['operation_horizon'], d.get('binding'))
        seen=set()
        for raw in cp['refusals']:
            x=Refusal.model_validate(raw);require(bool(x.refusal_id) and x.refusal_id not in seen,'duplicate/empty refusal id');seen.add(x.refusal_id)
            horizon(raw['original_operation_horizon']);horizon(raw['operation_horizon'])
            d=decisions.get(x.decision_id)
            require(d is not None and d['effect_id']==x.effect_id,'dangling/substituted refusal binding')
            require(d['result']=='authorized' and d['binding'] is not None,'refusal requires original authorized decision')
            require(x.original_operation_horizon == (Horizon.model_validate(d['operation_horizon']) if d['operation_horizon'] is not None else None),'original horizon differs from decision')
            require(bool(x.reasons) and all(x.reasons),'refusal requires typed reasons');_aware_time(x.recorded_at);inputs(x.resolution_inputs)
            for change in x.changed_inputs:
                require(any(i.input_type==change.input_type and i.input_id==change.input_id for i in x.resolution_inputs),'changed input lacks actual read attribution')
        seen=set()
        for raw in cp['resolution_checks']:
            x=Check.model_validate(raw);require(bool(x.check_id) and x.check_id not in seen,'duplicate/empty resolution check id');seen.add(x.check_id)
            _aware_time(x.evaluated_at);inputs(x.inputs)
        for raw in cp['closeouts']:
            x=Closeout.model_validate(raw);_aware_time(x.observed_at);_aware_time(x.reconciled_at)
            require(any(a['attempt_id']==x.attempt_id and a['effect_id']==x.effect_id and a['status']==x.original_status for a in cp['attempts']),'closeout lacks original attempt lineage')
            require(any(r['effect_id']==x.effect_id and r.get('observation_accepted') and (r.get('observation') or {}).get('state')==x.observed_state and (r.get('observation') or {}).get('observed_at')==x.observed_at for r in cp['reconciliations']),'closeout lacks accepted observation lineage')
    except (ValidationError,KeyError,TypeError,AttributeError) as exc:
        raise ImportContractError('typed refusal profile: unsupported/missing evidence fields') from exc


def extend_retained_inputs(cp, bundle):
    """Rebuild all four fields for downstream semantic revalidation, not an allowlist bypass."""
    from .importers import ImportContractError
    result=deepcopy(cp)
    for field,kind in EXTENDED.items():
        rows=[deepcopy(r['data']) for r in bundle['records'] if r.get('record_type')==kind]
        if field=='input_time_floors':
            if len(rows)!=1:raise ImportContractError('typed refusal profile requires one time-floor record')
            result[field]=rows[0]
        else: result[field]=rows
    return result
