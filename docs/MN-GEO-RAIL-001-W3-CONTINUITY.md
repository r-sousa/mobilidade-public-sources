# MN-GEO-RAIL-001 — W3, continuidade espacial de MDT espanhol

**Produtor:** IGN/CNIG. **Serviço:** [WCS de modelos digitais de terreno](https://servicios.idee.es/wcs-inspire/mdt).

## Verificação executada em 30 de outubro de 2026

A [execução #41141184949](https://github.com/r-sousa/mobilidade-public-sources/actions/runs/41141184949) concluiu **4/4 comparações** envolvendo duas resoluções e dois setores de Aliste, sem selecionar qualquer traçado ferroviário. Em cada setor e resolução foram descarregados separadamente dois blocos MDT adjacentes de **2 × 2 km** e uma consulta independente à respetiva **união de 4 × 2 km**.

| Setor | MDT | Células da união | Células válidas | Células mascaradas NoData | Diferença máxima perante a união independente |
|---|---:|---:|---:|---:|---:|
| Alcañices | 25 m | 12 800 | 12 800 | 0 | 0 m |
| Alcañices | 5 m | 320 000 | 320 000 | 0 | 0 m |
| Viñas | 25 m | 12 800 | 12 800 | 0 | 0 m |
| Viñas | 5 m | 320 000 | 320 000 | 0 | 0 m |

Foram verificados **16 km² de território**, sem duplicar a superfície por resolução. Os pixels e as máscaras dos blocos reconstituídos coincidem integralmente com os da consulta independente à união. Os 12 GeoTIFF foram utilizados apenas durante a execução; todos os bytes de origem foram eliminados, ficando guardados os hashes SHA-256 e indicadores técnicos.

**Recibo:** [es-adjacent-blocks-union-qa.json](../reports/mn-geo-rail-001/es-adjacent-blocks-union-qa.json).

## Limites

Os 16 km² não demonstram cobertura contínua de todo o território entre Porto e Zamora, nem validam exatidão altimétrica independente, referenciais verticais, detalhes de aterros/escavações ou geometria de traçados. Os locais são **áreas de verificação de dados**, não propostas de estações ou corredores.

O resultado é evidência técnica pré-canónica. Não foram atribuídos Fxx, preservados rasters nativos nem autorizada a publicação dos dados. O acompanhamento encontra-se no [issue #25](https://github.com/r-sousa/EU-transp-weekly/issues/25) e no [PR canónico #26](https://github.com/r-sousa/EU-transp-weekly/pull/26).
