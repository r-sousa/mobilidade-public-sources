# G41 — Fontes LNEG oficiais para geologia, hidrogeologia e sondagens no Marão–Alvão

## Diagnóstico de fonte em 1 de novembro de 2026

Foram verificados **quatro serviços oficiais WFS do LNEG** por pedidos GetCapabilities de origem; todos devolveram XML válido. A auditoria de consultas espaciais GetFeature limitadas a cinco objetos em dois retângulos Marão–Alvão **ainda não demonstrou a existência de feições vetoriais obtidas para essas áreas**. Não se deve interpretar um resultado vazio como ausência de rocha, aquíferos, falhas ou sondagens.

| Fonte | Endpoint WFS oficial | Tipos de objeto anunciados | Amostra vetorial local validada |
|---|---|---:|---|
| Geologia harmonizada 1:50 000 | LNEG CGP50k INSPIRE WFS | 5 | Não |
| Geologia harmonizada 1:200 000 | LNEG CGP200k INSPIRE WFS | 4 | Não |
| Hidrogeologia 1:200 000 vetorial | LNEG CHP200k_vetor WFS | 20 | Não |
| SONDABASE geológica | LNEG Sondabase WFS | 1 | Não |

A auditoria demonstrou que os serviços ESRI INSPIRE podem devolver **GML XML nativo**, pelo que solicitar obrigatoriamente GeoJSON gera erros HTTP 400 ou XML de exceção. Ao usar GetFeature no formato original, os pedidos confinados às áreas Marão–Alvão regressaram com coleções de zero membros, pelo que se registou **cobertura local não comprovada**, sem ausência de perigos ou condicionantes.

### Metadados primários e limites de cobertura

- [Carta geológica harmonizada 1:50 000](https://sig.lneg.pt/metadados/catalog/search/resource/details.page?uuid=23ffa8e0-5e40-4479-bb19-671ac85dca7e). O dataset inclui apenas 30 folhas harmonizadas; nos territórios do Norte constam Vila Real, Mirandela e Vila Pouca de Aguiar, mas isto não equivale a cobertura total dos troços Marão–Alvão.
- [Carta geológica harmonizada 1:200 000](https://sig.lneg.pt/metadados/catalog/search/resource/details.page?uuid=b2e7fda4-38a7-4d3e-bc35-f0c5050e5578). Cobertura espacial e edições devem ser confirmadas por folha; uma escala 1:200k não identifica descontinuidades geotécnicas locais.
- [Hidrogeologia vetorial 1:200 000](https://sig.lneg.pt/metadados/catalog/search/resource/details.page?uuid=9bb77a39-6320-4e1d-a199-aa201f473c13). Metadados oficiais indicam serviço WFS, mas a série 1:200k compreende folhas com datas e cobertura distintas.
- [SONDABASE](https://sig.lneg.pt/metadados/catalog/search/resource/details.page?uuid=25fc9f7335f34d9a80b5bb58de34d80a). Sondagens disponíveis podem ter objetivos de exploração, recursos, estratigrafia e outros; não substituem investigação geotécnica do corredor.

### Próximos passos de aquisição, sem repetir os trabalhos anteriores

1. Confirmar as **folhas geológicas realmente publicadas** que cobrem os trechos de interesse e obter mapas georreferenciados originais quando o serviço vetorial não devolver feições na área.
2. Consultar a OGC API do LNEG e, quando necessário, as cartas raster 1:50k e o mapa geológico do Norte 1:200k para identificar contactos litológicos, lineamentos e zonas com necessidade de levantamento especializado.
3. Retomar os **sete sítios DGT2m de estação** já avaliados e os setores de túnel/portais apenas depois de traçar ligações ferroviárias horizontal e verticalmente plausíveis.
4. Não converter ausência de registo SONDABASE em presunção de maciço favorável, aquífero inexistente ou permeabilidade baixa.
5. Conservar as **30 alternativas G10+G30** em comparação, e o resultado G40 de 27 rasteres originais para 36 amostras como parte da base de terreno espanhol.

Natura 2000 e PIC permanecem condicionantes maiores. **G41 não demonstrou geologia específica de um traçado, licença ou viabilidade de túnel.** Sem aquisição de quadrículas DGT2m adicionais, Fxx ou Site.
