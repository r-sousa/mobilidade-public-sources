# Private canonical sink

The preferred control direction is:

`EU-transp-weekly orchestrator → public request file → public acquisition runner → private sink + sanitized public receipt`

This allows genuinely public producer acquisition to use free public GitHub-hosted runners while the private repository remains canonical.

## Optional sink secret

Configure this secret **only in** `r-sousa/mobilidade-public-sources`:

`MN_PRIVATE_SINK_TOKEN`

Use a fine-grained personal access token restricted to:

- repository: `r-sousa/EU-transp-weekly` only;
- repository permission: **Contents — Read and write**;
- no Administration, Actions, Secrets, Packages, Issues, Pull requests or organisation/account-wide permissions.

The token value must never appear in chat, source files, logs, receipts, Releases or Actions artifacts.

## Behaviour with the secret

For a source spec with `sink: private` the public runner:

1. acquires the genuinely public producer bytes;
2. validates native format/semantics;
3. calculates SHA-256 and native source-object fingerprint;
4. creates or reuses an idempotent private prerelease in `EU-transp-weekly`;
5. uploads and downloads-back-verifies each exact native asset;
6. writes an immutable private receipt under:

   `statistics/recovery-20260920/simple-runtime/public-acquisition-receipts/Fxx/<fingerprint>.json`

7. writes only a sanitized receipt to this public repository.

No canonical source-set manifest is changed by the public runner.

## Behaviour without the secret

Acquisition still runs successfully in receipt-only mode:

- producer bytes are acquired/validated/hashed ephemerally;
- a sanitized public receipt is persisted;
- plaintext source bytes disappear with the runner workspace;
- the private orchestrator records `PUBLIC_ACQUISITION_VERIFIED_RECEIPT_ONLY`.

This fallback is safe, but byte-dependent normalization remains pending.

## Request without private Actions

The private orchestrator need not call a private GitHub Action. It may create exactly one request file in this public repository:

```json
{
  "source_set_id": "F148",
  "request_id": "MN-PRIVATE-CTRL-F148-20260921T0910"
}
```

Any `requests/**.json` push triggers the generic public acquisition workflow.

## Governance

A private-sink receipt is preservation evidence, not analytical acceptance.

Only the private Mobilidade Norte orchestrator may:

- accept source evidence canonically;
- change rights/reuse state;
- update `Fxx` manifests/catalogues;
- authorize consumer/publication/Site promotion.

Public availability and successful acquisition never imply redistribution permission.
