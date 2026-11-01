# MN-GEO-RAIL-001 · G27 — triagem territorial verificável (sem viabilidade jurídica presumida)

## Questão e universo

As cinco referências originais obrigatórias de Vila Real e Bragança deram lugar, após G23–G25, a **sete posições geográficas distintas** (três Vila Real; quatro Bragança). São posições exploratórias e não projetos de estação. O G26C já recortou **246 polígonos oficiais COS2025 da DGT**, sobre sete círculos de 400 m de raio, com integridade, hashes e cobertura espacial confirmados. O G25 mede o acesso de referência por estrada aos pontos mais próximos da rede OSM (não a entrada jurídica numa estação).

## Primeira comparação — fontes já comprovadas

| Cidade | Referência EPSG:3763 (m) | Ocupação COS2025 artificializada na circunferência de 400 m | Acesso OSRM de referência (min) | REN/RAN/PDM e demais SRUP |
|---|---|---:|---:|---|
| Vila Real | 32588,50; 181000,00 | 80,49% | 3,18 | Por validar legalmente |
| Vila Real | 29588,50; 181000,00 | 14,60% | 7,37 | Por validar legalmente |
| Vila Real | 29888,50; 181250,00 | 17,94% | 6,61 | Por validar legalmente |
| Bragança | 114308,60; 239000,00 | 69,73% | 2,15 | Por validar legalmente |
| Bragança | 114029,35; 238890,38 | 91,27% | 1,94 | Por validar legalmente |
| Bragança | 113000,00; 237308,60 | 52,04% | 4,06 | Por validar legalmente |
| Bragança | 117218,20; 238781,80 | 16,89% | 5,83 | Por validar legalmente |

Os tempos referem-se à **estrada navegável nas proximidades** da referência, sem comprovar um acesso físico/legal à parcela ou a uma estação. Uma parcela mais artificializada não é necessariamente inviável, e um solo rural ou florestal não constitui um terreno livre/sem condicionantes. Os valores de cobertura artificializada são medidos em 2025 e não a disponibilidade fundiária em 2026.

## Fontes oficiais de restrições — descoberta G27A

A verificação de `GetCapabilities` dos serviços originais da **DGT/SNIT** identificou três serviços WFS oficiais operacionais:

- **REN/Norte**: `https://servicos.dgterritorio.pt/SDISNITWFSSRUP_REN_NORTE/WFService.aspx`, camada `gmgml:REN_Norte`; obteve resposta GML original.
- **RAN/Portugal**: `https://servicos.dgterritorio.pt/SDISNITWFSSRUP_RAN_PT1/WFService.aspx`, camada `gmgml:RAN`; a resposta pequena num ponto não permite afirmar a ausência de RAN noutras localizações.
- **CRUS/Continente**: `https://servicos.dgterritorio.pt/SDISNITWFSCRUS/WFService.aspx`, camada `gmgml:CRUS`; obteve resposta GML original.

**REN**: a cartografia oficial georreferenciada das delimitações municipais publicada em Diário da República prevalece em divergências relativamente à camada vetorial SNIT. A camada pode conter **exclusões** da REN; presença de uma geometria não prova incidência de restrição material e ausência de geometria não prova ausência legal.

**RAN**: o regime legal e a delimitação vigente do município, tal como publicada e depositada, exigem verificação própria; não converter classes COS de agricultura em RAN.

**CRUS**: é uma harmonização das classes dos instrumentos de planeamento, para uso territorial/estatístico, **não** peça de licenciamento ou substituto do PDM e regulamento aplicável.

## G27C — Interseções primárias SNIT efetivamente verificadas

O workflow de origem **G27C #41261770729** concluiu 21 consultas WFS da DGT (3 temas × 7 posições, 400 m), com geometria GML interpretada e 31 polígonos recortados e conservados:

| Fonte oficial SNIT | Setores com geometria original observada | Restantes respostas |
|---|---:|---|
| REN Norte (`gmgml:REN_Norte`) | **7/7** | Deve distinguir as classes **REN** e **Exclusões**; não se pode chamar interdição sem a cartografia legal |
| RAN nacional (`gmgml:RAN`) | **3/7** | **4/7** sem elementos no WFS para a janela pedida — **não** é ausência legal provada |
| CRUS nacional (`gmgml:CRUS`) | **7/7** | Respostas limitadas pelo máximo de 5 elementos, logo a cobertura **não é exaustiva** e a CRUS não define licenciamento |

Os 31 recortes positivos não equivalem a 31 restrições jurídicas. A REN pode incluir exclusões e elementos de várias tipologias; a RAN e os PDM exigem confirmação dos instrumentos/diplomas aplicáveis. O estado de cada um dos sete pontos permanece **pré-jurídico**, ainda sem decisão de elegibilidade.

## Alteração regulamentar particularmente relevante — Bragança (9 de junho de 2026)

O **Aviso n.º 14240/2026/2, de 9 de junho**, Município de Bragança, publicado no Diário da República, aprovou a **2.ª correção material da 1.ª revisão do PDM**. A correção ao artigo 62.º, n.º 7, clarifica a repartição simétrica da largura total das faixas de proteção das vias; houve também alteração cartográfica da hierarquização de segmentos da Estrada do Turismo e da antiga EN 217 junto aos acessos à A4, passando a Sistema Secundário. É informação diretamente pertinente para interfaces periféricos orientados pela A4, que requer confirmação espacial sobre a cartografia vigente.

Fonte primária: [Diário da República — Aviso n.º 14240/2026/2](https://diariodarepublica.pt/dr/detalhe/aviso/14240-2026-1130568389). **Não atribuir automaticamente a correção a um dos quatro setores sem sobreposição cartográfica da planta oficial.** Não confundir **Vila Real** com Vila Real de Santo António ao pesquisar PDM.

## Portões que ainda dependem de confirmação

1. Confrontar o mosaico das interseções WFS com as **cartas e diplomas REN/RAN publicados** e identificar expressamente exclusões, alterações e datas por município.
2. Verificar a **planta de condicionantes e de ordenamento dos PDM em vigor** em Vila Real e Bragança (incluindo alterações e suspensões); cruzar com instrumentos de ordenamento especial aplicáveis.
3. Completar domínio hídrico, cursos de água e zonas inundáveis, Rede Natura e outras áreas classificadas, património, servidões rodoviárias, aeronáuticas e de infraestruturas.
4. Confirmar cadastro e disponibilidade real de solo, traçado ferroviário contínuo nas aproximações e projeto dos acessos rodoviários; todos faltam à pré-viabilidade.

## Aquisição adicional de MDT2m

O G26B confirmou **84 quadrículas de origem DGT 1×1 km** já preservadas. São distintas da grelha de exploração de 2×2 km dos corredores. O G23B dispôs de MDT para 327/351 faixas topográficas locais exploratórias. Não adquirir mais MDT apenas por aumento da lista de posições. Mantendo *todas* as 16 orientações e antes de selecionar corredores, os défices condicionais de quadrículas DGT de 1×1 km seriam 6 (±1,5 km; meia largura 300 m), 30 (±3 km; 300 m), ou 135 (±6 km; 1000 m). Estes números são **cenários de cobertura**, não ordens de descarga ou traçados de engenharia.

**Próximo gatilho:** depois da verificação REN/RAN/PDM/SRUP e da definição de geometrias ferroviárias contínuas alternativas, pedir apenas os originais DGT de 2 m que intersetem as faixas escolhidas, retirando os 84 já existentes. A necessidade de faixas geológicas e de engenharia no restante corredor Porto/AFSC–Vila Real–Bragança–Zamora será aferida numa etapa própria.

Fontes originais: DGT [SRUP](https://www.dgterritorio.gov.pt/atividades/ordenamento/sgt/srup), [SNIT](https://www.dgterritorio.gov.pt/atividades/ordenamento/snit), [CRUS](https://www.dgterritorio.gov.pt/atividades/ordenamento/crus), G26C COS2025 e G25/G26B validados.

Vila Real e Bragança obrigatórias; Sanábria excluída. Guimarães, Amarante, Mirandela e Macedo de Cavaleiros não eliminadas, como oportunidades de serviço a verificar. Não atualizar Fxx/catálogo canónico ou Site antes da validação legal e de engenharia.
