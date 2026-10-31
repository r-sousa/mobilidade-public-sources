# MN-GEO-RAIL-001 — Como delimitar as áreas de aquisição de dados de relevo (31/10/2026)

## 1. O que está e o que não está definido

A [Infraestruturas de Portugal](https://www.infraestruturasdeportugal.pt/pt-pt/estudos-de-viabilidade-da-linha-de-alta-velocidade-de-tras-os-montes) identifica a **viabilidade de uma ligação Porto–Vila Real–Bragança–fronteira**, com eventual ligação a **Sanábria/Zamora**. Isso é o **objeto territorial/funcional de estudo**. Não implica um traçado ferroviário selecionado, uma obrigação de atravessar todos os centros urbanos, nem uma escolha definitiva de estações.

O **retângulo A1** `[-8.65,41.08,-5.55,41.92]` foi escolhido como **limite técnico inicial de aquisição** do modelo Copernicus 30m — não era, por si só, um corredor ferroviário válido. A avaliação posterior mostrou que **Puebla de Sanabria (centro urbano ~42.055° N) não estava incluída**. Portanto, A1 isoladamente não deve ser rotulado como cobertura de todas as opções indicadas pelo estudo oficial.

## 2. Quatro hipóteses espaciais de pesquisa, sem escolher traçados

| Identificador | Referências de pesquisa | Estatuto |
| --- | --- | --- |
| F1 | Porto, Vila Real, Bragança, Zamora | **Hipótese estrutural de política pública**; os referenciais oficiais são cidades/regiões de serviço, não pontos geométricos de passagem da via |
| F1b | Porto, Amarante, Vila Real, Mirandela, Macedo de Cavaleiros, Bragança, Zamora | Variante de **serviço territorial em análise**, não imposição de visita a todos os municípios |
| F2 | Porto, Chaves, Bragança, zona de Sanábria, Zamora | **Exploração alternativa setentrional**, com cobertura adicional a adquirir; não há compromisso de percurso através de Chaves |
| F3 | Porto, Peso da Régua, Torre de Moncorvo, Miranda do Douro, Zamora | **Hipótese meridional de sensibilidade**, não validada por estudos prévios como alternativa ferroviária viável |

**As linhas ligando estes centros são apenas eixos esquemáticos de pesquisa. Não são poligonais admissíveis da futura ferrovia** nem permitem inferir comprimento, custo, raio mínimo, inclinação, túneis, viadutos, procura ou coerência com a rede espanhola.

Os critérios objetivos para a fase de triagem são:
1. **End points Porto–Zamora** e referência ao objeto oficial Porto–Vila Real–Bragança. Confronto entre alternativas com serviço territorial e trajetos mais diretos.
2. **Rácio geodésico de desvio** `(d(Porto,x)+d(x,Zamora))/d(Porto,Zamora)`: cenários 1,15 (núcleo), 1,30 (alternativas) e 1,45 (sensibilidade máxima). O valor **não é um limite recomendado de extensão ferroviária**; requer ensaio de sensibilidade e comparação com soluções reais em terreno.
3. **Faixa de 20 km em torno dos eixos de referência conceptual**, sujeita a testes de 10 e 30 km. Objetivo: priorizar os locais para aquisição, não restringir juridicamente a passagem da linha.
4. **Setores quadrados de 10 km** em ETRS89 LAEA EPSG:3035. Medir efetivamente as cotas de MDS Copernicus e o relevo robusto `P95-P05` como **indicador preliminar de necessidade de informação de terreno**, não estimativa de terraplenagens ou de velocidade. Selecionar setores distribuídos pelo eixo oeste-leste e incluir controlos em baixo relevo.
5. **À escala fina**, cruzar a lista de setores com fronteiras oficiais, quadrículas/produtos DGT e IGN/CNIG, vales, hidrografia, restrições ambientais, geologia e ligações ferroviárias existentes. **Só então** escolher exatamente os ficheiros nativos MDT de 2m/5m a descarregar. Não há proposta de traçado até se comparar alternativas em terreno e condicionantes de engenharia.

## 3. Execução efetiva da aquisição A1b: extensão norte para a zona de Sanábria

O [workflow público A1b #41197841639](https://github.com/r-sousa/mobilidade-public-sources/actions/runs/41197841639) executou **dois jobs integralmente bem-sucedidos**, incluindo publicação separada sem credenciais de aquisição.

Foram descarregados e verificados **quatro GeoTIFF COG originais** do Copernicus `N41/N42 × W007/W006`, perfazendo **160 825 176 bytes de fonte**, e criada uma **nova faixa de superfície contínua** no retângulo WGS84 `[-7,41.92,-5.55,42.30]`, que inclui o centro urbano de Puebla de Sanabria (não equivale à localização da estação AV). O mosaico de 1 segundo de arco tem **5 220 × 1 368 píxeis, 7 140 960 todos válidos, 0 NoData**. Os testes analisaram a junção horizontal dos produtos `N41/N42` (latitude 42°) e a junção vertical `W007/W006` (longitude −6°). A fronteira com o mosaico A1 existente **é contígua em coordenadas a 41,92°**, mas os respetivos valores de píxeis de duas Releases ainda **não foram confrontados diretamente**.

A [Release A1b de pré-aceitação](https://github.com/r-sousa/mobilidade-public-sources/releases/tag/mn-geo-rail-001-a1b-sanabria-north-DSM-preacceptance-41197841639) preserva o GeoTIFF derivado de **16 154 365 bytes**, SHA256 `a78ac98fe87875a48857f0db7a2df283dbb57a2981b0f4cf3ed1012bcffc1fcc`, e relatório fonte original com SHA256 `018209687398bbf58ec7f73573e99144eb6dd69b1c7755e6a5d764fee4254fe8`, com [licença e atribuição Copernicus](https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM).

A faixa representa aproximadamente **5 062 km²** adicionais de modelo de **superfície**, fora da cobertura A1 (aproximadamente 24 146 km²), ambos com 100% das células raster de saída válidas, sem afirmar um MDT terrestre contínuo, datum vertical PT–ES validado ou corredor ferroviário selecionado.

## 4. Bloqueios concretos da fase de detalhe B1/C1

- A1/A1b: **base MDS regional** suficiente para orientar consultas e comparar relevo superficial, NÃO para determinar soluções ferroviárias.
- B1 português: a seleção exata de IDs DGT MDT2m deve verificar presença real dos produtos, limites oficiais PT/ES e orçamento de bytes antes de cada aquisição autenticada protegida por `dgt-cdd`. Não converter envelopes STAC em prova de píxeis.
- C1 espanhol: o MDT5m deve ser obtido por blocos WCS e preservado com atribuição IGN/CNIG; Sanábria e acessos a Zamora são áreas prioritárias que já têm base MDS.
- D1: comparação técnica de soluções implica avaliar raios mínimos, declives, velocidades e obras de arte, sempre em dados terrestres reais. Referenciais altimétricos independentes continuam no gate G4.

**Progresso será medido por dados originais efetivamente descarregados, área física válida e alternativas de território analisáveis**, não pelo número de candidatos STAC ou documentos de auditoria.
