# MN-GEO-RAIL-001 — G48: regras de inclinação por função ferroviária (substitui os pressupostos-base G42–G47)

**Estado:** protocolo de investigação e controlo de qualidade, não projeto de execução, homologação de infraestrutura, autorização ambiental ou despacho sobre o traçado.

## 1. Nova hierarquia de hipóteses

| Gradiente máximo de ensaio | Função | Estatuto na avaliação do corredor |
|---|---|---|
| **12,5‰** | Linha mista e mercadorias | **Cenário-base principal** |
| **15‰** | Linha mista e mercadorias | **Cenário normal condicionado** (tração, tonelagem e perfil da rampa) |
| 18‰ | Mercadorias F1 | **Sensibilidade excecional** conforme enquadramento específico espanhol; aprovação/justificação não presumida |
| 20‰ | Mercadorias F2–F3 | **Sensibilidade excecional** conforme enquadramento específico espanhol; aprovação/justificação não presumida |
| **25‰** | Via geral de linha de tráfego maioritário de passageiros | **Alternativa funcional distinta**; nunca inferir mercadorias na secção onde se projeta este valor |

Os valores acima seguem as categorias e condições do **quadro 4.1.4.1.3 da IFI espanhola (Orden TMA/135/2023)**. A regra **não se transplanta automaticamente para o território português**: exige verificar o enquadramento de projeto em Portugal e o perfil integral de circulação transfronteiriça. As exceções de mercadorias implicam decisões e condições adicionais — não equivalem a declive autorizado no projeto.

A **ETI INF 4.2.3.3**, na redação consolidada após o Regulamento (UE) 2023/1694, não fixa 12,5‰ como regra universal para todas as linhas mistas. Dispõe nomeadamente sobre rampas das novas linhas **P1 dedicadas a passageiros** até 35‰, sujeitas a restrições da média móvel em 10km e da extensão de rampas continuadas, e sobre vias de estação com estacionamento ou engate/desengate. Não utilizar os 35‰ de uma P1 para admitir tráfego de mercadorias.

Fontes oficiais:
- [BOE — Orden TMA/135/2023, IFI, 4.1.4.1.3](https://www.boe.es/buscar/doc.php?id=BOE-A-2023-4324).
- [EUR-Lex — ETI INF, Regulamento (UE) 1299/2014 consolidado em 2023](https://eur-lex.europa.eu/eli/reg/2014/1299/2023-09-28/eng).

## 2. Localização e função das estações: um segundo filtro independente

Não aplicar o valor de 2,5‰ a **todas** as plataformas de passageiros. O G48 ensaia, numa reta hipotética central de 800m sobre os locais de estação G47, três funções distintas:

1. **Via geral sem restrição adicional de estação**, apenas para definir referência comparativa de rasante.
2. **10‰** como referência da instrução espanhola para paragem de passageiros / P.A.T. sem estacionamento prolongado nem acoplamento/desacoplamento, que não constitui, por si, norma portuguesa validada.
3. **2,5‰** no caso em que se aplique a exigência de estacionamento prolongado ou operações regulares de engate/desengate; no caso de estacionamento, a ETI prevê disposições específicas para impedir deslocamento involuntário.

Uma estação sobre o corredor com 15‰ de via geral **não** equivale a uma plataforma com esse gradiente; e uma plataforma com 2,5‰ **não** determina que a via geral adjacente deva ter 2,5‰. As transições têm de ser estudadas com raios verticais, plataforma, comprimentos, paragem e exploração reais.

## 3. O que permanece válido nos resultados anteriores

- G10+G30: as **27 alternativas G10 + 3 G30** não são removidas nem reordenadas pelas novas normas.
- G23–G27/G35/G44: as **sete posições DGT2m de estação previamente estudadas** continuam pontos reais de referência de localização, não estações aprovadas.
- G42: a descoberta de cinco módulos e de uma só geometria inicial local por cidade é válida; os resultados 18/25‰ continuam histórico exploratório, mas não cenários-base de linha mista.
- G43: mantém-se a amostragem de **241 pontos de terreno original IGN25** em Zamora e a necessidade de usar 25m e concordâncias verticais em vez de 500m.
- G45/G46/G47: mantêm-se **630 casos** de geometria em planta, os **84 ficheiros DGT de 2m** verificados, as **18 quadrículas** que cobrem as quatro faixas centrais e as **484 cotas originais** nos perfis de 3km. Nenhuma dessas amostras, por si, determina uma rasante final.
- A G48 recalcula as **cinco rampas** para os cinco perfis com **dois tipos de condições nos extremos**. O caso espanhol é testado com raio vertical matemático sem limite adicional / 10km / 20km, e os casos de estação com três requisitos operacionais de rampa na reta de 800m, totalizando **150 problemas de otimização**. Dez resultados anteriores 18/25‰ são reconstituídos para confirmar a reprodutibilidade.

## 4. Portões seguintes para seleção real de corredores

Uma decisão comparativa entre alternativas requer: **(i)** definir por troço a função passageiros/mista e as condições do transporte de mercadorias, **(ii)** verificar as rampas contínuas de todo o itinerário e a tração/frenagem dos comboios de mercadorias, **(iii)** redesenhar o traçado horizontal/vertical com as aproximações a Vila Real e Bragança e os serviços a Guimarães, Amarante, Mirandela e Macedo de Cavaleiros, **(iv)** validar o terreno contínuo incluindo os setores ainda sem DGT2m e compatibilizar o datum Espanha/Portugal, **(v)** investigar geologia, águas, Natura 2000 e PIC a partir das fontes legais, e **(vi)** apenas então estimar túneis, viadutos, custos e tempos.

**Regra operacional:** todos os estudos de engenharia posteriores a G48 devem tratar 12,5‰ e 15‰ como **referências primárias para ferrovia mista**, 18‰ e 20‰ como **exceções condicionadas**, e 25‰ como **hipótese de passageiros** com mudança explícita da função de linha, sem permitir que a velocidade isolada de 160/200/250 km/h determine a função ferroviária.

O registo de política computacional é `tools/geo_rail_gradient_policy_G48.py`. **Sem novas aquisições de dados, nem integração de Fxx/Site nesta etapa.**
