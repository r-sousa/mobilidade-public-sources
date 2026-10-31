# MN-GEO-RAIL-001 — Origem DGT 279503: QA original e controlo NP159

**31/10/2026 — pré-aceitação, sem atribuição Fxx.**

A [execução protegida #41191696943](https://github.com/r-sousa/mobilidade-public-sources/actions/runs/41191696943) foi concluída com sucesso em `main`: gate de proteção, autenticação DGT `dgt-cdd`, descarga de um original `MDT-2m-279503-09-2024`, QA de geometria, NoData, SHA256 e comparação **contextual** de cota do terreno na posição WFS NP159. A [Release pública de pré-aceitação](https://github.com/r-sousa/mobilidade-public-sources/releases/tag/mn-geo-rail-001-dgt-279503-NP159-preacceptance-41191696943) contém o raster original e o QA completo num **job de publicação separado sem credenciais**. A licença comunicada é CC BY 4.0, com atribuição DGT.

## Resultado confirmado de fonte

| Elemento | Resultado |
| --- | --- |
| GeoTIFF original | `original-DGT-279503.tif` |
| Byte count | 1 212 288 |
| SHA256 original | `b9ca562fa7890a39e32646e85fdd6abd87f12b51c4a7b6eb907e10a2aba49879` |
| SHA256 recibo QA | `c0f86ac10f572b6fa24d4c0507abfad5f71acc632dbf033a0121f4725a332473` |
| CRS horizontal | EPSG:3763 |
| Bounding box PT-TM06 | [79000,202000,80000,203000] |
| Resolução, píxeis | 2 m; 500 × 500, 250 000 válidos, 0 mascarados |
| Cotas do raster original | 212,570–287,267 m |
| Referencial vertical | Cascais na documentação do produtor, **não codificado como vertical CRS no próprio GeoTIFF** |

A independência do controlo incluiu nova leitura do GeoTIFF e dos artefactos GitHub, com hash original igual ao `digest` do asset publicado e amostragem independente através do `rasterio`.

## NP159: o que a evidência demonstra e não demonstra

O WFS da DGT apresenta **cinco marcas fisicamente distintas** (NP159 e quatro variantes) com a mesma geometria substituta `(79468,618;202288,178)`. O centro de célula mais próximo no GeoTIFF é `(79469,202289)`, a 0,906 m dessa posição nominal. A **cota de terreno nessa célula é 229,549667 m**; a vizinhança 3×3 varia entre 229,345657 e 229,744156 m, com mediana 229,549667 m. Nenhuma destas cotas é a altitude **no local de implantação de cada marco**: não existem coordenadas físicas individuais verificadas. A amplitude de alturas publicadas para as cinco marcas não pode ser transformada em RMSE nem resíduos das cinco marcas. **Não foi calculado viés vertical, precisão vertical do MDT, nem harmonização PT–ES.**

Este novo quilómetro quadrado é **separado** dos 12 km² contíguos de origem DGT já preservados em Mirandela; são **13 km² de raster nativo distintos ensaiados e preservados**, mas não um mosaico contínuo de 13 km². Continua ausente a validação de continuidade da cobertura Porto–Zamora.

[Recibo resumido e hashes](../reports/mn-geo-rail-001/pt-dgt-native-279503-NP159-source-qa-acceptance.json). Relatório completo preservado na Release; o resumo não substitui a fonte original. **G1/G3/G5 abertos; G2 e G4 parciais.** O sucesso do workflow não concede autorização de Site, Fxx ou utilização de perfis ferroviários.
