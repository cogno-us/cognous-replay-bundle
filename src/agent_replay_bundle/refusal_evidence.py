"""Strict, non-authorizing preservation of the c7f122ba bounded evidence fields."""
from copy import deepcopy
from typing import Any, Literal
import re

from pydantic import BaseModel, ConfigDict, ValidationError


class Evidence(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class Extensible(Evidence):
    """Reserved ``extensions`` member (ODES execution-attempt-lifecycle contract, decision 16): ``x-`` named members
    are accepted and preserved verbatim (the retained record is the raw object); their names are checked by
    ``check_extensions``. They carry no authority and are ignored by the journal-to-check content binding."""
    extensions: dict[str, Any] | None = None


def check_extensions(raw, label):
    from .importers import ImportContractError, EXTENSION_NAME
    ext = raw.get('extensions') if isinstance(raw, dict) else None
    if ext is None: return
    bad = sorted(str(k) for k in ext if not (isinstance(k, str) and EXTENSION_NAME.match(k)))
    if bad:
        raise ImportContractError(f"typed refusal profile: {label}.extensions names must start with 'x-': " + ",".join(bad),
                                  'invalid_extension_key')


class Horizon(Evidence):
    source: Literal['runtime_proposal']
    proposal_commitment: str
    not_before: str | None
    expires_at: str | None


class Input(Extensible):
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


class Check(Extensible):
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


class AuthorityInput(Input):
    input_type: Literal['manifest','authority_context','grant','policy','approval','evidence','role_mapping','identity','mandate','conflict','purpose']
    read_state: Literal['unreadable','cached_positive'] | None = None


class AuthorityRefusal(Refusal):
    reason_vocabulary_version: Literal['runtime-authority-reasons/0.1']
    reopen_conditions: list[dict] = []
    resolution_inputs: list[AuthorityInput]


class AuthorityCheck(Check):
    inputs: list[AuthorityInput]


class JournalEvent(Extensible):
    check_id: str
    phase: Literal['opened','input','completed','interrupted']
    stage: Literal['decision','effect','claim']
    recorded_at: str
    owner: dict[str,str]
    proposal_commitment: str
    decision_id: str | None
    effect_id: str | None
    action_class: dict
    input: AuthorityInput | None
    reasons: list[str]
    reason_vocabulary_version: Literal['runtime-authority-reasons/0.1']


class P2Input(AuthorityInput):
    """Programme-2 (freshness/0.1): a resolution input also carries how the age of its read is known, and a read can be a
    nonce mismatch."""
    read_state: Literal['unreadable','cached_positive','nonce_mismatch'] | None = None
    age_basis: Literal['nonce_bound','source_asserted'] | None = None


class P2Refusal(AuthorityRefusal):
    """Programme-2: an effect-time refusal also names its journal check (operation identity), the evaluation time and the
    deadline it was refused past (freshness), and the rule identity it was decided under (rule revision)."""
    resolution_inputs: list[P2Input]
    reason_vocabulary_version: Literal['runtime-authority-reasons/0.1','runtime-authority-reasons/0.2']
    check_id: str | None = None
    evaluated_at: str | None = None
    deadline: str | None = None
    rule_identity: dict | None = None


class P2Check(AuthorityCheck):
    inputs: list[P2Input]
    recorded_at: str | None = None


class P2Event(JournalEvent):
    phase: Literal['opened','input','completed','interrupted','overdue','expired']
    input: P2Input | None
    reason_vocabulary_version: Literal['runtime-authority-reasons/0.1','runtime-authority-reasons/0.2']
    evaluated_at: str | None = None
    deadline: str | None = None
    age_bound_seconds: int | None = None
    extension_id: str | None = None
    nonce: str | None = None


AUTHORITY_EXTENDED = {'check_events':'resolution_check_event', 'vocabulary_changes':'reason_vocabulary_change'}


EXTENDED = {'refusals':'effect_time_refusal', 'resolution_checks':'resolution_check',
            'closeouts':'attempt_closeout', 'input_time_floors':'input_time_floors'}


def _structure_code(exc):
    """Contract refusal code for a pydantic failure: an undeclared member, a value outside a closed enumeration,
    or any other structural violation."""
    kinds = {e.get('type') for e in exc.errors()}
    if 'extra_forbidden' in kinds: return 'undeclared_member'
    if 'literal_error' in kinds or 'enum' in kinds: return 'unknown_enum_value'
    return 'schema_violation'


def _freeze(value):
    """Hashable form with the equality of ``==`` on JSON values (object member order ignored)."""
    if isinstance(value,dict):
        return frozenset((k,_freeze(v)) for k,v in value.items())
    if isinstance(value,(list,tuple)):
        return tuple(_freeze(v) for v in value)
    return value


#: Work budget of the journal-to-check matcher: candidate entries built, search steps taken and ordering comparisons made.
#: A run past it is refused (``input_too_large``) rather than left to run for an unbounded time. About 1,200 completed
#: journals with identical content fit; a real run holds a few dozen.
MAX_MATCH_WORK = 4_000_000


def validate_run(cp, proposal, *, runtime_authority=False, profiles=False):
    from .importers import ImportContractError, _aware_time
    def require(ok, reason, code=None):
        if not ok: raise ImportContractError('typed refusal profile: '+reason, code)
    def inputs(values):
        for x in values:
            require(bool(x.input_id), 'empty input identity')
            check_extensions({'extensions': x.extensions}, 'input')
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
    InputModel = (P2Input if profiles else AuthorityInput) if runtime_authority else Input
    RefusalModel = (P2Refusal if profiles else AuthorityRefusal) if runtime_authority else Refusal
    CheckModel = (P2Check if profiles else AuthorityCheck) if runtime_authority else Check
    EventModel = P2Event if profiles else JournalEvent
    unfinished=[]
    try:
        require(set(EXTENDED) <= cp.keys(), 'required evidence collection missing')
        require(isinstance(cp['input_time_floors'],dict), 'time floors must be an object')
        for key,stamp in cp['input_time_floors'].items():
            require(isinstance(key,str) and bool(key), 'empty time-floor identity'); _aware_time(stamp)
        decisions={d['decision_id']:d for d in cp['decisions']}
        for d in cp['decisions']:
            inputs([InputModel.model_validate(x) for x in d['resolution_inputs']])
            horizon(d['operation_horizon'], d.get('binding'))
        seen=set()
        for raw in cp['refusals']:
            x=RefusalModel.model_validate(raw);require(bool(x.refusal_id) and x.refusal_id not in seen,'duplicate/empty refusal id');seen.add(x.refusal_id)
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
            x=CheckModel.model_validate(raw);require(bool(x.check_id) and x.check_id not in seen,'duplicate/empty resolution check id','duplicate_check_id');seen.add(x.check_id)
            _aware_time(x.evaluated_at);inputs(x.inputs)
            check_extensions(raw,'resolution_checks');[check_extensions(i,'resolution_checks.inputs') for i in raw['inputs']]
        closeout_keys=set()
        for raw in cp['closeouts']:
            x=Closeout.model_validate(raw);_aware_time(x.observed_at);_aware_time(x.reconciled_at)
            require((x.attempt_id,x.observed_state) not in closeout_keys,'duplicate attempt closeout');closeout_keys.add((x.attempt_id,x.observed_state))
            require(any(a['attempt_id']==x.attempt_id and a['effect_id']==x.effect_id and a['status']==x.original_status for a in cp['attempts']),'closeout lacks original attempt lineage')
            require(any(r['effect_id']==x.effect_id and r.get('observation_accepted') and (r.get('observation') or {}).get('state')==x.observed_state and (r.get('observation') or {}).get('observed_at')==x.observed_at for r in cp['reconciliations']),'closeout lacks accepted observation lineage')
        # An attempt whose last recorded status is still uncertain (attempted/unknown/failed) must be closed out
        # for every accepted applied/partial observation of its effect (Control Plane close_uncertain_attempts).
        latest={}
        for a in cp['attempts']: latest[a['attempt_id']]=a
        for r in cp['reconciliations']:
            state=(r.get('observation') or {}).get('state')
            if r.get('observation_accepted') and state in ('applied','partial'):
                for aid,a in latest.items():
                    if a['effect_id']==r['effect_id'] and a['status'] in ('attempted','unknown','failed'):
                        require((aid,state) in closeout_keys,'uncertain attempt lacks closeout for accepted observation')
        if runtime_authority:
            # freshness/0.1: a decision held for check_lease_unavailable is written before the check is journalled, so a run whose
            # only decisions are such holds has no journal events (programme-2 generation only).
            lease_only=profiles and bool(cp['decisions']) and all(
                d.get('result')=='hold' and d.get('reasons')==['check_lease_unavailable'] and d.get('binding') is None for d in cp['decisions'])
            require((isinstance(cp.get('check_events'),list) and bool(cp['check_events'])) or lease_only, 'resolution journal missing')
            checks={};completions=[];open_at={};close_at={};terminal=set()
            resolution_index=None;resolution_reasons=[]
            work=[0]
            def charge(units):
                work[0]+=units
                require(work[0]<=MAX_MATCH_WORK,'journal matching exceeds the work limit','input_too_large')
            def normalize(values):
                return [{k:v for k,v in x.items() if k not in ('previous_observed_at','extensions')} for x in values]
            for seq,raw in enumerate(cp.get('check_events',[])):
                event=EventModel.model_validate(raw);_aware_time(event.recorded_at)
                check_extensions(raw,'check_events');check_extensions(raw.get('input'),'check_events.input')
                require(re.fullmatch(r'sha256:[a-f0-9]{64}',event.proposal_commitment),'invalid journal proposal commitment','schema_violation')
                if event.phase=='opened':
                    require(event.check_id not in checks,'duplicate journal opening','journal_protocol')
                    checks[event.check_id]=[event,False,[]];open_at[event.check_id]=seq
                elif profiles and event.phase in ('overdue','expired'):
                    # freshness/0.1: 'overdue' reports a live check and closes nothing; 'expired' is the terminal dispatch-gate
                    # event, allowed after 'completed' but never after 'interrupted' or 'expired'.
                    require(event.check_id in checks,'journal missing opening','journal_protocol')
                    opening=checks[event.check_id][0]
                    require(all(getattr(event,k)==getattr(opening,k) for k in ['owner','stage','proposal_commitment','decision_id','effect_id','action_class']),'journal binding changed','journal_protocol')
                    if event.phase=='overdue':
                        require(not checks[event.check_id][1],'journal check already closed','journal_protocol')
                    else:
                        require(event.check_id not in terminal,'journal check already terminal','journal_protocol')
                        terminal.add(event.check_id);checks[event.check_id][1]=True;close_at.setdefault(event.check_id,seq)
                else:
                    require(event.check_id in checks and not checks[event.check_id][1],'journal missing opening or already closed','journal_protocol')
                    opening=checks[event.check_id][0]
                    require(all(getattr(event,k)==getattr(opening,k) for k in ['owner','stage','proposal_commitment','decision_id','effect_id','action_class']),'journal binding changed','journal_protocol')
                    if event.phase=='input':
                        require(event.input is not None,'journal input missing','journal_protocol');inputs([event.input])
                        checks[event.check_id][2].append(raw['input'])
                    else:
                        checks[event.check_id][1]=True
                        if event.phase=='interrupted':
                            unfinished.append(event.check_id);terminal.add(event.check_id)
                        if event.phase=='completed':
                            # Journal and resolution-check IDs are separate producer UUIDs; bind by content.
                            if resolution_index is None:
                                # Built once (not once per completed journal): resolution checks keyed by stage and normalized inputs.
                                resolution_index={};resolution_reasons=[]
                                for i,x in enumerate(cp['resolution_checks']):
                                    resolution_index.setdefault((x['stage'],_freeze(normalize(x['inputs']))),[]).append(i)
                                    resolution_reasons.append(set(x['reasons']))
                            wanted=set(event.reasons)
                            bucket=resolution_index.get((event.stage,_freeze(normalize(checks[event.check_id][2]))),[])
                            charge(len(bucket)+1)
                            candidates=[i for i in bucket if wanted<=resolution_reasons[i]]
                            require(bool(candidates),'completed journal differs from actual resolution check','journal_unbound_completion')
                            completions.append((event.check_id,candidates));close_at[event.check_id]=seq
                if event.decision_id is not None:
                    require(event.decision_id in decisions and decisions[event.decision_id]['effect_id']==event.effect_id,'journal decision/effect lineage mismatch')
            # Each actual resolution check may substantiate at most one completed journal.
            owner={}
            def assign(start):
                # Iterative augmenting-path search (no recursion, so the number of completed journals cannot exhaust the stack).
                for i in completions[start][1]:
                    charge(1)
                    if i not in owner:  # a free check needs no search
                        owner[i]=start
                        return True
                seen=set()
                stack=[(start,iter(completions[start][1]))]
                chosen=[]  # chosen[k] is the actual check frame k moved to while looking for a free one
                while stack:
                    j,candidates=stack[-1]
                    descended=False
                    for i in candidates:
                        charge(1)
                        if i in seen:
                            continue
                        seen.add(i)
                        chosen.append(i)
                        if i not in owner:
                            for (frame_j,_),frame_i in zip(stack,chosen):
                                owner[frame_i]=frame_j
                            return True
                        stack.append((owner[i],iter(completions[owner[i]][1])))
                        descended=True
                        break
                    if not descended:
                        stack.pop()
                        if chosen:
                            chosen.pop()
                return False
            for j in range(len(completions)):
                require(assign(j),'completed journals reuse one actual resolution check','journal_check_reused')
            # Resolution checks are appended as they complete. Checks that did not overlap in the journal (one
            # completed before the other opened) must match actual checks in that order; overlapping (concurrent)
            # checks may complete in either order.
            chosen={}
            for cid,candidates in completions:
                charge(len(chosen)+len(candidates)+1)
                previous=max([chosen[o] for o in chosen if close_at[o]<open_at[cid]],default=-1)
                later=[i for i in candidates if i>previous]
                require(bool(later),'resolution checks are out of journal order','resolution_checks_out_of_order')
                chosen[cid]=min(later)
            # Opened-only and interrupted checks are retained as evidence of incompletion.
            unfinished.extend(k for k,v in checks.items() if not v[1])
            for d in cp['decisions']:
                accepted_labels=('runtime-authority-reasons/0.1','runtime-authority-reasons/0.2') if profiles else ('runtime-authority-reasons/0.1',)
                require(d.get('reason_vocabulary_version') in accepted_labels,'decision vocabulary missing')
                binding=d.get('binding') or {}
                if binding:
                    authority=binding.get('runtime_authority')
                    require(isinstance(authority,dict) and authority.get('profile')=='runtime-authority/0.1','runtime authority binding missing')
                    base_fields={'profile','approval_commitment','required_inputs_digest','catalogue_digest',
                        'expected_effective_grant_digest','effective_grant_derivation_version'}
                    # operation-identity/0.1: issuer-supplied identity, always as a pair.
                    fields=base_fields|({'operation_id','operation_issuer'}&set(authority) if profiles else set())
                    require(set(authority)==fields,'runtime authority fields unsupported','undeclared_member')
                    for field in ['approval_commitment','required_inputs_digest','catalogue_digest']:
                        require(isinstance(authority.get(field),str) and re.fullmatch(r'sha256:[a-f0-9]{64}',authority[field]),'runtime authority commitment invalid')
            require(isinstance(cp.get('vocabulary_changes',[]),list),'vocabulary changes malformed')
            for change in cp.get('vocabulary_changes',[]):
                require(set(change)=={'change_id','previous_version','version','registry_digest','kind','previous_codes','codes','acknowledged_by','acknowledged_at'},'vocabulary change fields unsupported')
                require(change['previous_version']!=change['version'] and bool(change['acknowledged_by']),'invalid vocabulary transition')
                _aware_time(change['acknowledged_at'])
    except ValidationError as exc:
        raise ImportContractError('typed refusal profile: unsupported/missing evidence fields', _structure_code(exc)) from exc
    except (KeyError,TypeError,AttributeError) as exc:
        raise ImportContractError('typed refusal profile: unsupported/missing evidence fields') from exc
    # Journal check IDs that never completed (opened-only or interrupted), in journal order.
    return unfinished


def extend_retained_inputs(cp, bundle):
    """Rebuild all four fields for downstream semantic revalidation, not an allowlist bypass."""
    from .importers import ImportContractError
    result=deepcopy(cp)
    authority = any(r.get('record_type') == 'resolution_check_event' for r in bundle['records'])
    extensions = {**EXTENDED, **AUTHORITY_EXTENDED} if authority else EXTENDED
    for field,kind in extensions.items():
        rows=[deepcopy(r['data']) for r in bundle['records'] if r.get('record_type')==kind]
        if field=='input_time_floors':
            if len(rows)!=1:raise ImportContractError('typed refusal profile requires one time-floor record')
            result[field]=rows[0]
        else: result[field]=rows
    # Programme-2 profile lists (opt-in; present only in a bundle that retained them, so every earlier bundle rebuilds as before).
    from .programme2_profiles import PROFILE_LISTS
    for field,kind in PROFILE_LISTS.items():
        rows=[deepcopy(r['data']) for r in sorted(bundle['records'],key=lambda r:r.get('source_sequence',0)) if r.get('record_type')==kind]
        if rows: result[field]=rows
    return result
