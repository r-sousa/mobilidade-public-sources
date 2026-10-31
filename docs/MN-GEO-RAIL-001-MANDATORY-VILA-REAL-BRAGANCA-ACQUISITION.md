# MN-GEO-RAIL-001 — Plano de aquisição B1/C1 revisto: Vila Real e Bragança obrigatórias

**31 de outubro de 2026. Versão ativa após decisão do promotor. A aquisição do eixo Sanábria deixa de ser priorizada.**

## 1. Decisão territorial vinculativa

A avaliação de conectividade ferroviária considera **Vila Real e Bragança como dois nós de serviço obrigatórios**, não apenas cidades opcionais. O traçado **não tem de atravessar os respetivos centros**: são admissíveis áreas periféricas de estação, desde que a acessibilidade por estradas urbanas/regionais possa ser comprovada e que os tempos totais de acesso e de viagem sejam comparados com as alternativas. É inadequado desenhar um único corredor por segmentos de reta entre os centros das cidades.

O âmbito operativo revisto é **área do Porto → área de Vila Real → área de Bragança → fronteira Norte–Espanha → Zamora**. A eventual ligação por Sanábria é **excluída do processo de seleção e das novas aquisições**. A Release pré-existente A1b mantém-se apenas por rastreabilidade histórica: a existência de dados adquiridos **não** confere relevância à alternativa excluída.

## 2. Rede viária como hipótese de organização espacial, não como eixo rígido

A [Infraestruturas de Portugal](https://infraestruturasdeportugal.pt/pt-pt/subconcessoes) identifica a **A4/IP4** Vila Real–Quintanilha, com ligação à fronteira espanhola. A [documentação IP sobre o Túnel do Marão](https://servicos.infraestruturasdeportugal.pt/a-descobrir/obras-de-arte/tunel-do-marao-ips) evidencia que a travessia Amarante–Vila Real exigiu cerca de 6 km de túnel rodoviário e extensas obras de arte. Em Espanha, o [Congreso de los Diputados, 29/10/2024](https://www.congreso.es/public_oficiales/L15/CONG/BOCG/D/BOCG-15-D-225.PDF) identifica o itinerário da **N-122**: Trabazos, Alcañices, Muelas del Pan e Zamora, entre outros. Estas são fontes documentais para construir **eixos rodoviários de referência**, e não provas de que uma ferrovia poderia acompanhar, nos mesmos declives ou raios, qualquer uma destas plataformas.

Separar três componentes do valor territorial das alternativas: **acesso aos nós obrigatórios (Vila Real/Bragança)**, **custo físico de vencer as barreiras topográficas** e **continuidade/função transfronteiriça**. A rede de autoestradas pode aproximar o serviço aos nós de procura, mas pode também usar rampas, curvas e viadutos incompatíveis com a via férrea; o seu eixo deve servir para orientar setores a testar, nunca para determinar a poligonal da ferrovia.

## 3. Organização em módulos físicos e geográficos

| Módulo | Objetivo | Necessidade de MDT de terreno | Restrição |
| --- | --- | --- | --- |
| P1 | Área Porto–Amarante–travessia do Marão | Blocos DGT 2m alternativos de passagem pelo relevo, lado ocidental, travessia e lado oriental; cruzar com A4 e IP4 | Não reproduzir o eixo/túnel rodoviário sem análise independente |
| P2 | **Área de serviço obrigatória de Vila Real** | Várias áreas candidatas **periféricas**, com gradiente/topografia e acessos rodoviários comparados | Estação no centro não obrigatória; acesso por via pública deve ser comprovado |
| P3 | Vila Real–Mirandela–Macedo–Bragança | Faixas de pesquisa alternativas ao longo e de ambos os lados do eixo rodoviário; aquisição por setores contíguos, não por pontos isolados | Cidades intermédias opcionais, apenas se melhorarem procura/custos/acessibilidade |
| P4 | **Área de serviço obrigatória de Bragança** | Vários setores periféricos e rotas possíveis de aproximação/saída com análise de acessos A4/IP4 | Bragança nunca pode ser contornada sem serviço funcional comprovado |
| P5 | Bragança–Quintanilha–Alcañices–Zamora | DGT 2m em território PT; MDT5m CNIG em Espanha, com pormenor acrescido nas travessias | N-122 referencia serviços/ligação rodoviária, não imposição de corredor ferroviário |

**Critérios de comparação futura:** distância de acesso por rede viária até estação, tempo de acesso, captação de população, efeitos de relevo (picos, cotas, linhas de água, desníveis), extensões em túnel/viaduto de hipóteses ferroviárias sujeitas a parâmetros de projeto, distância e tempo de viagem ferroviária, custos e impacto ambiental. Não estimar custos ou rampas de via férrea a partir do MDS ou apenas da proximidade à A4.

## 4. Aquisição C1 espanhola executada

A [execução C1 #41199556336](https://github.com/r-sousa/mobilidade-public-sources/actions/runs/41199556336) adquiriu **24 respostas GeoTIFF reais do WCS IGN/CNIG MDT05**, organizadas em **dois blocos de 8 × 6 km** (`Elevacion25830_5`, EPSG25830):
- **Alcañices**: `[218000,4619000,226000,4625000]` m em EPSG:25830, 12 ficheiros 2×2 km e um mosaico 1 600 × 1 200 células;
- **Muelas del Pan**: `[248000,4597000,256000,4603000]` m, também 12 ficheiros 2×2 km e um mosaico 1 600 × 1 200 células.

**Total: 96 km² distintos, 3 840 000 píxeis MDT de solo nu a 5m efetivamente válidos, 0 NoData, e 24/24 conjuntos de valores da fonte reconstituídos exatamente nos mosaicos.** O serviço espanhol é [licenciado CC BY 4.0](https://datos.gob.es/es/catalogo/e0dat0002-wcs-de-modelos-digitales-del-terreno-de-espana1), com atribuição IGN/CNIG. A [Release C1](https://github.com/r-sousa/mobilidade-public-sources/releases/tag/mn-geo-rail-001-c1-cnig-n122-96km2-ground-preacceptance-41199556336) inclui os 24 originais *de resposta WCS* (não folhas originais do arquivo COG), dois GeoTIFF de mosaico sem alteração de valores e o recibo com hashes de todas as fontes; os dois trabalhos GitHub Actions passaram.

Esta aquisição **não** define dois pontos obrigatórios de passagem, uma solução ferroviária, um datum vertical comprovado na resposta ou cobertura de solo nu contínua em todo o percurso até Zamora. São **setores de sondagem de detalhe** para comparar opções na zona rodoviária N-122.

## 5. Ordem concreta das próximas aquisições B1 portuguesas

A seleção deve ser derivada da interseção **(a) áreas periféricas de serviço obrigatório**, **(b) barreiras do relevo do MDS Copernicus de 1 segundo de arco**, **(c) acesso medido por rede viária/estradas locais** e **(d) quadrículas efetivas de catálogo DGT MDT2m**, com validação de licença e orçamento de bytes. Priorizar:
- **B1.1 — Vila Real:** várias áreas candidatas de implantação/estação periférica e acessibilidade; apenas depois selecionar polígonos de blocos contíguos 2m e IDs originais DGT.
- **B1.2 — Bragança:** o mesmo procedimento obrigatório, incluindo aproximações de oeste e este.
- **B1.3 — Marão / A4:** duas ou mais passagens/relevos alternativos, sem importar o túnel e declive da estrada.
- **B1.4 — Figueira de Castelo Rodrigo? Não.** Limitar esta missão à ligação Vila Real–Bragança–Zamora: iniciar ligação oriental por Quintanilha e/ou alternativas próximas tecnicamente viáveis. Evitar a expansão de âmbito para corredores não escolhidos.

**Segurança DGT:** a aquisição de originais sob credenciais registadas deve continuar exclusiva de jobs `workflow_dispatch` protegidos em `main` com environment `dgt-cdd`; **não colocar credenciais num workflow de push, branch de trabalho ou manifestos públicos**. A seleção prévia de IDs e áreas pode ser pública; a etapa autenticada permanece protegida. Não se alterarão secrets/tokens.

**Estado:** C1 tem novo MDT físico preservado; B1 ainda requer seleção verificada de setores e aquisição autenticada. Manter Fxx/Site fora do âmbito até haver cobertura de solo nu e conformidade horizontal/vertical adequadas.
