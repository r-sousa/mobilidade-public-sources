# Initial private-workflow migration inventory

This inventory is preparatory only. No legacy workflow is deleted or disabled by this file.

| Private workflow / family | Current public replacement | Private sink? | Retirement readiness | Disposition |
|---|---|---:|---|---|
| `mn-source-bridge-eurostat.yml` | `eurostat` adapter | yes unless already cleared | Pilot F01 proven; F148 private sink pending | Retire only after F148 receipt reconciliation is proven |
| `mn-source-bridge-ansr.yml` | `static_http` + XLSX validation | yes | Spec F49 staged | Retire after private receipt + idempotency test |
| INE part of `mn-source-bridge-ine-amt.yml` | `ine_json` | normally yes unless explicitly cleared | F85 staged | Split from AMT; retire INE bridge after pilot |
| AMT part of `mn-source-bridge-ine-amt.yml` | static/report discovery not yet generalized | yes | Not ready | Keep private workflow until static/operator-native adapter is proven |
| `ine-full.yml`, `ine-spacing-trial.yml`, `mn26-ine-source.yml` | `ine_json` | depends on source rights | Candidate | Consolidate only after bounded INE pilot coverage is validated |
| `mn26-w3-ige-successor-source.yml`, `mn26-w4-ige-source.yml` | `ige_table` | yes while rights unresolved | F30 staged | Retire source-specific acquisition after IGE API pilot |
| `mn26-w1-jcyl-source.yml`, `mn26-w4-jcyl-source.yml` | `opendatasoft` / static HTTP | yes while canonical rights unresolved | F181 staged | Retire only source products covered by exact public API specs |
| `mn26-w5-gtfs.yml`, `mn26-w6-metro-gtfs.yml` | `ckan_gtfs` / future static GTFS adapter | source-specific | F12 runner reached producer but official DNS currently fails | Keep until producer route is operational and more feeds are covered |
| `mn26-apdl-f09-cache-source.yml` | `static_http` candidate | yes | Not yet proven | Keep; migrate after exact underlying APDL data assets are pinned |
| `mn26-cnmc-rail-source.yml` | static/API family candidate | yes | Not yet implemented | Keep |
| `mn26-dgt-source.yml`, `mn26-dgt-cos-source.yml` | future ArcGIS/open-geospatial adapter | yes | Adapter not yet implemented | Keep |
| `mn-source-bridge-authenticated.yml` (DataComex/Aena) | **No public replacement** | private lane only | Intentionally excluded | Keep private; never migrate credentials or sessions |

## Retirement gate

A legacy workflow becomes retirement-ready only when the replacement has demonstrated:

1. a public hosted runner starts;
2. exact producer bytes are acquired and hashed;
3. native semantics are preserved;
4. the correct public/private sink is selected;
5. private receipt delivery works where required;
6. reruns are idempotent;
7. the private orchestrator reconciles the receipt without granting it canonical authority;
8. no reuse/right state is silently promoted.

Retirement itself is a later explicit cleanup step.
