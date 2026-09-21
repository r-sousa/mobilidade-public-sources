# Chunking and recomposition contract

Public acquisition does not assume that every producer can or should be acquired in one request.

The common contract is:

`plan → acquire chunks → validate every chunk → deterministic recomposition → completeness evidence`

Chunk semantics remain adapter-specific.

| Adapter/family | Chunk unit | Split trigger | Recomposition |
|---|---|---|---|
| INE JSON | period × dimension member groups | >40,000 planned cells, URL >1800 chars, producer `Cod=7`, saturated response | raw JSON chunks → deduplicated observation JSONL.GZ + coverage manifest |
| OpenDataSoft | API page/offset | producer page limit | pages → ordered JSONL.GZ + composition manifest |
| ArcGIS Feature Layer | `resultOffset/resultRecordCount` page | `maxRecordCount` | GeoJSON pages → one FeatureCollection + count proof |
| HTML-discovered file series | producer file/edition | one file per period/edition/product component | ordered series manifest; heterogeneous files are not blindly concatenated |
| Static HTTP | one producer object | none unless the product is explicitly a file series | no chunking |
| GTFS static/CKAN | one feed ZIP | none | structural validation; no artificial chunking |
| Eurostat | normally one bounded JSON-stat response | dataset-specific 413/size limits; future specs may partition dimensions/time where needed | adapter-specific, preserving JSON-stat semantics |
| IGE table API | one table response unless producer/API size requires a selection | producer-specific | table-specific; no artificial split by default |

## INE contract

The public INE adapter inherits the proven acquisition rules used in the private pipeline:

- `MAX_CELLS = 40_000`;
- one period member per initial plan branch;
- split `Dim2` first when possible, otherwise the largest splittable dimension;
- split again when the INE returns semantic error code 7 or a saturated response;
- keep request URLs below roughly 1800 characters;
- minimum two seconds between request starts;
- 15-second retry interval for transient failures;
- no more than three concurrent INE workers at orchestration level;
- preserve missing/confidential markers exactly; never coerce missing to zero;
- raw chunks remain native evidence; recomposed outputs are derived and excluded from the native-byte fingerprint.

## Spanish international trade

The Castilla y León international/intracommunity trade family (F31–F34) is explicitly included in the chunking model.

The regional operation is published by Estadística de Castilla y León using AEAT/Aduanas data. Its natural chunk is a producer file/edition (for example an annual ZIP/workbook or monthly publication), not a 40k dimensional API slice.

Therefore:

1. use already preserved F31–F34 private source/processed packages first;
2. when a successor edition is required, discover the official producer files;
3. download each edition/file as a native chunk;
4. hash and validate each file;
5. compose an ordered series manifest;
6. only perform row-level workbook reconciliation in a product-specific semantic assembler.

Authenticated DataComex access is a separate private-lane concern and is not used to validate the public adapter family.

## Completeness

A successful HTTP response is not enough.

Each chunked adapter must prove completeness using the producer's own contract where possible:

- INE: requested metadata members vs observed members;
- OpenDataSoft: `total_count` vs recomposed row count;
- ArcGIS: `returnCountOnly` vs recomposed feature count;
- file series: declared/discovered edition inventory vs acquired file inventory.

Recomposition never changes source identity, reuse state or canonical acceptance.
