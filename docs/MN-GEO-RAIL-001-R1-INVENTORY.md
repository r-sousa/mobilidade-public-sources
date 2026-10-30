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
