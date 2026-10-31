# MN-GEO-RAIL-001 — W2: ensaio português de continuidade em duas quadrículas nativas

**Objetivo limitado:** verificar uma fronteira comum de 1 km entre dois MDT-2m originais da DGT, com 2 km² no total, a partir do acesso registado e de recibo de QA sanitizado.

## Quadrículas autorizadas

| Papel | ID original DGT | Limites esperados EPSG:3763 |
|---|---|---|
| Norte (já validada e preservada em Release) | `MDT-2m-282510-09-2024` | [82000,209000,83000,210000] |
| Sul (metadados STAC revistos; ainda não adquirida) | `MDT-2m-282509-09-2024` | [82000,208000,83000,209000] |

As fronteiras da quadrícula sul são uma **hipótese de teste** a confirmar no GeoTIFF, não uma geometria nativa já verificada. Os envelopes WGS84 originais estão no índice STAC DGT já preservado. Se o segundo raster não tiver exatamente os limites previstos, o ensaio falha e não afirma continuidade.

## Fluxo protegido

O ficheiro [`mn-geo-pt-cdd-pair-pilot.yml`](../.github/workflows/mn-geo-pt-cdd-pair-pilot.yml) só dispõe de `workflow_dispatch`, na `main` protegida, com `environment: dgt-cdd` e os dois *secrets* existentes. A sua execução **não** é automaticamente iniciada por PR ou `push`, e depende das condições de aprovação do Environment. Não criar/rodar tokens nem apresentar credenciais no chat.

No GitHub, selecionar Actions → **MN-GEO-RAIL-001 DGT protected Mirandela adjacent 2-tile QA** → **Run workflow** → branch **main**. O procedimento adquire temporariamente os **dois IDs exatos**, impõe 25 MB por GeoTIFF, 50 MB de conjunto, valida SHA-256, EPSG:3763, resolução de 2 m e 500×500 células por objeto, além de verificar a fronteira comum de 500 pares de células. São registadas as contagens válidas e estatísticas das diferenças de altitude entre células vizinhas; **não** se presume igualdade entre as suas cotas reais.

Os GeoTIFF, cookies e URLs assinados são eliminados no fim do job. Apenas o recibo técnico JSON, sem estes dados, é conservado durante 15 dias no artefacto `mn-geo-rail-001-dgt-pair-qa-<run_id>`. Não é criada Release adicional, nem Fxx, nem dados para o Site.

## Condições de aceitação

O teste só pode ser descrito como validado após execução autenticada real, dois GeoTIFF conformes, dois hashes reais, fronteira partilhada exata, máscaras válidas e 500 pares de células finitos. Mesmo então, valida apenas **2 km²** nas imediações de Mirandela. A transformação de referencial vertical e a continuidade Porto–Trás-os-Montes–Zamora continuam em aberto.

**Estado da preparação:** código e testes em revisão; execução real condicionada ao lançamento manual protegido. Esta documentação não substitui a evidência futura do run.
