# MN-GEO-RAIL-001 — W4, referenciais altimétricos e transformação Cascais–Alicante

**Data da prova:** 30 de outubro de 2026. **Estado:** operação de grelhas reproduzida em pontos de teste; **harmonização de rasters ainda não executada**.

## Referências e componentes

- Portugal continental: sistema horizontal PT-TM06/ETRS89 (`EPSG:3763`) e **Cascais height** (`EPSG:5780`). [DGT — modelos digitais](https://www.dgterritorio.gov.pt/atividades/cartografia/cartografia-topografica/modelos-digitais); [DGT — sistemas de referência](https://www.dgterritorio.gov.pt/atividades/geodesia/sistemas-referencia).
- Espanha peninsular: ETRS89/UTM 30N (`EPSG:25830`), **Alicante height** (`EPSG:5782`), sistema altimétrico nacional [REDNAP](https://datos-geodesia.ign.es/geoide/Leeme_Readme.pdf).
- Copernicus GLO-30: **DSM**, altitudes associadas ao referencial EGM2008 (`EPSG:3855`); não converter automaticamente estes valores para os referenciais ibéricos sem operação específica.
- Grelhas disponíveis no [PROJ CDN](https://cdn.proj.org/), identificadas no catálogo oficial de grids como licenciadas de forma aberta:
  - `pt_dgt_GeodPT08.tif`, **81 638 bytes**, SHA-256 `8c006ae3afa037c214d30e7ec97736452705773ccb663274e003ced1d08ccaa0`.
  - `es_ign_egm08-rednap.tif`, **827 857 bytes**, SHA-256 `d1758a580c2acc7cddcb814c2aebe1e5ab83f74dfaed8c1a885355bb3f85df58`.

## Ensaio empírico

A [execução W4 #41141813957](https://github.com/r-sousa/mobilidade-public-sources/actions/runs/41141813957) concluiu com sucesso. Foram temporariamente descarregadas as duas grelhas PROJ, ambas verificadas como TIFF e lidas espacialmente; registaram-se limites, resolução da grelha, checksums e validade dos valores. Os ficheiros foram destruídos após a prova, sem serem publicados no repositório.

O PROJ, inicialmente sem as duas grelhas, apenas tinha disponível uma transformação Cascais–Alicante de exatidão nominal **0,2 m**, indicando a transformação com grelhas como indisponível. Depois da introdução das duas grelhas, passou a oferecer a operação baseada em `pt_dgt_GeodPT08.tif` e `es_ign_egm08-rednap.tif`, com exatidão nominal declarada de **0,09 m**.

Uma primeira chamada não devolveu valores finitos devido à ordem dos eixos. A prova final controlou explicitamente as convenções `lat,lon` do CRS vertical e `lon,lat` do pipeline equivalente e obteve valores finitos nestes pontos ilustrativos de entrada **0 m Cascais**:

| Coordenada de ensaio | Altura sintética resultante em Alicante |
|---|---:|
| Mirandela (-7,2; 41,5) | +0,102749 m |
| Nordeste português (-6,9; 41,75) | −0,030255 m |
| Amarante (-8,1; 41,26) | +0,083000 m |
| Alcañices (-6,34647; 41,6994) | −0,057913 m |
| Zamora (-5,746992; 41,50378) | Não definida para a grelha portuguesa nesse ponto |

**O valor 0 m é apenas um parâmetro sintético da prova, não uma altitude observada.** Estes números não são pontos de controlo altimétrico, nem substituem validação geodésica. Mostram, contudo, que o ajuste não deve ser presumido constante.

## Condições obrigatórias para avançar à harmonização

1. Confirmar nos metadados técnicos de cada MDT do CDD e do IGN/CNIG qual o referencial vertical efetivamente codificado ou declarado; os GeoTIFF WCS espanhóis testados estavam identificados com CRS horizontal `EPSG:25830`, **não codificavam explicitamente `EPSG:5782`**.
2. Identificar extensão espacial de aplicação das grelhas e garantir que ambas são válidas onde se pretende converter. Em Zamora, o GeoTIFF português GeodPT08 não abrange o ponto de teste.
3. Confrontar as operações com marcos altimétricos ou outra evidência geodésica de controlo, em especial na fronteira.
4. Controlar explicitamente ordem dos eixos, NoData, unidades, altura ortométrica versus elipsoidal e rastreabilidade do pipeline, incluindo as grelhas e os respetivos hashes.
5. Aplicar apenas após aceitação canónica, com preservação dos produtos derivados e do metadado de transformação. **Não foram processados MDT completos nem produzidos perfis ferroviários nesta prova.**

**Recibo técnico completo:** [vertical-cascais-alicante-grid-audit.json](../reports/mn-geo-rail-001/vertical-cascais-alicante-grid-audit.json).

**Governação:** [issue MN-GEO-RAIL-001](https://github.com/r-sousa/EU-transp-weekly/issues/25) e [PR privado #26](https://github.com/r-sousa/EU-transp-weekly/pull/26).
