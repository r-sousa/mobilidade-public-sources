# MN-GEO-RAIL-001 G39 — Série longitudinal real de solo nu, IGN MDT25 perto de Zamora

## Resultado auditado em 01-11-2026

A primeira aquisição por blocos contíguos de fontes originais do IGN/CNIG obteve **13/13 respostas válidas**, cobrindo 13 referências sucessivas a intervalos de 500m ao longo dos **últimos 6km da linha de grelha de investigação G10 P2-2-1** na região de Zamora.

Cada uma das 13 requisições WCS GetCoverage foi feita sobre um envelope original de 1km² em ETRS89 / UTM 30N (EPSG:25830), cobertura **Elevacion25830_25** de solo nu, malha 25m. Os bytes GeoTIFF são preservados num ZIP; cada peça foi submetida a teste de assinatura, georreferenciação, 25m, cota finita, extensão e checksum SHA256 e extração do píxel na coordenada pretendida. As respostas originais WCS são reproduzíveis com código público, sem transação manual nem novas transferências DGT.

| Medida | Resultado |
|---|---:|
| Pontos de referência da grelha do corredor | 13 |
| Pontos com raster original validado | **13/13** |
| Passo de amostragem | **500 m** |
| Comprimento exploratório | **6 km** |
| Cota mínima amostrada | **636 m** |
| Cota máxima amostrada | **713 m** |
| Intervalos com gradiente *do solo* superior a 18‰ em módulo | **7 de 12** |
| Falhas de fonte / valores interpolados | **0** |
| Rasante de linha ferroviária comprovada | **NÃO** |
| Custo, túnel, viaduto e tempo comercial | **NÃO avaliados** |

A linha de referência é um encadeamento de centros de células da grelha G10 de 2km, não uma ferrovia com retas de projeto, curvas de transição, raios, superelevação, rampa máxima imposta e localização efetiva de estações. O gradiente entre dois pontos do **terreno** não representa a rampa ferroviária necessária ou suficiente; uma alteração local de eixo, túnel, viaduto ou terraplenagem pode produzir rasantes substancialmente diferentes.

## Programa a executar após a verificação do método

1. Ampliar estes pedidos por blocos a **faixas ferroviárias efetivamente delimitadas** em três grupos representativos da shortlist de pesquisa: G10 competitiva, G30 evitamento Natura superficial e G30 hipótese subterrânea, respeitando limites de consulta WCS e aproveitando a superposição de blocos.
2. Cobrir os lados português e espanhol com dados **de solo nu** e controlo de sistemas de referência altimétrica antes de juntar perfis longitudinais. Evitar assumir que DGT MDT 10m está pronto a descarregar; utilizar os 84 ficheiros originais DGT2m já preservados e apenas os novos faltantes em faixas de engenharia realmente escolhidas.
3. Ligar o estudo às **sete posições DGT2m locais de estação** anteriormente avaliadas (G23–G27) nos nós obrigatórios Vila Real/Bragança e preservar as 30 alternativas G10/G30 lado a lado para qualidade de serviço.
4. Delimitar fontes LNEG de geologia, hidrogeologia, falhas e sondagens, com especial atenção ao Marão–Alvão; os efeitos Natura 2000, águas, portais e poços de túnel exigem estudo e avaliação apropriada. PIC continua a exigir fonte oficial identificada.
5. Só depois criar geometrias 3D ferroviárias parametrizadas, estimativas de estruturas, custos por intervalos e tempos de marcha, incluindo velocidades de 160/200/250km/h por troço.

Os ficheiros G39 constituem **material de pré-viabilidade com fonte original observada**, não projeto ferroviário, licença ambiental ou avaliação custo-benefício. Fxx/Site não autorizados.

Fonte: [serviço IGN/CNIG MDT WCS](https://servicios.idee.es/wcs-inspire/mdt) e [catálogo CNIG MDT25](https://centrodedescargas.cnig.es/CentroDescargas/mdt25-segunda-cobertura).
