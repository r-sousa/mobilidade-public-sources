# Mobilidade Norte — Public Source Acquisition

Public execution/acquisition plane for genuinely public source families used by the Mobilidade Norte data platform.

The private repository `r-sousa/EU-transp-weekly` remains the canonical governance layer for source identity, acceptance, rights/reuse state, private preservation and controlled-access sources. This repository never allocates or redefines `Fxx` identities.

## Architecture

`producer → public GitHub Action → native-byte validation + SHA-256 → disposition`

Disposition is fail-closed:

- **public_release** — allowed only when the private canonical state already records reuse as verified **and** the declared asset-level check passes;
- **private** — the public runner acquires and validates the public producer bytes. If the optional narrowly scoped `MN_PRIVATE_SINK_TOKEN` is configured, it uploads the exact bytes directly to an immutable private `EU-transp-weekly` Release and writes a canonical private receipt. Without that secret it falls back to sanitized receipt-only mode and deletes plaintext with the runner workspace;
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
- `docs/PILOT-STATUS.md` — current validation evidence;
- `docs/CHUNKING-CONTRACT.md` — adapter-specific chunk planning and deterministic recomposition;
- `catalogues/` — open-data discovery/resolution portals kept separate from Fxx source identity.

## Governance boundary

A successful acquisition receipt is **changed-route evidence**, not canonical acceptance. Only the Mobilidade Norte private orchestrator may accept evidence, change rights/reuse state, update canonical manifests/catalogues, promote consumer assets or authorize downstream publication/Site ingestion.

**acquisition != validation != acceptance != reuse clearance != preservation != publication != Site ingestion**

Public availability is not equivalent to redistribution permission. Missing/confidential values are preserved as supplied by the producer and are never manufactured as zeros.

## Control plane

The private control plane can instruct this execution plane either with `repository_dispatch`
or, without consuming private Actions, by creating one tiny `requests/**.json` file containing
only a canonical `source_set_id` and unique `request_id`. The public push workflow then runs
on the free public hosted runner.

Producer credentials remain private. The optional `MN_PRIVATE_SINK_TOKEN` is not a producer
credential; it is a single-repository GitHub token used only to deliver unresolved-rights public
source bytes into the private canonical preservation layer.

For private-sink sources, successful acquisition evidence is written to
`receipts/Fxx/<native_asset_fingerprint>.json`. These receipts contain metadata,
source URLs, hashes, byte counts and validation state — never unresolved-rights source
bytes.

## Implemented adapter families

- Eurostat Statistics API / JSON-stat;
- INE Portugal bounded JSON/API with metadata-verified dimension selection;
- static HTTP assets (HTML, JSON, XLSX and related formats);
- static GTFS feeds;
- CKAN-discovered GTFS feeds;
- IGE table API, including verified repair for incomplete TLS certificate chains;
- OpenDataSoft-compatible pagination with deterministic JSONL recomposition;
- ArcGIS Feature Layer pagination with complete GeoJSON recomposition;
- HTML/download discovery for producer file series, with ordered series manifests;
- embedded Drupal Easychart/Highcharts pages, preserving native HTML and deterministic JSON/CSV chart payloads;
- open-data catalogue resolvers for `dados.gov.pt`, `datos.gob.es` and `data.europa.eu` (catalogue role only, never automatic Fxx identity).

Chunking is adapter-specific rather than universal. INE uses the proven 40,000-cell contract,
OpenDataSoft and ArcGIS use producer pagination, and heterogeneous file series are not blindly
row-concatenated. Producer-native chunks remain distinct from recomposed/derived outputs.

The public runner preserves producer-native bytes during validation and does not perform
consumerization.
