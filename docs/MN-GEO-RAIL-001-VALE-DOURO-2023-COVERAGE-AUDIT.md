# MN-GEO-RAIL-001 — confronto da proposta Associação Vale d’Ouro com os rasters Copernicus adquiridos

**31/10/2026. Proposta externa distinta de uma alternativa independente concebida por Mobilidade Norte.**

## Objeto exato verificado

A [página original da Associação Vale d’Ouro](https://www.avtrasosmontes.associacaovaledouro.pt/) disponibiliza uma revisão de **11 de janeiro de 2023** da proposta de linha de alta velocidade **Porto–Zamora**, com [sumário executivo oficial do promotor](https://www.avtrasosmontes.associacaovaledouro.pt/estudo_rev01/ASCVD.LAVTM.SUM-EXECUTIVO.pdf) e [planta de localização](https://avtrasosmontes.associacaovaledouro.pt/estudo_rev01/LAVTM.00.G-01.pdf). A revisão de 2023 usa **AFSC–Paços de Ferreira–Amarante–Vila Real–Alijó/Murça–Mirandela–Podence/Macedo de Cavaleiros–Bragança–Terra de Miranda–Alcañices–Zamora**. A revisão 2023 inclui alterações face à anterior solução por Otero de Bodas/Sanábria. Os seus pontos de referência funcionais devem ser tratados separadamente de um traçado rigorosamente digitalizado.

**As peças desenhadas disponibilizadas em PDF devem ser usadas posteriormente para adquirir os eixos georreferenciados da solução efetivamente proposta**. Até esses vértices serem extraídos, interpretados e validados, o teste abaixo é uma **confrontação de território e locais de referência versus limites dos rasters**, não prova de contenção integral, metro a metro, da poligonal projetada.

## Cobertura da fonte e dos produtos publicados

- **Fonte original Copernicus:** os quatro COG completos de `N41 W009, W008, W007 e W006` (161 565 323 bytes, todos com hashes SHA256) foram adquiridos para A1. O COG N41/W009 cobre longitude aproximadamente −9° a −8°, incluindo a zona do AFSC. Contudo, **os arquivos COG completos são fontes temporárias no runner, não os rasters regionais publicados**.
- **Primeiro recorte A1**: `[-8.65,41.08,-5.55,41.92]` (WGS84) **excluiu o ponto de referência do AFSC**, embora cobrisse os restantes locais de referência da versão 2023. O [AIP oficial NAV Portugal LPPR](https://ais.nav.pt/wp-content/uploads/AIS_Files/eAIP_Current/eAIP_Online/eAIP/LP-AD-2.LPPR-en-PT.html) fixa o aeroporto em `411408N 0084041W` = lat 41.235556°, lon **−8.678056°**, isto é, 0.028056° ou aprox. 2,34 km a oeste da fronteira antiga −8.65°.
- **Recorte A1 alargado e definitivo para esta proposta**: `[-8.75,41.08,-5.55,41.92]` WGS84, 1 segundo de arco, **11 520 × 3 024 = 34 836 480 píxeis de superfície válidos e 0 NoData**. O ponto oficial do aeroporto encontra-se estritamente no interior, com margem de aprox. 6 km para oeste. A [execução correta #41198485197](https://github.com/r-sousa/mobilidade-public-sources/actions/runs/41198485197) completou os dois trabalhos sem falhas. A [Release oficial corrigida](https://github.com/r-sousa/mobilidade-public-sources/releases/tag/mn-geo-rail-001-r1-airport-zamora-dsm-preacceptance-41198485197) contém o GeoTIFF de **85 193 353 bytes**, SHA256 `a708b502b2eb86236c70f2d74322e9d8e2ea1417eb24094d0e43536845407bd9`, e relatório QA hash `ae51fab9c868fcd123fd8b5b110956f28a9f196496df4c2b9489921f3c2df2a7`. Conservam-se os quatro COG oficiais em SHA256, sem redistribuição do original de 1°; o novo recorte **substitui A1** como fonte central do estudo.
- **Extensão A1b Sanábria**, já disponível em [Release separada](https://github.com/r-sousa/mobilidade-public-sources/releases/tag/mn-geo-rail-001-a1b-sanabria-north-DSM-preacceptance-41197841639): `[-7,41.92,-5.55,42.30]`, mais **7 140 960 píxeis válidos**; relevante para a variante **anterior/setentrional**, **não indispensável** apenas para confrontar os locais de referência da revisão por Terra de Miranda. A1b e A1 têm áreas interiores não sobrepostas e partilham fronteira geográfica em 41.92°N. As diferenças de valores nas linhas adjacentes e a semântica de cada raster continuam a merecer controlo específico.

| Elemento da solução Vale d’Ouro 2023 | Recorte A1 antigo | Recorte A1 AFSC alargado |
| --- | --- | --- |
| AFSC (ponto de referência oficial LPPR) | **Fora** | **Dentro** |
| Paços de Ferreira, Amarante e Vila Real (zonas urbanas) | Dentro | Dentro |
| Alijó/Murça, Mirandela e Podence/Macedo (zonas urbanas) | Dentro | Dentro |
| Bragança e Terra de Miranda (zonas urbanas) | Dentro | Dentro |
| Alcañices e Zamora (zonas urbanas) | Dentro | Dentro |
| **Eixo geometrizado das plantas Lote A–D** | **Não vetorizado / não confrontado** | **Não vetorizado / não confrontado** |

## Distinções determinantes para a aquisição fina

1. O raster A1/A1b é **Copernicus GLO-30 MDS**, com edifícios e vegetação, e não DGT/IGN **MDT de solo nu**. A cobertura de pontos do eixo não autoriza leituras diretas de perfil ou rampas ferroviárias.
2. As **13 quadrículas de MDT2m DGT** verificadas são apenas uma pequena amostra em Mirandela, **12+1 km² desconexos**, não representam continuidade de MDT sobre o eixo Vale d’Ouro. Os ensaios WCS IGN são locais e também não cobrem o eixo integral.
3. O recorte corrigido remove a lacuna do aeroporto mas **não substitui o confronto rigoroso com o eixo desenhado**. A próxima ação deve ser extrair de **planta e perfis de cada lote** a poligonal geográfica (ou obter ficheiro CAD/GIS original junto do promotor), fazer a interseção integral com A1/A1b e desenhar buffers de aquisição MDT 2m/5m por troço e engenharia potencialmente constrangida.
4. **Não se assume que a proposta externa foi adotada por entidades públicas, nem que o seu traçado é ótimo ou a única alternativa**. Deve ser tratada como cenário de referência formalmente descrito, confrontável com variantes adicionais.

**Estado:** base regional de superfície 30m já cobre todos os locais de referência identificados na proposta revista Vale d’Ouro de 2023; prova de **cobertura integral da geometria concreta** e de **MDT bare-earth** continua pendente de vetorizar o eixo e descarregar MDT ao longo dele.
