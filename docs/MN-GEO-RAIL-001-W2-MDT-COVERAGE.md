# MN-GEO-RAIL-001 — W2 / inventário de metadados MDT da DGT

**Atualização:** 30 de outubro de 2026. Estado **candidato, não aceite canonicamente**.

## Resultado verificado

Foi confirmada a possibilidade de pesquisa **anónima de metadados** no Centro de Dados da DGT, através da interface STAC `/dgt-be/v1/search`. Na [execução pública #41139980884](https://github.com/r-sousa/mobilidade-public-sources/actions/runs/41139980884), doze consultas limitadas (seis janelas exploratórias WGS84 × `MDT-2m` / `MDT-50cm`) terminaram com HTTP 200 e **sem paginação remanescente**.

| Janela de diagnóstico | MDT 2 m — IDs únicos na janela | MDT 0,5 m — IDs únicos na janela |
|---|---:|---:|
| E01, Nordeste, setor norte | 108 | 108 |
| E02, Nordeste, setor sul | 108 | 108 |
| E03, setor de Macedo | 120 | 120 |
| E04, setor de Mirandela | 120 | 120 |
| E05, setor de Vila Real | 120 | 120 |
| E06, setor de Amarante | 108 | 108 |
| **Total nos seis setores** | **684** | **684** |

Não se observaram IDs repetidos na mesma coleção entre estas seis janelas. Os dois grupos são fontes/produtos distintos: **684 por resolução**, não 1 368 tiles espaciais independentes. Estes valores são **identificadores de itens de catálogo**, não 1 368 ficheiros descarregados, nem uma superfície contínua do Norte.

## Anomalia do metadado primário

Nos cinco setores mais orientais, o campo `bbox` de todos os objetos da amostra inicial não podia ser interpretado como WGS84. Exemplo do produtor, `MDT-2m`: `[110000,2,0,247000]`. A geometria GeoJSON `Polygon` do mesmo objeto tinha coordenadas longitude/latitude plausíveis.

O extrator distingue `source_bbox` e `geometry_recovered`, valida a faixa WGS84 portuguesa e a interseção com a janela pesquisada, e não associa ausência de cobertura à rejeição de um `bbox` inválido. Resultado por coleção: **576 envelopes recuperados da geometria** e **108 aceites do bbox original**.

## Ficheiros de evidência

- [Recibo de aquisição — metadados e hashes das respostas](../reports/mn-geo-rail-001/pt-dgt-mdt-sector-footprints.json).
- [Índice de revisão em GeoJSON — 1 368 retângulos candidatos](../reports/mn-geo-rail-001/pt-dgt-mdt-candidate-envelopes.geojson).

O GeoJSON foi construído por deduplicação de `collection + tile_id`, validando a conclusão das páginas e rejeitando conflitos de limites entre IDs. As geometrias são **envelopes retangulares**, não os polígonos originais e **não devem ser utilizadas para calcular percentagens de cobertura de MDT sem nova verificação**.

Os ficheiros não contêm assinaturas de URLs de descarga nem qualquer token, cookie ou sessão. A pesquisa de metadados foi anónima, mas a **descarga dos dados nativos continua sujeita ao regime de acesso do CDD**. A DGT anuncia licença geral de dados abertos CC BY 4.0; requer-se verificação da edição e dos assets concretos antes de uma publicação autorizada.

## Gates de governação

A identidade canónica Fxx ainda não foi atribuída, e esta aquisição não autoriza a publicação no Site Mobilidade Norte nem cálculos de declives ferroviários. Para o estudo seguinte é necessário: confirmar os ativos nativos e os direitos de download; recortar ao envelope oficial de estudo; validar NoData e pegadas originais; testar o sistema vertical; preservar ficheiros com SHA-256; e obter aceitação canónica. A autoridade mantém-se no [PR privado #26](https://github.com/r-sousa/EU-transp-weekly/pull/26) e [issue #25](https://github.com/r-sousa/EU-transp-weekly/issues/25).

**Fontes oficiais:** [DGT — descarregamento LiDAR](https://www.dgterritorio.gov.pt/descarregamento-de-dados-lidar-de-portugal-continental), [DGT — dados abertos](https://www.dgterritorio.gov.pt/dados-abertos), [CDD](https://cdd.dgterritorio.gov.pt/).

## Teste adicional de acesso a objetos nativos — W2, 30/10/2026

[Execução pública #41141266505](https://github.com/r-sousa/mobilidade-public-sources/actions/runs/41141266505), concluída com sucesso, [recibo de acesso](../reports/mn-geo-rail-001/pt-dgt-native-asset-preflight.json).

Foram identificados, em consultas STAC anónimas, dois objetos `MDT-2m`:
- Setor Mirandela — `MDT-2m-282510-09-2024`;
- Setor Amarante — `MDT-2m-200484-07-2025`.

Os dois metadados indicam o recurso `data`, com MIME `image/tiff; application=geotiff`. Em cada caso, um pedido `HEAD` anónimo ao host oficial `cdd.dgterritorio.gov.pt` **devolveu HTTP 302**. O redirecionamento foi deliberadamente **não seguido**, não houve envio de cookies/tokens/credenciais nem descarga de dados, e o recibo contém apenas host, status, tipo de recurso e SHA-256 da resposta STAC — **não** guarda URLs completas ou eventuais assinaturas.

**Conclusão limitada:** comprovação de descoberta pública do raster no catálogo, **não** comprovação de download anónimo. Um redirecionamento HTTP 302 não indica ausência do ficheiro; para avançar à aquisição dos bytes originais é necessário assegurar uma via de acesso autorizada, compatível com a autenticação exigida pelo CDD e sem colocar credenciais nas Actions públicas. A DGT indica explicitamente registo para descarregamento no [webinar CDD de 2025](https://www.dgterritorio.gov.pt/sites/default/files/ficheiros-artigos/Apresentacoes/2025/5-Webinar_LiDAR_15jul2025.pdf).

O relatório distingue, assim, três níveis: **STAC consultável**, **asset nativo catalogado** e **dados nativos efetivamente obtidos e validados**. Apenas os dois primeiros se encontram comprovados nos ensaios portugueses atuais.
