# Temporary public-runner bridge to private preservation

This bridge exists because GitHub-hosted Actions in `r-sousa/EU-transp-weekly` are temporarily unavailable while the private-repository quota is exhausted.

The public repository remains only an execution plane. The private repository remains canonical.

## Security model

The workflow `.github/workflows/recover-private-preserved-public.yml` is **manual-dispatch only**. It has no `pull_request`, `push` or scheduled trigger.

It uses one temporary secret:

`MN_PRIVATE_READ_TOKEN`

The credential must be a fine-grained GitHub personal access token restricted to the single private repository:

`r-sousa/EU-transp-weekly`

Required repository permission:

- **Contents: Read-only**

No write permission to the private repository is required. Do not grant Administration, Actions, Workflows, Secrets, Packages, Issues, Pull requests or organisation-wide access.

Recommended expiry for the temporary bridge: **7 days**. Remove the secret when private Actions become available again.

## Setup

In `r-sousa/mobilidade-public-sources`:

1. Open **Settings → Secrets and variables → Actions**.
2. Create repository secret **MN_PRIVATE_READ_TOKEN**.
3. Paste the fine-grained token value there. Never put the token in a source file, issue, chat, receipt or workflow input.
4. Open **Actions → Recover preserved public data from private repository → Run workflow**.
5. Leave `source_set_id` blank for the configured bootstrap batch, or supply one Fxx for a bounded test.

## Publication gate

The workflow does not equate "public source" with "publicly redistributable bytes".

For each source set it requires all of the following:

1. Fxx is present in the private canonical `byte-redistribution-candidates.json`;
2. the private canonical manifest still says `public_reuse_status=verified` and public export is eligible subject to asset-level check;
3. the private Release asset SHA-256 matches both GitHub's recorded digest and the configured expected digest;
4. a product-specific asset-level check passes:
   - Eurostat: package identity matches the Eurostat product code;
   - INE: package identity matches the indicator and the private licence evidence says CC BY 4.0;
   - STCP GTFS: canonical licence is CC0-1.0 and the package contains the required GTFS files.

Only then is the exact preserved package uploaded as a public prerelease in this repository.

Sources with unresolved reuse rights are **not** included in this bootstrap configuration. They may later be inspected ephemerally by a separate audit-only lane but their bytes must not be persisted in this public repository.

## Bootstrap coverage

F01 is skipped because a direct public-source Release already exists.

The initial preserved-data bootstrap covers:

- F02–F04 — Eurostat;
- F12 — STCP GTFS;
- F19–F23 — INE;
- F24 — Eurostat;
- F25–F26 — INE.

The private source is the current consolidated Release `data-20260915-9d994478fdb13e04`; each recovered public Release records the private preservation tag, source asset SHA-256 and the checks used to authorize publication.
