# MN-GEO-RAIL-001 — índice preliminar R1 (Copernicus GLO-30)

Esta ferramenta **não adquire** altimetria nem altera o catálogo Fxx. Gera apenas um índice geoespacial de células candidatas para reconhecimento regional; depende de futura decisão canónica no repositório privado, [mission #25](https://github.com/r-sousa/EU-transp-weekly/issues/25).

## Executar localmente ou num worker já autorizado

```bash
python tools/geo_rail_r1_index.py \
  --bbox=-9,40.8,-5.5,42.5 \
  --output=r1_candidates.geojson
python -m unittest discover -s tests -p 'test_geo_rail_r1_index.py'
```

O retângulo `(-9,40.8,-5.5,42.5)` é **experimental**, suficientemente amplo para estudar vários eixos entre Porto e Zamora, e **não é** delimitação aceite do corredor. A execução produz 12 células candidatas de 1° × 1°, cada uma com `discovery_status=unverified`; não permite concluir que a cobertura R1 existe.

A identificação de células pode ser cruzada opcionalmente com a lista disponibilizada pelo produtor, após obtenção da fonte original:

```bash
python tools/geo_rail_r1_index.py \
  --bbox=-9,40.8,-5.5,42.5 \
  --tile-list=tileList.txt \
  --output=r1_candidates_indexed.geojson
```

O programa inscreve SHA-256 dos bytes da lista fornecida e distingue `listed_not_validated` de `not_in_supplied_list`. A mera presença na lista **não** equivale à confirmação de disponibilidade do objeto, leitura, georreferenciação, altimetria, extensão efetiva, direitos de redistribuição nem preservação. Nenhum download remoto é efetuado pelo programa.

**Fonte primária:** [distribuição pública Copernicus AWS](https://copernicus-dem-30m.s3.amazonaws.com/readme.html). GLO-30 é um **DSM**, não um MDT do solo. Referência horizontal WGS84 (EPSG:4326), vertical EGM2008. A harmonização com DGT/CNIG exige uma validação posterior específica.

**Gates seguintes:** validar bbox de estudo, obter footprints/URLs reais, ler metadados dos COGs, conferir NoData, CRS, continuidade e condições de reutilização; sujeitar a identidade Fxx e a preservação à governação privada. Não modificar `source_specs`, `requests`, workflows, tokens, secrets, nem declarar produtos aceites com base neste índice.

Este utilitário não cria processos agendados. Não existem aquisições autónomas lançadas por esta contribuição.

## Execução empírica no runner público — 30/10/2026

O índice preliminar sem informação externa evoluiu para dois ensaios reprodutíveis:

| Controlo | Resultado |
|---|---|
| [R1 metadata (run 41137817047)](https://github.com/r-sousa/mobilidade-public-sources/actions/runs/41137817047) | Sucesso |
| Fonte original `tileList.txt` (1 110 900 bytes) | 26 450 IDs; SHA-256 `10604e3052c98a09e9216f1a8f0a555a04148419757575f783d4937fd44316dc` |
| Células do envelope experimental | 12 de 12 listadas no produtor |
| Respostas individuais de HEAD | 12 de 12 com HTTP 200; soma `Content-Length` 490 765 676 bytes (468 MiB) |
| Pedidos HTTP Range por COG | 12 de 12 com assinatura TIFF válida; 3600×3600 segundo a IFD inicial |
| Bytes do prefixo de raster examinados | 196 608 (16 KiB × 12), sem transferência dos ficheiros completos |
| [Amostra de um raster nativo (run 41137911359)](https://github.com/r-sousa/mobilidade-public-sources/actions/runs/41137911359) | Sucesso |
| Raster N41_00_W008_00 | 44 038 002 bytes, SHA-256 `860fb53b25e4ebc2a519458e8e457211e808c7f0f10d80a3b0dc4d4c03e22715` |
| Validação da amostra | Float32, EPSG:4326, 3600×3600, resolução de 1 segundo de arco, 65 536 células válidas em janela 256×256 |
| Preservação dos GeoTIFF nativos | **Não efetuada**; o único ficheiro descarregado foi eliminado no final do ensaio |
| Autorizações de reutilização/publicação | **Aguardam aceitação canónica; nenhuma publicação de raster realizada** |

Recibos: `reports/mn-geo-rail-001/r1-20261030-producer-list-and-head.geojson` e `reports/mn-geo-rail-001/r1-single-tile-technical-validation.json`.

O teste de leitura completa só abrange um mosaico. Os 12 cabeçalhos são suficientes para confirmar a organização estrutural inicial mas **não** confirmam integridade, georreferenciação e continuidade de toda a coleção. A comparação com MDT DGT e CNIG permanece condicionada por cobertura, proveniência e datum vertical.

Os dois workflows introduzidos são **específicos desta branch de ensaio** e não substituem o contrato do mecanismo público Fxx. O merge dos relatórios/código não equivalerá à criação da identidade canónica nem à autorização para disseminar os rasters.
