# MN-GEO-RAIL-001 — W3: persistência dos GeoTIFF obtidos diretamente pelo WCS IGN/CNIG em Zamora

**31/10/2026 — fonte original de resposta pública WCS, em pré-aceitação**

## Fonte, licença e prova de persistência

A execução [#41194194127](https://github.com/r-sousa/mobilidade-public-sources/actions/runs/41194194127) concluiu os dois trabalhos com sucesso: (1) dois pedidos limitados ao serviço público WCS IGN/CNIG em `Elevacion25830_5` e `Elevacion25830_25`, com inspeção dos GeoTIFF; (2) **verificação independente dos dois hashes, das dimensões, do CRS horizontal, das resoluções, das máscaras e dos valores, antes da publicação em Release separada**. Nenhum identificador privado DGT é exigido.

A [Release permanente e atribuída ao IGN/CNIG](https://github.com/r-sousa/mobilidade-public-sources/releases/tag/mn-geo-rail-001-cnig-wcs-zamora-1km2-preacceptance-41194194127) contém os dois GeoTIFF exatos devolvidos pelo WCS e o QA de 2 759 bytes. O serviço está identificado como [CC BY 4.0 no catálogo oficial español de dados públicos](https://datos.gob.es/es/catalogo/e0dat0002-wcs-de-modelos-digitales-del-terreno-de-espana1).

**Distinção importante:** os ficheiros foram devolvidos pelo WCS, não são as folhas de produto original LiDAR/MDT25/MDT05 arquivadas pelo produtor. Cobrem **a mesma área de 1 km²** (Zamora), em duas resoluções — não são 2 km² e muito menos uma cobertura contínua transfronteiriça.

| Propriedade | WCS 5 m | WCS 25 m |
| --- | ---: | ---: |
| Área única comum | 1 km² | 1 km² |
| Bbox ETRS89/UTM30N, EPSG:25830 | [270500,4597800,271500,4598800] | Igual |
| Dimensões | 200×200 | 40×40 |
| Valores válidos | 40 000 | 1 600 |
| Células mascaradas | 0 | 0 |
| Dimensão original de resposta | 80 536 bytes | 3 656 bytes |
| SHA256 | `b3ddf00ccbbfbafe2e46e21769a4be6076a4df1e8d5de186e92eb429862a99db` | `1983cd9f53ed8f3e9ade85c7316cd6a6dd94cbef2f944a1ef8fb7ed109471dd4` |
| Tipo de dados | `int16` | `int16` |
| Cotas amostradas | 621–657 | 621–657 |
| CRS vertical explícito no GeoTIFF | Não | Não |

A ausência de `VERTCRS`/`VERT_CS` no cabeçalho **não prova que as alturas são incompatíveis**, mas impede deduzir autonomamente o datum vertical deste TIFF. A identificação horizontal `EPSG:25830` não especifica o sistema vertical. A identificação do referencial altimétrico e a comprovação da conversão PT–ES continuam pendentes.

## Comportamento entre resoluções — não confundir com precisão vertical

Foi executado um ensaio independente de leitura dos ficheiros binários preservados e reconstrução da correspondência espacial: cada célula 25 m é confrontada com a **média aritmética dos 25 píxeis de 5 m contidos na mesma área**, sem reamostragem automática nem deslocação dos pixels. O código reprodutível está em `tools/geo_rail_es_wcs_crossres_qa.py` e a [evidência quantitativa](../reports/mn-geo-rail-001/es-cnig-zamora-WCS-5m-25m-resolution-QA.json) preserva hashes dos ficheiros.

Ambos os ficheiros usam **valores inteiros de altitude** (`int16`, 37 níveis de 621 a 657 m, com incrementos de 1 m no produto WCS devolvido). Comparando os 1 600 pares de áreas de 25 m, a diferença entre a cota MDT25 e a média do MDT5 tem **mediana 0 m, diferença absoluta média 0,513 m, RMS de diferença 1,020 m, amplitude −5,04 a +10,80 m**, e percentil 95 da diferença absoluta 2,04 m.

Estes números **não são RMSE de precisão vertical**, nem erros face a marcos geodésicos. São diferenças entre dois produtos/resoluções distintos, com possíveis diferenças de generalização e processamento. O tipo de dados inteiro na resposta WCS **não permite concluir precisão vertical de 1 m**, mas revela a granularidade dos valores transmitidos neste ensaio.

**Gates:** G1/G3/G5 continuam abertos, G2/G4 parciais. Nenhum novo Fxx, Site, perfil longitudinal ferroviário ou evidência de continuidade Porto–Zamora autorizados.
