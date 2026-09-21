# Private canonical sink

The public acquisition workflow uses one GitHub Actions secret:

`MN_PRIVATE_SINK_TOKEN`

Create it in **r-sousa/mobilidade-public-sources → Settings → Secrets and variables → Actions → New repository secret**.

Recommended initial credential: a **fine-grained personal access token** restricted to the single repository `r-sousa/EU-transp-weekly`.

Minimum repository permission required by the current implementation:

- **Contents: Read and write** — create/read Releases and create immutable receipt files on the governed branch.
- Metadata read access is implicit.

Do **not** grant Actions, Administration, Issues, Pull requests, Secrets, Workflows, Packages or organisation/account-wide permissions.

The token is used only at workflow runtime. It must never be pasted into source specifications, logs, receipts, Releases or ChatGPT.

A GitHub App installation token is a preferable later hardening step because it can provide shorter-lived credentials and tighter revocation/audit boundaries. It is not required for the pilot architecture.
