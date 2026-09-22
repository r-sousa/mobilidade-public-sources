# Acquisition mechanism coverage

This document maps public-source technical families to reusable acquisition mechanisms.
It is deliberately **not** an Fxx allocation or migration decision.

No source listed here is acquired merely because a mechanism exists. Canonical identity,
preserved-first state, reuse clearance and execution authorization remain separate.

## Statistical and economic APIs

| Source family | Mechanism | Notes |
|---|---|---|
| INE Portugal | `ine_json` | Metadata-defined partitioning, 40k-cell cap, Cod=7 resplitting and deterministic recomposition. |
| IGE Galicia | `ige_table` | Native IGE table API with TLS-chain repair where needed. |
| Eurostat dissemination | `eurostat` | Bounded Statistics API / JSON-stat. |
| Eurostat Comext / PRODCOM | `sdmx_rest` | Dedicated Comext endpoint; queries must be bounded/filtered for detailed trade data. |
| OECD Data Explorer | `sdmx_rest` | Public SDMX REST; explicit dataflow/query required. |
| Banco de Portugal BPstat | `bpstat_jsonstat` | Explicit domain/dataset/series selection. |

## Geospatial services

| Source family | Mechanism | Notes |
|---|---|---|
| ArcGIS Feature Layer | `arcgis_feature_service` | Count-based pagination + GeoJSON recomposition. |
| OGC API - Features | `ogc_api_features` | Follows producer `rel=next` pagination. |
| WFS 2.0/1.x | `wfs` | Preserves capabilities and feature pages; GeoJSON recomposed, GML retained as ordered series. |
| Atom download feeds | `atom_feed` | Preserves feed and linked distributions; suitable for INSPIRE/download services. |
| Static geospatial packages | `static_http` / `html_assets` / `ckan_resource` | ZIP/GPKG/GML and related producer files. |

APA/SNIAmb and other INSPIRE publishers may expose a mixture of WFS, downloadable ZIPs
and ArcGIS/OGC services. The mechanism is selected from the actual producer distribution,
not from the institution name.

## Transport-sector public sources

| Source family | Mechanism | Notes |
|---|---|---|
| GTFS direct | `gtfs_static` | Producer-native feed validation. |
| GTFS via CKAN | `ckan_gtfs` | CKAN discovery plus GTFS structural validation. |
| Generic CKAN | `ckan_resource` | Non-GTFS resources selected by format/name/URL contract. |
| DG MOVE Statistical Pocketbook | `html_assets` | Edition/file-series model for XLSX publications. |
| TEN-T map/public file library | `html_assets` / geospatial mechanism when a documented public distribution exists | Do not assume the provider-facing TENtec API is a public read API. |
| ERA Knowledge Graph | `sparql_json` | Read-only bounded SELECT/ASK queries. |
| EMSA public WFS services | `wfs` | Suitable for public feature services such as location/reference data. |
| EMSA public full-dataset binary REST | `static_http` | AVRO object-container validation is available when the product exposes a stable public URL. |

## Research and innovation

| Source family | Mechanism | Notes |
|---|---|---|
| CORDIS framework-programme open-data downloads | `html_assets` / `static_http` | Public bulk/open-data files are preferable to authenticated extraction for reproducible snapshots. |
| EURIO / CORDIS Linked Open Data | `sparql_json` | Bounded read-only knowledge-graph queries. |
| CORDIS DET API | private/controlled lane | The extraction API requires an API key; it is not a public-runner mechanism. |

## Education and science (DGEEC)

DGEEC currently exposes a mixture of public HTML tables, Power BI dashboards, XLSX/ODS
downloads and catalogue/geospatial services. The public engine therefore relies primarily on:

- `html_assets` for publication pages and file series;
- `static_http` for known XLS/XLSX/ODS files;
- `ckan_resource` when a dados.gov.pt/CKAN resource resolves the producer distribution;
- `wfs` only where an actual feature service exists.

ODS and legacy XLS validation are supported by the engine. WMS is treated as a portrayal
service, not as a substitute for underlying feature/statistical data.

## Energy (DGEG)

DGEG publishes long annual/monthly series primarily as linked XLS/XLSX files and some
indicators are also disseminated through INE. Current mechanisms are therefore normally
sufficient:

- `html_assets` / file-series for DGEG workbooks and publications;
- `static_http` for stable known files;
- `ine_json` when the primary statistical dissemination route is the INE indicator API.

A DGEG-specific adapter should only be introduced if a stable machine API is documented
that cannot be represented by these mechanisms.

## Environment (APA)

APA/SNIAmb has substantial geospatial open-data coverage. Public distributions commonly
include WFS, WMS and downloadable ZIP packages. For acquisition:

- prefer `wfs` for vector feature data;
- prefer producer ZIP/GeoPackage distributions through `static_http`/`html_assets`;
- use `arcgis_feature_service` or `ogc_api_features` when those are the actual producer services;
- do not treat WMS imagery as equivalent to vector/source observations.

## Generic bounded mechanisms

- `rest_json`: explicitly declared bounded REST/JSON calls;
- `sdmx_rest`: explicitly bounded SDMX REST data and optional structure;
- `sparql_json`: read-only bounded SPARQL SELECT/ASK;
- `ckan_resource`: generic CKAN resource resolver;
- `html_assets`: HTML-discovered producer file series;
- `atom_feed`: producer download-feed series.

These generic mechanisms are intentionally conservative: they do not crawl arbitrary APIs,
infer joins, manufacture pagination rules, or silently convert public accessibility into
redistribution clearance.


## TENtec / TEN-T

The public TENtec surface is not limited to static maps. An official European Commission
ArcGIS REST MapServer is publicly exposed for TENtec network layers. The current
`arcgis_feature_service` adapter operates on queryable ArcGIS layer endpoints and is
therefore also applicable to `MapServer/{layer}` sublayers when the layer metadata exposes
geometry and fields. The separate `wfs` adapter covers TENtec layers whenever the
corresponding WFS service endpoint is publicly exposed.

This means TENtec does not require a TENtec-specific acquisition adapter. The preferred
mechanism is selected per actual public distribution: ArcGIS REST layer, WFS, or static map/file.

## NAP Portugal

The Portuguese National Access Point is best treated as both a **transport catalogue/resolver**
and, for some records, an authoritative access surface. Its multimodal catalogue describes or
links datasets including STePP public-transport geometry, NeTEx-oriented information and records
with explicit WFS (GeoJSON) access URLs.

Relevant mechanisms now include:

- `wfs` for records exposing WFS/GeoJSON;
- `static_http` for Shapefile/ZIP/NeTEx downloads and stable linked distributions;
- `rest_xml` for bounded public DATEX II / NeTEx XML endpoints;
- `html_assets` when a NAP record resolves to a producer file page;
- `gtfs_static` where a linked producer distribution is GTFS.

NAP catalogue metadata must remain distinct from the underlying producer dataset identity.
A future NAP catalogue resolver may be useful, but it should resolve access URLs rather than
allocate new canonical Fxx identities automatically.

## UVE charging-station list

The UVE rapid-charging list is a substantial public HTML table maintained as a continuously
updated user-oriented inventory. It is useful as a **secondary validation/coverage source**,
not as the preferred canonical charging-network source when a primary MOBI.E/official dataset
exists.

The `html_table` mechanism preserves the raw page as the native object and emits a deterministic
derived table representation for comparison and QA. No redistribution or canonical-promotion
decision follows from the existence of this mechanism.

## ACAP / MotorData

ACAP publishes sector statistics through public ACAP pages and embedded MotorData tables/charts.
Some public views expose HTML tables directly, while annual statistical editions are publication/file
products. Appropriate mechanisms are therefore:

- `html_table` for public MotorData/ACAP tabular views;
- `html_assets` / `static_http` for public annual reports or downloadable files;
- `rest_json` only if ACAP documents a stable public machine endpoint.

The public statistics mechanism must not be confused with reserved MotorData/AutoInforma areas,
which remain outside the public runner. Reuse/publication rights require a separate assessment.
