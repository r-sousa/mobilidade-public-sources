# MN-GEO-RAIL-001 — W2 G09: sondagem anónima leste, auditada (31/10/2026)

## Fonte, perímetro e execução

A [execução GitHub Actions #41190974922](https://github.com/r-sousa/mobilidade-public-sources/actions/runs/41190974922) terminou com sucesso após corrigir o ciclo de geração de janelas do primeiro ensaio. Foram realizadas **48 consultas STAC anónimas completas** (24 janelas WGS84 × 2 coleções nativas `MDT-2m` e `MDT-50cm`) no retângulo exploratório `[-7.25,41.40,-6.65,42.00]`. Todos os itens foram submetidos aos controlos existentes de geometria e extensão de resposta, e os dados de observação ficaram no [recibo fonte de 2,14 MB](../reports/mn-geo-rail-001/pt-dgt-macedo-braganca-anonymous-strip.json). Não há download de GeoTIFF, login, segredos, URLs assinados ou dados privados.

Este perímetro não é um eixo ferroviário selecionado nem valida a cobertura do corredor.

## Resultados de inventário cumulativo sem duplicações

O [ensaio de reconciliação independente #41191267756](https://github.com/r-sousa/mobilidade-public-sources/actions/runs/41191267756) verificou o relatório [de quatro ecrãs](../reports/mn-geo-rail-001/pt-dgt-four-screen-catalogue-union-qa.json) e preservou hashes SHA256 dos quatro recibos produtores. Foram deduplicados por coleção e ID de item original:

| Medida | Resultado |
| --- | ---: |
| E01-E06 + G07 + G08 — posições antigas por resolução | 4 333 |
| G09 — posições por resolução | 3 199 |
| G09 — IDs comuns ao inventário anterior | 462 |
| G09 — novos IDs, após deduplicação | 2 737 |
| **União das quatro sondagens, por resolução** | **7 070** |
| Janelas pesquisadas / consultas STAC completas | 56 / 112 |
| Sufixos de produtos 2m/50cm pareados | 7 070 |
| Pares 2m/50cm com envelopes WGS84 exatamente iguais | 7 016 |
| **Pares com envelopes WGS84 diferentes** | **54** |

As **54 discrepâncias** pertencem a produtos do setor norte G09, com diferenças de fronteira estimadas inferiores a 3 m (máximo observado próximo de 2 m). O relatório mantém os **54 identificadores originais, ambos os envelopes e um diagnóstico aproximado por par**. Estas diferenças não foram corrigidas por arredondamento ou suposta igualdade espacial. Resultam dos metadados do produtor e **não provam nem excluem diferenças nos píxeis originais**; a sua interpretação depende de inspeção nativa posterior. Não se confunde resolução nominal (0,5 m / 2 m) com equivalência geométrica, nem se utiliza o envelope STAC para medir NoData real.

## Qualidade, reprodutibilidade e governação

A união é reproduzível por `tools/geo_rail_pt_four_screen_union.py` a partir dos quatro recibos versionados e é testada por `tests/test_geo_rail_pt_four_screen_union.py`, com verificações de identidade, integridade, continuidade dos pedidos, pares de produtos, conflitos de envelopes entre diferentes sondagens e exatidão dos resultados acima. A aquisição G09 tem testes próprios de perímetro e paginação falhada.

**Estado:** W2 prossegue em pré-aceitação. Confirmam-se apenas **metadados**: 0 novos GeoTIFF, 0 km² novos de píxeis MDT realmente testados, nenhuma cobertura nativa contínua para Porto–Zamora, nem datum vertical harmonizado. **Sem Fxx, aceitação canónica ou publicação no Site**. A missão e os gates são acompanhados em [issue canónico #25](https://github.com/r-sousa/EU-transp-weekly/issues/25).
