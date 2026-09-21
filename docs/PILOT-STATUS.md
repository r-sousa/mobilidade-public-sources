# Pilot status — 21/09/2026

## Proven

### F01 — Eurostat `road_go_na_rl3g`

- public hosted runner assigned and executed successfully;
- official Eurostat API response materialized;
- producer-native JSON preserved;
- local SHA-256/byte verification passed;
- public reuse gate inherited as verified and asset-level official-output check passed;
- public Release created with deterministic source-object fingerprint;
- Release asset downloaded back and digest-verified;
- rerun with unchanged source bytes completed successfully;
- exactly one F01 source Release exists after the rerun.

Current source-object fingerprint:

`b9f96c0e6d28731b8c4618c1ad5206399ca0b4e4c8e756147fcf7783273f04a4`

Native data asset:

- `road_go_na_rl3g.json`
- 2,308,085 bytes
- SHA-256 `72127340332e7483ea5862ae97c9d9ef833eb55e14243c24b64813b0cbf21529`

This proves the public-runner and `public_release` architecture, including source-object idempotency.

## Reached producer route but currently blocked upstream

### F12 — STCP GTFS / Porto Digital

A public GitHub runner started normally. Acquisition then failed at DNS resolution for the canonical producer host `opendata.porto.digital`.

Disposition:

- classify as producer-route/DNS failure, not GitHub Actions infrastructure failure;
- do not infer loss of source identity, rights or GTFS semantics;
- do not silently replace the official producer route with a secondary mirror;
- retain F12 for retry after the official producer route is operational.

## Staged, not yet executed against the private sink

Draft PR #1 stages:

- F148 — Eurostat `tran_r_rago`;
- F85 — INE indicator route `0013516`, preserving canonical F85 identity;
- F49 — ANSR annual XLSX annexes;
- F30 — IGE table 4580;
- F181 — Junta de Castilla y León OpenDataSoft dataset.

They remain unmerged until the public repository contains the repository Actions secret `MN_PRIVATE_SINK_TOKEN`. No secret value belongs in source, logs, receipts or chat.

## Remaining pilot gates

- verify cross-repository private Release creation/upload;
- verify immutable private receipt creation;
- rerun identical private-source bytes and confirm no duplicate canonical source object;
- verify private orchestrator discovery/reconciliation of the receipt;
- repair any producer-specific adapter issues exposed by those live runs;
- only then assess legacy private workflow retirement readiness.
