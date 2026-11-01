# G33 — Acessibilidade potencial uniforme dos 30 corredores e lacunas efetivas de qualidade de serviço

## Princípio de continuidade

A carteira integral definida em G32 é **27 G10 + 3 G30**, sem substituições. G33 acrescenta uma matriz de **30 × 6 = 180 observações de mercado urbano**, conservando todos os **90 cenários 160/200/250 km/h** técnicos G32. As seis cidades, pela mesma ordem e método, são Guimarães, Amarante, Vila Real, Mirandela, Macedo de Cavaleiros e Bragança. Vila Real e Bragança são obrigatórias; Sanábria permanece excluída. Não exigir estação em centro urbano, mas não inferir uma estação de um ponto da malha de 2km.

## Fontes reutilizadas sem novas aquisições volumosas

1. G10: original público das 27 cadeias da grelha de investigação, recuperado da release G10.
2. G30: três novas cadeias de investigação e respetivo quadro de proveniência, reutilizados da release G30.
3. G32: 90 resultados técnicos e ambientais comparáveis, sem alterações de metodologia, importados da release G32 e verificados pelos IDs de todos os 30 corredores.
4. G11: referências citadinas, método de projeção e distância mínima à linha, limiar máximo de ajuste OSRM de **600 m nas duas pontas**, tabela OSRM por cidade e sensibilidade idealizada de tempos adicionais de paragem.
5. G14 e G17/G18: BGRI2021 oficial e isócronas de chegada à estrada para **três famílias de estudo anteriores**, insuficientes para imputar população ou procura às 30 alternativas. Estes resultados não são indevidamente transferidos.

## Método

Para cada corredor e cada uma das seis referências urbanas, projetar a referência urbana sobre a poligonal dos centros da grelha 2km (EPSG:3763), medir distância euclidiana e referência de progressiva, converter o ponto para WGS84 e consultar o serviço OSRM demonstrativo para viagem rodoviária até à via de automóvel para a qual esse ponto foi ajustado. Fazer até **seis consultas por execução** (uma por cidade), com todos os 30 corredores na mesma janela temporal, deduplicando destinos coincidentes.

**Cuidado metodológico:** uma via navegável a menos de 600 m de um ponto na grelha não demonstra que exista acesso legal, instalação de estação, espaço disponível, linha ferroviária ou transferência viável. Um tempo OSRM é estimativa para um ponto de estrada e sem congestionamento real, não acesso à plataforma, não transporte público nem qualidade de serviço ferroviário. Falhas e timeouts produzem N/D; não reempregar valores antigos como se fossem da mesma execução. Não ordenar os corredores por um resultado único de acesso de uma cidade quando isso conflita com a qualidade geral do itinerário.

A matriz 180× produz seis indicadores geográficos e seis rodoviários por corredor; um quadro adicional 30×3 de cenários técnicos G32 inclui os mesmos seis mercados. Quatro padrões hipotéticos de paragens (expresso com VR/Bragança; regional com Amarante; regional com Guimarães; e seis cidades) são comparados em todas as 30 alternativas e velocidades, mas **o número de paragens não é garantia geométrica de implantação**. A análise de atraso por paragens adicionais é uma sensibilidade de aceleração/desaceleração e permanência, não horários ou tempos totais.

## Restrições e critérios para o próximo passo

- **BGRI2021 e qualidade do mercado:** para comparação verdadeira, calcular para cada uma das 30 alternativas a população residente em áreas de acesso rodoviário a cada **posição de estação que venha a ser validada**, com análise de dupla contagem, necessidades de serviço público e estimativas de 2021 devidamente datadas. Os produtos G14/G17/G18, restritos a 3 famílias e outras posições, não podem ser comparados indiscriminadamente aos novos pontos.
- **Relações entre mercados e serviço existente:** estudar Guimarães com a Linha de Guimarães, e Mirandela/Macedo com tipos de serviço/ligação rodoviária, não equiparar proximidade direta do novo eixo a existência de serviço ferroviário com paragem.
- **Estação real e interoperabilidade:** validar terreno à escala de estação, orientação de aproximação, níveis longitudinais, curvatura, vias de resguardo, entrada legal, estacionamento/intermodalidade e tempos de ligação.
- **Natura 2000 + PIC:** o G33 preserva os resultados G32 e bloqueia conclusões ambientais. Túnel sob o Marão/Alvão pode reduzir ocupação superficial, mas requer verificação hidrogeológica e avaliação apropriada aplicável. PIC continua pendente de definição e fonte geoespacial.
- **Custos e tempos ferroviários:** permanecem N/D até projeto 3D comparável; não usar comprimento/velocidade ou MDS como custo monetário.
- **Acesso por transporte público:** não assumir zero quando faltam feeds GTFS ou horários sistematicamente verificáveis para toda a NUTS2 Norte.

**Decisão:** não selecionar já 3–6 corredores nem adquirir mais quadrículas DGT2m. A próxima fase deve localizar interfaces potencialmente construíveis ao longo dos 30 e comparar acessibilidades por rede, demanda estatística histórica e efeitos das paragens, antes de impor a engenharia de detalhe nas faixas mais promissoras.

**Publicação:** pré-aceitação apenas, sem inserção no catálogo Fxx canónico nem Site Mobilidade Norte.
