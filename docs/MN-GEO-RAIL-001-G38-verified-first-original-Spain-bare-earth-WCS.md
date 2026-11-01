# MN-GEO-RAIL-001 G38 — Primeiro raster espanhol de solo nu comprovadamente adquirido

## Resultado e proveniência

A execução G38 GitHub Actions **41305650100** (01-11-2026) obteve um **GeoTIFF real** de solo nu no serviço oficial IGN/CNIG WCS [MDT](https://servicios.idee.es/wcs-inspire/mdt). O serviço anunciou a cobertura **Elevacion25830_25**. A tentativa inicial GetCoverage com eixos E,N deu erro 404, mas o pedido correto com **X,Y** obteve efetivamente dados, validados com rasterio.

| Propriedade | Valor observado |
|---|---|
| Área do ensaio | 1 km × 1 km perto de Zamora, amostra de fonte, não estação |
| Matriz e validade | 40 × 40 células, **1 600 píxeis válidos** |
| Referência e resolução | **EPSG:25830**, ETRS89 / UTM 30N, **25 m** |
| Envelope nativo | X=270311–271311; Y=4597738,2–4598738,2 m |
| Altimetria amostrada | **621–654 m**; mediana **638 m** |
| QA obrigatória | GeoTIFF, píxeis finitos, cobertura do ponto solicitado, EPSG e resolução, hash original |
| Geometria de ferrovia ou estação | **NÃO demonstrada** |

A release publica o **raster original**, com SHA256 e comprovativo de origem, não uma simulação de perfil. A amostra demonstra que o serviço pode fornecer terreno espanhol real em operações futuras limitadas e repetíveis.

## Reutilização e limitações

- **84 quadrículas originais DGT de 1×1 km, MDT 2m** já preservadas; não adquiridas novamente por G38.
- Os produtos LiDAR Portugal de 2 m e 50 cm são públicos através da DGT, mas a disponibilidade de uma **descarga contínua MDT10m operacional para o Norte continua por verificar**. Uma especificação cartográfica de 10m não substitui uma origem disponível.
- O catálogo LNEG respondeu HTTP 200 e referencia dados geológicos, hidrogeológicos e sondagens; **ainda não foram adquiridas geometrias WFS específicas**.
- IGN/CNIG utiliza altitudes ortométricas espanholas; o referencial altimétrico da DGT em Portugal poderá ser Cascais 1938. **Não combinar cotas sem harmonização vertical comprovada**.
- Natura 2000 e PIC continuam pendentes de análise e cartografia apropriadas; um túnel sob o Alvão/Marão exige verificar portais, poços, geologia, águas subterrâneas e habitats dependentes de água.

## G39 — Caminho para faixas e perfis ferroviários

1. Escalar a **cobertura oficial WCS de 25m validada** em pequenos blocos contíguos do lado espanhol, respeitando limites de resposta, proveniência, NoData, referência vertical, mosaico e QA. Não descarregar território irrelevante.
2. Definir 2–3 famílias representativas (G10 de bom compromisso, evitamento superficial Natura, hipótese de túnel), sem perder os **30 corredores** originais da comparação.
3. Aproveitar os sete locais históricos estudados G23–G27 de Vila Real e Bragança; testar **aproximações ferroviárias horizontais e verticais contínuas**, sem as assumir já viáveis.
4. Adquirir **poucas quadrículas DGT2m adicionais**, apenas quando o percurso 3D e os setores de maior incerteza estiverem concretamente delimitados; não executar aquisição cega de ~1780 quadrículas condicionais do G37.
5. Obter recortes oficiais LNEG (geologia 50k, hidrogeologia 200k, sondagens, falhas), testar variantes de túnel com restrições ecológicas/hidrogeológicas e só então construir intervalos de custos e tempos.

**Critério de passagem:** sem geometria de ferrovia validada e cobertura coerente de solo nu não é legítimo publicar quilómetros de túnel/viaduto, velocidades de operação, custos, análise custo-benefício ou decisão ambiental. **Sem Fxx/Site.**

Referências: [DGT LiDAR](https://www.dgterritorio.gov.pt/descarregamento-de-dados-lidar-de-portugal-continental), [CNIG MDT25](https://centrodedescargas.cnig.es/CentroDescargas/mdt25-segunda-cobertura), [LNEG](https://geoportal.lneg.pt/pt/dados_abertos/servicosdados/).
