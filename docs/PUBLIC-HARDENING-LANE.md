# Public hardening lane during canonical migration

This branch/lane is intentionally independent from the canonical migration coordinated in `EU-transp-weekly`.

## Non-interference contract

While the private orchestrator is stabilising migration, work in this lane must not:

- create or redefine Fxx identities;
- change canonical rights, acceptance or preservation decisions;
- change `source_specs/` or `requests/` to trigger new producer acquisition;
- rewrite `preserved_state/index.json` from assumptions;
- promote private bytes to public storage;
- alter private canonical manifests or migration queues.

Safe work includes:

- unit and contract tests for acquisition-engine behaviour;
- receipt immutability and public-redaction tests;
- preserved-first routing tests;
- primary-repair authorization tests;
- schema/static validation;
- public-plane quality and coverage reporting;
- documentation and CI hardening;
- deterministic checks that require no producer or private-control-plane calls.

## Merge rule

Changes from this lane should remain unmerged until the orchestrator declares the migration stable, unless they fix an urgent execution/security defect and are explicitly coordinated.

The quality report distinguishes execution evidence from canonical state:

- a source spec means that an execution route exists;
- a receipt means that acquisition evidence exists;
- neither means canonical acceptance, reuse clearance, preservation completeness or consumer readiness.

This separation allows hardening of the public acquisition engine without competing with migration or changing its conclusions.
