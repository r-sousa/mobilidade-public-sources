# Private control plane and canonical sink

The public repository does **not** hold a credential for `r-sousa/EU-transp-weekly`.

The direction of control is:

`private orchestrator → repository_dispatch → public acquisition runner → sanitized public receipt → private acceptance/preservation`

## Secret location

A dispatch credential, if a PAT is used initially, belongs **only in the private repository**:

`r-sousa/EU-transp-weekly → Settings → Secrets and variables → Actions → New repository secret`

Suggested name:

`MN_PUBLIC_ACQUISITION_TOKEN`

Recommended initial credential: a fine-grained PAT restricted to the single repository
`r-sousa/mobilidade-public-sources`.

Minimum repository permission for the current `repository_dispatch` design:

- **Contents: Read and write** on `r-sousa/mobilidade-public-sources`;
- Metadata read access is implicit.

Do not grant access to any other repository and do not grant Administration, Secrets,
Packages, Issues, Pull requests or organisation/account-wide permissions.

A GitHub App installation token is preferable later for shorter-lived credentials and
narrower audit/revocation boundaries.

## Public runner behaviour

For a source whose canonical sink is private, the public runner:

1. acquires the genuinely public producer response;
2. validates native format/semantics;
3. computes SHA-256 and byte counts;
4. deletes the plaintext with the ephemeral runner workspace;
5. persists only a sanitized receipt under `receipts/Fxx/<fingerprint>.json`.

No producer bytes with unresolved redistribution status are uploaded as public
Releases or Actions artifacts.

## Private reconciliation

The private orchestrator reads the public receipt and remains the only authority that
may accept it. When preservation is warranted, the private side reacquires the same
producer URL, verifies that SHA-256 and byte count match the public evidence, and then
creates/reuses the canonical private source object and immutable receipt.

This deliberately trades one repeated download for a stronger security boundary:
no private-repository credential or producer credential is ever present in the public
execution plane.

A future encrypted-spool or GitHub-App broker may remove the repeated download without
weakening this boundary, but it is not required for the initial architecture.
