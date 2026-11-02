# rw01_f4_governed_real: REAL Control Plane F4 `GovernedAgeWorkflow` records (UNEDITED)

Produced by the real Control Plane PR #102 head `6648ae2cf70b8a873aeac36306b72b1b2763775c` (`GovernedAgeWorkflow(carry_selection_evidence=True)`) with the real Registry
PR #86 head `52ff5f7dd8145793a77add1574d54a9aa3351283` (real `Ed25519Verifier`; SYNTHETIC test keys, mechanism-only). `run.json` files are the bytes written by the
Control Plane's own `BoundedRecordStore` (equal to `BoundedRecordStore(...).load().model_dump(mode="json")`, asserted by the generator for the main record).
`proposal.json` is `RuntimeProposal.model_dump_json()` (re-indented, sorted keys). Nothing was edited, grafted, re-sealed or completed.

| Directory | Content |
|---|---|
| `.` | authorized + executed run with the carried Registry-signed `selection_evidence` |
| `effect_refusal/` | same, but effect-time resolution was made stale so `execute` refused (real `refusals[0]` row) |
| `hold_only/` | hold decision (aged status), no binding, no `selection_evidence` |

Generator: `generate.py` (this directory), run as
`RW01_SRC_DIR=<dir with control_plane/ registry/ replay/ links> PYTHONPATH=<PyNaCl 1.6.2> python generate.py <outdir>`
using the battery harness `rw01_f4_poc/battery/harness.py` of Qualification #263 `50de8cf0`. PyNaCl is NOT a Replay dependency; fixture generation is not part of the tests.
Generated 2026-11-02 under Python 3.13.

sha256:

```
6d6d0a8bedfd002cc303de8fe087a786cbd391c5ee1978d6b8d1317c115fea08  run.json
d43ac343139f8c9393ddca4746961d1fc7a4e05bafa5a6c5f446157a53e5178d  proposal.json
1682ea1ca941b7589147e6bcdd423d5c1ebeda26c135dbb3bdf262ae56bfb2a2  effect_refusal/run.json
d43ac343139f8c9393ddca4746961d1fc7a4e05bafa5a6c5f446157a53e5178d  effect_refusal/proposal.json
b3445c08258468717154c483b453bec69341e7ffddd5f62cdc01ffed27e274da  hold_only/run.json
d43ac343139f8c9393ddca4746961d1fc7a4e05bafa5a6c5f446157a53e5178d  hold_only/proposal.json
```

Operator-side values used by the tests (independent of the records): consumer `consumer-test`, tenant `tenant-alpha`, operation `refund-issue-routine`, host ages 60/60.
The tests use a stub verifier (Replay-unit scope); a stub proves nothing about authentication.
