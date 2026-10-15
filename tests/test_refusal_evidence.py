"""Actual current CP/executor records; explicit integration dependencies required."""
from copy import deepcopy
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import sys

import pytest
from agent_replay_bundle.importers import (import_bounded_workflow, ImportContractError,
    CONTROL_PLANE_REFUSAL_REVISION, MOLTBOT_REFUSAL_REVISION)
from agent_replay_bundle.refusal_evidence import EXTENDED, extend_retained_inputs


@pytest.fixture
def actual(tmp_path, monkeypatch):
    cp=os.environ.get('ARB_REFUSAL_CP_ROOT');executor=os.environ.get('ARB_REFUSAL_EXECUTOR_ROOT')
    fixture=os.environ.get('ARB_PINNED_MANIFEST_FIXTURE')
    if not all((cp,executor,fixture)):pytest.skip('Configure exact CP/executor refusal-profile integration inputs')
    monkeypatch.syspath_prepend(str(Path(cp)/'src'));monkeypatch.syspath_prepend(executor)
    monkeypatch.setenv('MOLTBOT_SAFE_CONTROL_PLANE_ROOT',cp);monkeypatch.setenv('MOLTBOT_SAFE_MANIFEST_FIXTURE',fixture)
    import agent_control_plane.bounded as bounded
    monkeypatch.setattr(bounded,'_now',lambda:datetime(2026,10,5,19,tzinfo=timezone.utc))
    spec=importlib.util.spec_from_file_location('refusal_runtime_helpers',Path(executor)/'tests/test_safe_executor.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    h,p,r,w,d,dest,ex,env=mod._integrated(tmp_path)
    return h,p,r,w,d,dest,ex,env


def bundle(actual, change='grant'):
    from engine.producer_contract import export_execution_artifacts
    h,p,r,w,d,dest,ex,env=actual
    if change=='grant':next(iter(r.statuses.values())).status='revoked'
    elif change=='approval':next(iter(r.approvals.values())).status='revoked'
    elif change=='policy':next(iter(r.policies.values())).version='changed'
    elif change=='evidence':next(iter(r.evidence.values())).state='stale'
    if change=='lost-ack':
        assert ex.execute(envelope=env,proposal=p,decision=d,now=h.NOW,simulate='lost_ack').status=='unknown'
    result=ex.execute(envelope=env,proposal=p,decision=d,now=h.NOW)
    cp=w.records.load().model_dump(mode='json',exclude_none=False)
    exported=export_execution_artifacts(env,result,dest,repository_revision=MOLTBOT_REFUSAL_REVISION)
    proposal=p.model_dump(mode='json',exclude_none=False)
    replay=import_bounded_workflow(cp,proposal=proposal,moltbot_export=exported,control_plane_revision=CONTROL_PLANE_REFUSAL_REVISION)
    return cp,proposal,exported,replay.model_dump(mode='json'),w.manifest


@pytest.mark.parametrize('change',['grant','approval','policy','evidence','lost-ack','success'])
def test_all_typed_source_fields_survive_reconstruction(actual,change):
    cp,p,exported,replay,_=bundle(actual,change)
    restored=extend_retained_inputs({k:deepcopy(v) for k,v in cp.items() if k not in EXTENDED},replay)
    assert restored==cp
    assert replay['status']=='reconstruction_complete'
    assert not any(f['code']=='B001' for r in replay['import_reports'] for f in r['findings'])
    again=import_bounded_workflow(restored,proposal=p,moltbot_export=exported,control_plane_revision=CONTROL_PLANE_REFUSAL_REVISION).model_dump(mode='json')
    for key in ['records','links','commitments','producer_profiles','status']:assert again[key]==replay[key]
    if cp['refusals']:
        assert exported['control_plane_evidence']['refusal']==cp['refusals'][0]
    if change=='lost-ack':assert cp['closeouts']


@pytest.mark.parametrize('mutation',['missing','unknown','decision','effect','input','floors','executor-drop','executor-substitute','closeout'])
def test_evidence_substitution_or_loss_is_rejected(actual,mutation):
    cp,p,exported,replay,_=bundle(actual)
    if mutation=='missing':del cp['refusals'][0]['resolution_inputs']
    elif mutation=='unknown':cp['refusals'][0]['future_permission']=True
    elif mutation=='decision':cp['refusals'][0]['decision_id']='other'
    elif mutation=='effect':cp['refusals'][0]['effect_id']='other'
    elif mutation=='input':cp['refusals'][0]['changed_inputs'][0]['input_id']='other'
    elif mutation=='floors':cp['input_time_floors']['grant:other']='not-a-time'
    elif mutation=='executor-drop':
        exported['control_plane_evidence'].pop('refusal');exported['execution_result']['control_plane_evidence']=deepcopy(exported['control_plane_evidence'])
    elif mutation=='executor-substitute':
        exported['control_plane_evidence']['refusal']['reasons']=['made-up'];exported['execution_result']['control_plane_evidence']=deepcopy(exported['control_plane_evidence'])
    else:cp['closeouts']=[dict(attempt_id='other',effect_id=cp['decisions'][0]['effect_id'],original_status='unknown',observed_state='applied',observed_at=cp['decisions'][0]['decided_at'],reconciled_at=cp['decisions'][0]['decided_at'])]
    with pytest.raises(ImportContractError):
        import_bounded_workflow(cp,proposal=p,moltbot_export=exported,control_plane_revision=CONTROL_PLANE_REFUSAL_REVISION)


def test_unknown_top_level_data_remains_explicit_loss(actual):
    cp,p,exported,_,_=bundle(actual);cp['future_audit']={}
    r=import_bounded_workflow(cp,proposal=p,moltbot_export=exported,control_plane_revision=CONTROL_PLANE_REFUSAL_REVISION)
    assert r.status=='reconstruction_partial'
    assert any(f.code=='B001' and f.path=='future_audit' for report in r.import_reports for f in report.findings)
