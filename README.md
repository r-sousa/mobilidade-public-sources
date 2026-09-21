# Mobilidade Norte — Public Source Acquisition

Public execution/acquisition plane for genuinely public source families used by the Mobilidade Norte data platform.

The private repository `r-sousa/EU-transp-weekly` remains the canonical governance layer for source identity, acceptance, rights/reuse state, private preservation and controlled-access sources. This repository never allocates or redefines `Fxx` identities.

## Architecture

`producer → public GitHub Action → native-byte validation + SHA-256 → disposition`

Disposition is fail-closed:

- **public_release** — allowed only when the private canonical state already records reuse as verified **and** the declared asset-level check passes;
- **private** — public runner may acquire the public producer bytes, but the bytes are delivered only to the private canonical repository;
- **controlled/authenticated** — does not execute here. DataComex authenticated access, Aena detailed/custom authenticated access, MFA/account/payment/terms-controlled sources and all credential-bearing sessions remain private.

The source-object identity is `source_set_id + native_asset_fingerprint`, where the fingerprint is SHA-256 over the ordered producer-native asset records `(name, sha256, byte_count)`. Rerunning unchanged source bytes reuses the same durable object and receipt.

## Repository layout

- `source_specs/` — declarative source specifications; identity is inherited from the private catalogue;
- `schema/source-spec.schema.json` — fail-closed source-spec contract;
- `src/mn_public_acquisition/adapters.py` — reusable acquisition adapters;
- `src/mn_public_acquisition/sinks.py` — public Release and private canonical sink logic;
- `.github/workflows/acquire.yml` — generic source acquisition workflow;
- `docs/PRIVATE-SINK.md` — minimum cross-repository credential contract;
- `docs/MIGRATION-INVENTORY.md` — preparatory inventory for legacy private workflows;
- `docs/PILOT-STATUS.md` — current validation evidence.

## Governance boundary

A successful acquisition receipt is **changed-route evidence**, not canonical acceptance. Only the Mobilidade Norte private orchestrator may accept evidence, change rights/reuse state, update canonical manifests/catalogues, promote consumer assets or authorize downstream publication/Site ingestion.

**acquisition != validation != acceptance != reuse clearance != preservation != publication != Site ingestion**

Public availability is not equivalent to redistribution permission. Missing/confidential values are preserved as supplied by the producer and are never manufactured as zeros.
