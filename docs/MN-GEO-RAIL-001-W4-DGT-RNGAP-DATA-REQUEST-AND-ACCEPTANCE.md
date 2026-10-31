# MN-GEO-RAIL-001 — pedido técnico de marcas e altitudes da RNGAP

**Estado:** minuta técnica pronta para encaminhamento, **não enviada**; não constitui pedido institucional emitido por qualquer entidade.

## Destinatário e fonte

Direção-Geral do Território — Geodesia / Rede de Nivelamento Geométrico de Alta Precisão (RNGAP).

Fontes de referência verificadas:
- [DGT — Infraestrutura Geodésica e RNGAP](https://www.dgterritorio.gov.pt/atividades/geodesia/infraestrutura-geodesica): marcas, sistema Cascais Helmert 38 e ajustamento da rede;
- [DGT — Produtos geodésicos](https://www.dgterritorio.gov.pt/loja/geodesia): as **altitudes de marcas de nivelamento em suporte digital** constam como **gratuitas**;
- [DGT — Formulário de contacto](https://www.dgterritorio.gov.pt/formulario-contacto): canal institucional de pedido;
- [DGT — GeodPT08](https://www.dgterritorio.gov.pt/atividades/geodesia/modelo-geoide): modelo geoidal;
- [IGN — REDNAP](https://api-features.ign.es/collections/red_nap?f=html): contraparte espanhola; 151 marcas e 119 pares de alturas já preservados no projeto.

## Texto para solicitação (PT-PT)

**Assunto: Solicitação de dados digitais RNGAP para controlo altimétrico de modelos digitais do terreno — Norte de Portugal**

No âmbito de um exercício técnico de análise geoespacial relativo à continuidade e compatibilidade altimétrica de modelos digitais do terreno no Norte de Portugal e na área transfronteiriça com Espanha, solicita-se a disponibilização, em suporte digital, de uma seleção de **marcas da Rede de Nivelamento Geométrico de Alta Precisão (RNGAP)**.

A seleção pretendida corresponde à faixa exploratória de longitude **−8,65° a −6,10°** e latitude **41,05° a 42,05°** (WGS84/ETRS89, valores de seleção aproximados). Esta delimitação visa apenas amostragem e controlo dos modelos digitais, sem pressupor a escolha de qualquer corredor ou traçado ferroviário. Caso a base de dados o permita, agradecer-se-ia a identificação das marcas principais e intermédias, dando preferência às disponíveis na região de Trás-os-Montes e na proximidade da fronteira.

Para cada marca, solicita-se, quando disponível:
1. Identificador oficial, nome/tipo de marca, linha e secção da RNGAP e estado de conservação/validade;
2. Coordenadas oficiais e respetivo sistema de referência (preferencialmente **ETRS89/PT-TM06, EPSG:3763**), com indicação da precisão posicional ou da categoria de coordenação;
3. Altitude ortométrica oficial e descrição integral do referencial vertical (**Cascais Helmert 38 / Alth38**, identificação EPSG e informação sobre ajustamento/época, quando aplicável);
4. Altitude elipsoidal GNSS, caso disponível, respetivo referencial/época, qualidade e documentação;
5. Indicadores de exatidão, incerteza, qualidade, observação/atualização, e notas sobre a relação da altitude oficial com a marca física;
6. Identificação de eventuais restrições de reutilização e forma de atribuição da fonte, e descrição do esquema de dados/serviço.

Privilegia-se a disponibilização através de **URL estável de API ou WFS/OGC Features**, com consulta espacial limitada, ou, em alternativa, de ficheiro público oficial **CSV, GeoPackage ou GeoJSON**. Não é necessária a transferência de informação geoespacial pesada, nem de rasters. Se os dados já estiverem acessíveis em serviço atual, agradece-se o endereço exato, o nome da camada e os atributos de altitude disponíveis.

A informação destina-se a verificar a consistência de altitudes entre as superfícies MDT da DGT e do IGN/CNIG. As marcas espanholas e as grelhas geoidais estão documentadas separadamente. Os resultados de controlo apenas serão considerados depois de verificados os sistemas de referência, a qualidade das marcas, a correspondência espacial e a independência das observações.

Agradece-se a indicação do canal mais adequado para a cedência ou consulta técnica destes dados.

## Critérios de aceitação e proteção contra conclusões prematuras

- A resposta automática ao pedido **não foi enviada por este projeto**; será necessária ação institucional explícita para a sua transmissão.
- Aceitar **apenas dados atribuíveis à DGT** com atributos de origem verificáveis e sem inventar cotas ou identificadores.
- Não confundir marcas da **RGN** com marcas da **RNGAP**.
- Não tratar altitude ortométrica, altitude elipsoidal e separação geoidal como valores intercambiáveis.
- Não usar modelo de geóide ajustado às mesmas marcas como prova de validação independente (evitar circularidade).
- Não comparar diretamente cota física de uma marca com MDT de terreno nu para calcular RMSE sem controlo da posição vertical e do tipo de marca.
- Qualquer serviço HTTPS ou ficheiro original deve ser identificado por hash e data de obtenção; ligações HTTP históricas sem autenticação não justificam a aceitação de cotas.
- **G4 permanece parcial**, ainda sem benchmark transfronteiriço validado. **G5** e a publicação canónica **Fxx/Site** continuam bloqueados.

## Entrada esperada no Mobilidade Norte

Quando a DGT disponibilizar um serviço ou ficheiro adequado, criar um recibo de aquisição com:
`publisher`, `dataset_version`, `retrieval_utc`, `source_sha256`, `licence`, `feature_id`, `xy_crs`, `height_vertical_crs`, `height_m`, `height_accuracy`, `observation_epoch`, `producer_quality`, `mark_condition`, `origin_line`, `native_attributes`.

A normalização deverá manter os dados originais inalterados, documentar nulos e impedir agregações que ocultem a incerteza.
