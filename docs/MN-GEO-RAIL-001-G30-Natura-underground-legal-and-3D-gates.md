# G30 — Natura 2000, alternativas subterrâneas e portões jurídicos (01-11-2026)

## Decisão metodológica

As interseções de linhas de estudo em grelha 2 km G10/G28 com polígonos Natura 2000 não são automaticamente superfícies de obra, impactes ecológicos nem provas de ilicitude. A auditoria deve manter **duas saídas separadas**:

- **Portão jurídico (não negociável):** determinar se o plano/projeto pode produzir efeitos significativos, individualmente ou cumulativamente, sobre os objetivos de conservação. Proceder à avaliação apropriada quando exigível, incluindo efeitos indiretos de obras fora do perímetro. Sem demonstração suficiente, **estado UNKNOWN / ASSESSMENT_REQUIRED**, nunca «isento porque subterrâneo».
- **Hipótese física de atravessamento:** distinguir superfície, falso túnel sem perfil, túnel com portais/poços/estaleiro dentro do sítio e túnel profundo com portais fora. Este último pode reduzir impactes diretos de ocupação/fragmentação, mas dependerá de hidrogeologia, geotecnia, águas, acessos de obra, vibração e perturbação.

O atravessamento subterrâneo é **hipótese de projeto**; não é medida compensatória, autorização, exceção automática nem desclassificação Natura. No *screening* de significância, não utilizar medidas de mitigação para suprimir indevidamente a necessidade de avaliação apropriada (TJUE C-323/17).

## Hierarquia de verificação jurídica (fontes primárias)

1. Diretiva Habitats 92/43/CEE, art. 6.º, n.os 3 e 4: avaliação dos objetivos de conservação e integridade; eventual derrogação excecional apenas mediante requisitos estritos (alternativas, interesse público imperativo e compensação), reforçados para habitats/espécies prioritários. Guia da Comissão Europeia de 2021: https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=oj%3AJOC_2021_437_R
2. Portugal: Decreto-Lei n.º 140/99, art. 10.º, na redação vigente. Procedimento AIA quando legalmente aplicável, sem assumir equivalência simplificadora entre AIA e avaliação apropriada.
3. **Alvão/Marão PTCON0003**: Decreto-Lei n.º 28/2025, de 20 de março, designadamente arts. 3.º, 4.º e 5.º — https://diariodarepublica.pt/dr/detalhe/decreto-lei/28-2025-911648874 ; Portaria n.º 135/2025/1, de 28 de março, que aprova o plano de gestão — https://diariodarepublica.pt/dr/detalhe/portaria/135-2025-912820664. O regime distingue atos proibidos/condicionados, mas não fornece autorização por profundidade de túnel.
4. Espanha: confirmar diploma e instrumentos de gestão dos sítios efetivamente afetados; não transferir o regime específico do Alvão/Marão para território espanhol ou outros sítios portugueses.
5. **PIC:** sigla e fonte geográfica oficial não identificadas nos dados auditados; é restrição maior **UNKNOWN**. Nenhuma alternativa será qualificada como ambientalmente apta antes de resolver esta lacuna, e não inventar o significado de PIC.

## Gate de engenharia geoespacial para G31+

| Campo | Evidência mínima para mudar de UNKNOWN | Situação G30 |
|---|---|---|
| Extensão exata em túnel | eixo 3D, cobertura efetiva, altimetria do terreno em solo nu | UNKNOWN |
| Perfil gradiente para 160 / 200 / 250 km/h | curvas, rampas, bitola, gabaritos, estação e transições | UNKNOWN |
| Intervenções à superfície | geometrias de portais, poços, galerias de emergência, estaleiros, terras e acessos | UNKNOWN |
| Efeitos hidrogeológicos | massas de água, nascentes, turfeiras, zonas húmidas, permeabilidade, modelo de fluxos, descarga e drenagem | UNKNOWN |
| Integridade dos habitats e espécies | objetivos de conservação por sítio, mapa de habitats, época de obras, cumulativos | UNKNOWN |
| Custos | volumes por túnel/viaduto, riscos geotécnicos e de drenagem, O&M, contingências, faseamento | UNKNOWN |
| Serviço e intermodalidade | estações ferroviárias funcionais, rede viária e transportes, BGRI2021/OSRM e critérios sociais | NÃO VERIFICADO |
| Solo e ordenamento | COS2025 já existente, REN/RAN/PDM/SRUP e regime legal de cada polígono | PARCIAL |

## Regras de seleção das alternativas

- Manter **Vila Real** e **Bragança** obrigatórias, **Sanábria excluída**; comparar oportunidades de serviço a **Guimarães, Amarante, Mirandela e Macedo de Cavaleiros** sem exigir estação no centro urbano.
- Explorar famílias de **evitamento superficial** e de **passagem subterrânea** em paralelo. Uma alternativa longa que evita a ZEC pode não ser melhor do que túnel profundo de reduzido impacte, mas nenhuma pode obter «penalização jurídica zero» nesta fase.
- Preservar G10, G28 e G29 como **fontes de investigação** imutáveis. G30 produz novas sequências geográficas e um cenário hipotético de túnel; não converte os km de interseção Natura em km de túnel e não atribui custos, capacidade ou tempos comerciais.
- Não encomendar novas quadrículas DGT 2 m antes de selecionar faixas com potencial geométrico. Reutilizar DSM Copernicus, 84 quadrículas originais 1 km² DGT já adquiridas, BGRI2021, COS2025 e OSRM quando forem usados na validação técnica e social posterior.
- Não publicar linhas G30 como projeto, reserva territorial, traçado viável ou informação Fxx/Site.

## Entregas verificáveis G30

A rotina de execução deve produzir: três cadeias geográficas novas em GeoJSON; respetivos comprimentos exploratórios e interseções com os polígonos G28; um mapa com sobreposição ICNF+MITECO; hashes de fonte; riscos remanescentes; e ensaios sintéticos independentes. Em falha de fontes, de código, de diferenciação ou dos testes, **não publicar resultados como validados**.
