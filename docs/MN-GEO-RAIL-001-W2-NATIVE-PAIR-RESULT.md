# MN-GEO-RAIL-001 — duas quadrículas DGT nativas em Mirandela

**Data da verificação:** 31/10/2026, 01:53 UTC. **Execução protegida:** [#41157391300](https://github.com/r-sousa/mobilidade-public-sources/actions/runs/41157391300), `success`.

Foi adquirida uma segunda quadrícula DGT `MDT-2m-282509-09-2024` com credenciais do ambiente GitHub `dgt-cdd`, sem intervenção do dispositivo do utilizador, e confrontada com a já preservada `MDT-2m-282510-09-2024`. A aquisição e o QA nativo concluíram com sucesso.

| Controlo | Resultado |
|---|---|
| Superfície conjunta real | 2 km² |
| Sistema horizontal, resolução | EPSG:3763, 2 m |
| Píxeis válidos (2 rasters) | 500 000 / 500 000 |
| Linha de fronteira comum | Y = 209 000 m PT-TM06 |
| Células adjacentes válidas | 500 / 500 |
| Diferença absoluta mediana entre vizinhos | 0,202393 m |
| Diferença absoluta máxima entre vizinhos | 2,163391 m |
| Diferença média com sinal (sul menos norte) | −0,101626 m |
| Datum vertical comprovado no GeoTIFF / por vértice geodésico | Não |
| Rasters publicados nesta execução | Nenhum |

SHA-256 dos GeoTIFF: quadrícula norte `761bc7ee18ef9377cca97556b6dececc14b8765c017c168dbf15552d8c9d78ba` (1 219 159 bytes), quadrícula sul `31027123ea8ba72cd0c24985467b0d1ba2ace562ef2523491144b07f2116af63` (1 214 414 bytes).

O [recibo derivado](../reports/mn-geo-rail-001/pt-dgt-mirandela-native-two-tile-seam-qa.json) preserva os resultados e a referência à prova original. O artefacto da execução (ID `13025677170`, conservado até 15/11/2026) contém o recibo original sanitizado de 6655 bytes; SHA-256 `542973c7e7be017e522d554c2d1a48c6e45032b1a1d213a4df6e2be7b593ed8c`; o ficheiro ZIP tem SHA-256 `a47a91c30da9829c6b3b8ae4e7d563969a81b542c3e283c35e6763c5c3161aa5`.

A quadrícula norte já se encontra preservada na [Release de pré-aceitação](https://github.com/r-sousa/mobilidade-public-sources/releases/tag/mn-geo-rail-001-dgt-mdt2m-mirandela-sha256-761bc7ee18ef9377). A quadrícula sul **não foi preservada** após a saída do runner. As diferenças entre células vizinhas correspondem à variação do terreno, não à diferença entre duas medições do mesmo ponto. Dois quilómetros quadrados contíguos **não** comprovam a continuidade da cobertura regional ou a transformação de datum para Espanha. A publicação do raster sul e a aceitação Fxx requerem deliberações separadas.
