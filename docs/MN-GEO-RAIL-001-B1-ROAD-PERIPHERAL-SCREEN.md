# MN-GEO-RAIL-001 — B1: vias existentes e relevo, Vila Real e Bragança obrigatórias

**31/10/2026 — análise territorial de triagem, não decisão de traçado ou localização de estações**

A rede rodoviária de referência é a **A4/IP4 Vila Real–Bragança–Quintanilha** [identificada pela Infraestruturas de Portugal](https://infraestruturasdeportugal.pt/pt-pt/subconcessoes). **A4 não é linha férrea, nem plataforma de implantação**. A necessidade de túnel rodoviário no Marão ilustra obstáculos físicos; não se transferem os declives nem os raios rodoviários para o projeto ferroviário.

Por decisão do promotor, **Vila Real e Bragança são mercados de serviço obrigatórios**, mas o eixo ferroviário pode aproximar-se por áreas periféricas, sujeitas a avaliação de **tempo real de acesso por estradas locais, cobertura de procura, intermodalidade, topografia do solo nu e engenharia ferroviária**. **Sanábria excluída.**

## Aquisição real da rede viária e sua leitura

A [execução B1 #41200362181](https://github.com/r-sousa/mobilidade-public-sources/actions/runs/41200362181), bem-sucedida, obteve 2 801 geometrias atuais de vias rodoviárias com as classes OSM `motorway`, `motorway_link`, `trunk`, `primary` e `secondary`, incluindo ligações/ramais, em duas áreas limitadas, Vila Real e Bragança. Os valores de origem foram reconstituídos com o serviço Overpass em 31/10/2026 e o SHA256 dos documentos fonte é preservado por cada cidade. Fonte OSM/Overpass é **secundária e colaborativa**, ao abrigo da [ODbL com atribuição aos contribuidores](https://www.openstreetmap.org/copyright); a validação institucional das categorias/entroncamentos depende de confirmação IP/municípios.

O script reabriu também o **raster GLO30 publicado com cobertura do AFSC**, SHA256 `a708b502b2eb86236c70f2d74322e9d8e2ea1417eb24094d0e43536845407bd9`, e mediu o relevo superficial robusto `P95-P05` em **222 setores periféricos de 2×2 km** ao redor dos dois nós obrigatórios. **96 setores** responderam aos limiares exploratórios estabelecidos: centro 2–12 km da área urbana, até 1,2 km por distância retilínea de via principal local e até 4 km de autoestrada/trunk (`Vila Real=65, Bragança=31`). **Estes limites não são critérios de projeto ou tempos de acesso por itinerário rodoviário.**

O relatório e a geometria digital são preservados na [Release B1 de pré-aceitação](https://github.com/r-sousa/mobilidade-public-sources/releases/tag/mn-geo-rail-001-b1-a4-mandatory-city-roads-source-preacceptance-41200362181), para ulterior aperfeiçoamento por modelos de **rede viária navegável** e **terreno bare-earth 2m DGT**.

## Informação topográfica comparável, mas não conclusiva

No subconjunto exploratório filtrado das duas cidades, a amplitude robusta P95–P05 do MDS varia. Exemplos com baixo relevo superficial medido e proximidade às vias cartografadas (os identificadores são **células de pesquisa**, não estações propostas):
- Vila Real `E40000 N184000`, cerca de 9,2 km geodésicos da referência urbana, amplitude robusta de superfície **68,4 m**, ~145 m da via local principal e 1,01 km da autoestrada/trunk;
- Vila Real `E36000 N178000`, cerca de 5,0 km, **80,4 m**, 15 m/45 m de distância geométrica a classes de vias cartografadas;
- Bragança `E110000 N234000`, cerca de 4,7 km, **63,0 m**, 803 m/334 m das classes de vias local principal/autoestrada;
- Bragança `E110000 N236000`, cerca de 3,6 km, **84,1 m**, 1042 m/97 m.

Números calculados a partir de raster **de superfície**, não MDT terrestre. Em particular, **proximidade à autoestrada não significa existência de nó de saída nem possibilidade legal/física de acesso à estação**. A direção e a amplitude do relevo entre setores, vales e travessias exigem modelo de vias e MDT 2m detalhados, sem determinar já preferências ou excluídos.

## Próximas tarefas de aquisição

1. **Confrontar todos os setores periféricos com quadriculagem real DGT MDT2m** (do catálogo fonte existente, não repetir pesquisa genérica). Selecionar grupos alternativos de quadrículas por cidade/posição e verificar os setores não inventariados, especialmente aproximações de leste.
2. **Só então adquirir rasters MDT2m**, em pequenos conjuntos contíguos e com controlo de bytes, pelo GitHub Actions em `main` protegido com credenciais privadas do environment `dgt-cdd`.
3. Completar rede navegável para avaliar **minutos efetivos** de acesso, não distâncias retilíneas a vias.
4. Comparar **hipóteses de corredor ferroviário** com velocidades/raios/rampas e obras de arte plausíveis, não apenas trajetos por cidades ou por autoestradas.

**Não incluir Sanábria nas alternativas ativas.** Nenhuma estação foi selecionada; manter Fxx/Site e engenharia ferroviária fora da pré-aceitação.
