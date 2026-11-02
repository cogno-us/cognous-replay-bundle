"""Legacy-output golden for RW-01-F4-PoC (N23 / N24 / E-3 named-key guard): the import of EVERY existing fixture under every supported revision and every pre-existing
mode (plain, old Registry-governed selector, caller-trusted digest match) is recorded as a SHA-256 of its canonical JSON dump (minus the volatile ``bundle_id`` and
``generated_at``) or, for a refusal, of its (exception type, code, message). ``legacy_outputs.json`` was generated ONCE from the unmodified base commit
6f45e288ae37ec7e7712f9296760927d2d843bba (before any production change) with ``PYTHONPATH=<pristine src> python -m tests.golden_legacy_outputs``; the test recomputes it on the
changed tree and requires byte equality, so the new profile, the new keyword and the named-key guard demonstrably change nothing when ``selection_evidence`` is absent.
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
FIXTURES = HERE / "fixtures"
GOLDEN = FIXTURES / "rw01_f4_poc_golden" / "legacy_outputs.json"
SELECTOR = "registry-governed-effective-configuration/0.1"
PINNED = "sha256:74e7cda7975979258803766c340a55d5fbdb1ea85abfc6a8ae8be0549dad95b7"
EXPORT_NAMES = ("executor.json", "runtime_export.json")


def _digest(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode()).hexdigest()


def compute() -> dict:
    from agent_replay_bundle import importers as I
    revisions = sorted({I.CONTROL_PLANE_REVISION, *I.CONTROL_PLANE_SUPPORTED_V2_REVISIONS})
    out = {}
    for run in sorted(FIXTURES.rglob("control_plane_run.json")):
        if "rw01_f4_poc" in str(run):
            continue
        name = str(run.parent.relative_to(FIXTURES))
        cp = json.loads(run.read_text())
        proposal = json.loads((run.parent / "proposal.json").read_text()) if (run.parent / "proposal.json").exists() else None
        exports = {"none": None}
        for export_name in EXPORT_NAMES:
            if (run.parent / export_name).exists():
                exports[export_name] = json.loads((run.parent / export_name).read_text())
        modes = [("plain", {}), ("governed", {"control_plane_profile": SELECTOR}), ("trusted", {"control_plane_profile": SELECTOR, "expected_effective_configuration_digest": PINNED})]
        for revision in revisions:
            for export_name, export in exports.items():
                for mode, kw in modes:
                    key = "|".join((name, revision[:8], export_name, mode))
                    try:
                        bundle = I.import_bounded_workflow(copy.deepcopy(cp), proposal=copy.deepcopy(proposal), moltbot_export=copy.deepcopy(export),
                                                           control_plane_revision=revision, **kw)
                        dumped = bundle.model_dump(mode="json")
                        dumped.pop("bundle_id", None)
                        dumped.pop("generated_at", None)
                        out[key] = "ok:" + _digest(dumped)
                    except Exception as exc:  # noqa: BLE001 - the golden records refusals too
                        out[key] = "refused:" + type(exc).__name__ + ":" + str(getattr(exc, "code", None)) + ":" + _digest(str(exc))
    return out


if __name__ == "__main__":
    import agent_replay_bundle
    print("generating with", agent_replay_bundle.__file__, file=sys.stderr)
    GOLDEN.write_text(json.dumps(compute(), indent=0, sort_keys=True) + "\n")
