# MN-GEO-RAIL-001 — Regra de comparação integral de corredores (G32+)

## Universo canónico

**Não substituir as 27 alternativas G10 pelas três variantes G30.** A carteira tem 30 cadeias exploratórias (27 G10 + 3 G30), todas comparadas lado a lado sob as mesmas fontes e métodos. São 90 observações para as três velocidades indicativas **160, 200 e 250 km/h**. Cada exclusão futura exige motivo geográfico, técnico ou jurídico verificável, registado antes da shortlist. Não eliminar alternativas apenas por sobreposição Natura 2000 bidimensional.

As 27 alternativas G10 são combinações de três módulos independentes com pontos obrigatórios de estudo; não são traçados ferroviários. As três variantes G30 procuram evitamento superficial Natura, uma hipótese de atravessamento subterrâneo e maior diversidade territorial; não são túneis projetados.

## Regras obrigatórias para todos os estudos posteriores

1. **30 alternativas sempre presentes** em matrizes e mapas, salvo exclusões explícitas e auditáveis. Novas alternativas adicionam-se à carteira e recebem identificador de fonte.
2. **Fontes comuns:** geometria oficial ICNF/MITECO Natura PT/ES, separando ZEC Alvão/Marão identificada oficialmente, COS2025 e os dados DGT/DSM originais já em cache. A sigla **PIC permanece por definir e cartografar** como restrição maior.
3. **Geometria e velocidades:** todos os 30 comparados com cenários 160/200/250, raio e gradiente, desvio do centro das quadrículas, solo nu onde existe, e requisitos reais de serviço a Vila Real e Bragança; Sanábria excluída e interfaces periféricos permitidos.
4. **Serviço, acessibilidade e coesão:** o mesmo método para rede rodoviária, transporte público, BGRI2021 e população/emprego; mercados Guimarães, Amarante, Mirandela e Macedo de Cavaleiros. Sem medida não significa zero — escrever UNKNOWN.
5. **Obras e custos:** não atribuir preços ou quilómetros de túnel/viaduto através da simples pressão vertical do MDS, que inclui edifícios e vegetação. Exigir projeto tridimensional, geotecnia e custos unitários documentados.
6. **Natura e hipótese de túnel:** não presumir autorização legal por passagem profunda; estudar água subterrânea, nascentes/turfeiras, portais, poços, acessos e conservação do sítio ao abrigo do artigo 6.º da Diretiva Habitats e plano de gestão específico.
7. **Quadros comparáveis:** incluir todas as 30 variantes e mesmas variáveis, com três velocidades; gráficos geográficos e quantitativos; só declarar Pareto com variáveis efetivamente observadas. Não transformar o Pareto de comprimento/relevo em recomendação de investimento.
8. **Gates de publicação:** nada de Fxx/catálogo canónico/Site antes de maturação técnico-jurídica.

## G32 — Contrato técnico de implementação

A rotina Python G32 produz matriz **30×3=90**, CSV legível por folha de cálculo, JSON auditável, tabela integral a 200 km/h, figura comum para as três velocidades e mapa das 30 geometrias. Testes impedem omitir qualquer G10/G30 ou afirmar isenção Natura por hipótese de túnel. Geometrias G10 e G30, polígonos G28 e MDS GLO30 original são recuperados das releases GitHub preservadas, com SHA256 do original GLO30 e do recorte G28 verificáveis; sem novas descargas DGT.

Métodos herdados G31: raios de triagem 1500/2400/3700m; desvio lateral de 3 km e sensibilidade 6 km; ajuste matemático 18‰/25‰. Todos **indicadores de investigação**, não cálculos validados de engenharia, tempo de circulação, acessibilidade ou impacto ambiental.

**Gatilho para shortlist de 3–6:** não basta ordenar km, Natura e pressão de MDS. Medir primeiro qualidade do serviço e acessos, travessias e interações hidrogeológicas, gradientes nas estações, potencial geométrico/estrutura e faixas plausíveis de custos. Não adquirir quadrículas DGT2m sem delimitação dos pontos críticos.
