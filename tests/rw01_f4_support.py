"""Test support for the authenticated-selection profile (RW-01-F4-PoC). LOGIC-ONLY: NO CRYPTOGRAPHY ANYWHERE IN THIS FILE.

``LogicOnlyStubVerifier`` is a STUB. It implements ``verify_selection_evidence(request)`` with plain string comparisons so that REPLAY-SIDE logic (selector matrix, trust
validation, admission order, closed verdict gate, echo checks, binding, markers, retained-bundle re-verification) can be driven through the real enforcement boundary
``import_bounded_workflow``. It checks no signature, holds no key and proves NOTHING about authentication: Replay cannot tell it from a genuine Registry adapter (known
non-detection NF-2, pinned by a test). Real Ed25519 evidence belongs to the Registry/Control Plane PRs of this sprint, not to Replay.
"""
from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from agent_replay_bundle import effective_configuration as EC
from agent_replay_bundle import importers as I
from agent_replay_bundle.registry_evidence import (REGISTRY_AUTHENTICATED_SELECTION_PROFILE, RegistryEvidenceTrust, RegistryExpectedContext, RegistryTrustSnapshotRef)

FIX = Path(__file__).parent / "fixtures" / "registry_governed_effective_configuration"
CUR_CP = I.CONTROL_PLANE_CUR_REVISION
SELECTOR = REGISTRY_AUTHENTICATED_SELECTION_PROFILE
OLD_SELECTOR = EC.REGISTRY_GOVERNED_PROFILE
AGES = ("status_max_age_seconds", "approval_max_age_seconds")
F4_FAMILY = "f4-control-plane-age-bounds"
LAYERS = ("structural", "integrity", "record_binding", "trust_snapshot", "authenticity", "authority", "scope", "time", "revocation", "epoch", "disposition")
T0 = datetime(2026, 11, 2, 12, 0, 0, tzinfo=timezone.utc)
CTX = dict(consumer_id="consumer-test", tenant="tenant-alpha", institution="urn:cognous:institution:synthetic-customer-service", authority_domain="customer-refunds",
           operation="refund-issue-op")
ACTION = "urn:cognous:action:refund-issue-routine-v1"
OPERATION = "refund-issue-op"
HOST = {"status_max_age_seconds": 60, "approval_max_age_seconds": 60}
CP_REV = "b" * 40
REG_REV = "c" * 40
SNAPSHOT_SECRET = "SNAPSHOT-SECRET-DO-NOT-ECHO"
VERIFIER_SECRET = "VERIFIER-FREE-TEXT-DO-NOT-ECHO"

SELECTION = '{"stub":"signed-selection","n":1}'
RECORD = '{"stub":"record","n":1}'
ALT_SELECTION = '{"stub":"signed-selection","n":2}'
ALT_RECORD = '{"stub":"record","n":2}'
SELECTION_NONASCII = '{"stub":"signed-selection","tenant":"ténant-a"}'
RECORD_NONASCII = '{"stub":"record","tenant":"ténant-a"}'
# what the STUB considers "genuinely signed": selection text -> (record text, signed bound, issuer, selection id, epoch)
GENUINE = {
    SELECTION: (RECORD, {"status_max_age_seconds": 120, "approval_max_age_seconds": 120}, "issuer-test-1", "sel-f4-001", 3),
    ALT_SELECTION: (ALT_RECORD, {"status_max_age_seconds": 90, "approval_max_age_seconds": 90}, "issuer-test-2", "sel-f4-002", 4),
    SELECTION_NONASCII: (RECORD_NONASCII, {"status_max_age_seconds": 120, "approval_max_age_seconds": 120}, "issuer-test-1", "sel-f4-003", 5),
}

WIRE_REQUEST_KEYS = {"contract", "family", "registry_contract", "selection_text", "record_text", "expected_context", "expected_operation_id", "trust_snapshot",
                     "verification_time", "verification_time_utc", "min_trust_snapshot_version", "last_accepted_snapshot", "host_policy"}
WIRE_VERDICT_KEYS = {"contract", "ok", "code", "authenticated", "layers", "family", "registry_contract", "selection_text_sha256", "record_text_sha256",
                     "verification_time_utc", "trust_snapshot_id", "trust_snapshot_version", "trust_snapshot_fingerprint", "floors_applied", "epoch_floor_applied",
                     "issuer_id", "selection_id", "epoch", "selection_digest", "bound_record_digest", "effective_policy_digest", "effective_values", "verifier_implementation"}


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def effective_for(host: dict, bound: dict) -> dict:
    return {k: min(host[k], bound[k]) for k in AGES}


def policy_digest(effective: dict) -> str:
    """The STUB's stand-in for the Registry effective-policy digest (a plain hash of the composed values; not the Registry function)."""
    return "sha256:" + hashlib.sha256(("stub-policy|" + json.dumps(effective, sort_keys=True)).encode()).hexdigest()


class OpaqueSnapshot:
    """Stands in for the Registry TrustSnapshot: opaque to Replay. Carries a secret that must never reach a bundle or an exception message."""
    snapshot_id = "snap-1"
    version = 7
    fingerprint = "fp-7"

    def __repr__(self) -> str:
        return "OpaqueSnapshot(" + SNAPSHOT_SECRET + ")"


UNSET = object()


class LogicOnlyStubVerifier:
    """STUB (logic only, NO crypto, proves nothing about authentication). ``mutate(verdict, request)`` may alter the verdict; ``replace`` returns an arbitrary object;
    ``raises`` raises it; ``refuse`` returns a refusal verdict with that code."""

    def __init__(self, *, mutate=None, replace=UNSET, raises=None, refuse=None, genuine=None):
        self.calls: list[dict] = []
        self.mutate, self.replace, self.raises, self.refuse = mutate, replace, raises, refuse
        self.genuine = GENUINE if genuine is None else genuine

    def verify_selection_evidence(self, request):
        self.calls.append(request)
        if self.raises is not None:
            raise self.raises
        if self.replace is not UNSET:
            return self.replace
        if self.refuse is not None:
            return {"contract": "registry-evidence-verdict/0.1", "ok": False, "code": self.refuse, "authenticated": False, "layers": {n: "not_evaluated" for n in LAYERS}}
        sel, rec = request["selection_text"], request["record_text"]
        if sel not in self.genuine:
            return self._no("signature_invalid")
        record_text, bound, issuer, selection_id, epoch = self.genuine[sel]
        if rec != record_text:
            return self._no("record_digest_mismatch")
        ctx = request["expected_context"]
        if ctx["operation"] != request["expected_operation_id"]:
            return self._no("selection_operation_mismatch")
        snapshot = request["trust_snapshot"]
        eff = effective_for(request["host_policy"], bound)
        verdict = {
            "contract": "registry-evidence-verdict/0.1", "ok": True, "code": None, "authenticated": True, "layers": {n: "pass" for n in LAYERS},
            "family": request["family"], "registry_contract": request["registry_contract"], "selection_text_sha256": sha(sel), "record_text_sha256": sha(rec),
            "verification_time_utc": request["verification_time_utc"], "trust_snapshot_id": snapshot.snapshot_id, "trust_snapshot_version": snapshot.version,
            "trust_snapshot_fingerprint": snapshot.fingerprint,
            "floors_applied": {"min_trust_snapshot_version": request["min_trust_snapshot_version"] >= 1, "last_accepted_snapshot": request["last_accepted_snapshot"] is not None},
            "epoch_floor_applied": False, "issuer_id": issuer, "selection_id": selection_id, "epoch": epoch, "selection_digest": "sha256:" + sha("statement|" + sel),
            "bound_record_digest": "sha256:" + sha("record|" + rec), "effective_policy_digest": policy_digest(eff), "effective_values": dict(eff),
            "verifier_implementation": {"name": "logic-only-stub", "registry_revision": "none"},
        }
        if self.mutate is not None:
            result = self.mutate(verdict, request)
            return verdict if result is None else result
        return verdict

    @staticmethod
    def _no(code):
        return {"contract": "registry-evidence-verdict/0.1", "ok": False, "code": code, "authenticated": False, "layers": {n: "not_evaluated" for n in LAYERS}}


def load(name="governed_executed"):
    return tuple(json.loads((FIX / name / f).read_text()) for f in ("control_plane_run.json", "proposal.json"))


def reseal_members(cp, mutate):
    cp = copy.deepcopy(cp)
    ec = cp["decisions"][0]["binding"]["runtime_authority"]["effective_configuration"]
    mutate(ec["members"])
    ec["digest"] = EC.digest_of(ec["version"], ec["members"])
    return cp


def evidence(selection=SELECTION, record=RECORD, operation=OPERATION, **over):
    """The single C2 carried-evidence object, built locally (the Control Plane worker's golden fixture is cross-checked separately when it exists)."""
    ev = {"version": "selection-evidence/0.1", "contract_version": "r08-v2", "family": F4_FAMILY, "operation_id": operation, "verified_at": "2026-11-02T11:59:00Z",
          "record_text": record, "selection_text": selection}
    ev.update(over)
    return ev


def f4_run(selection=SELECTION, record=RECORD, *, host=None, bound=None, with_evidence=True):
    """A Registry-governed run whose f4_ages family row is the STUB's composed digest (so a stub-admitted verdict matches), plus the carried evidence."""
    cp, proposal = load("governed_executed")
    host = HOST if host is None else host
    bound = GENUINE[selection][1] if bound is None else bound
    eff = effective_for(host, bound)

    def mutate(m):
        m["f4_scalars"] = dict(eff)
        row = {"slot": "f4_ages", "family_id": F4_FAMILY, "contract_version": "r08-v2", "family_schema_revision": None, "effective_policy_digest": policy_digest(eff)}
        m["families"] = [row] + [r for r in m["families"] if r["slot"] != "f4_ages"]
    cp = reseal_members(cp, mutate)
    if with_evidence:
        cp["decisions"][0]["selection_evidence"] = evidence(selection, record)
    return cp, proposal


def make_trust(**over):
    kw = dict(verifier=LogicOnlyStubVerifier(), trust_snapshot=OpaqueSnapshot(), trust_snapshot_ref=RegistryTrustSnapshotRef(snapshot_id="snap-1", version=7),
              expected_context=RegistryExpectedContext(**CTX), expected_action_id=ACTION, expected_operation_id=OPERATION, verification_time=T0, time_mode="as_of",
              min_trust_snapshot_version=5, last_accepted_snapshot=(7, "fp-7"), expected_host_ages=dict(HOST), control_plane_source_revision=CP_REV,
              registry_source_revision=REG_REV)
    kw.update(over)
    return RegistryEvidenceTrust(**kw)


def raw_trust(**over):
    """A trust object built WITHOUT ``__post_init__`` validation (as a hostile or careless caller could), to prove Replay re-validates at import."""
    trust = make_trust()
    for name, value in over.items():
        object.__setattr__(trust, name, value)
    return trust


def do_import(cp, proposal, *, trust=None, selector=SELECTOR, revision=CUR_CP, export=None, **kw):
    if trust is not None or "registry_evidence_trust" in kw:
        kw.setdefault("registry_evidence_trust", trust)
    return I.import_bounded_workflow(copy.deepcopy(cp), proposal=copy.deepcopy(proposal), moltbot_export=export, control_plane_revision=revision, control_plane_profile=selector, **kw)
