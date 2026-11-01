# G31 — Relevo, velocidade, áreas classificadas e eventual túnel Marão–Alvão

## Objetivo e limites

Aprofundar, com as **fontes geográficas efetivamente adquiridas**, as três alternativas genuinamente novas G30 e a referência P2-2-1 G10, testando as velocidades indicativas 160 / 200 / 250 km/h. Esta etapa não visa anunciar o traçado ferroviário ideal ou um túnel viável: visa excluir premissas que não se sustentam perante a curvatura/gradiente e identificar os dados de engenharia necessários para comparar soluções.

## Evidência reutilizada — sem nova aquisição DGT

- G10: 27 linhas de investigação da malha real de 2×2 km; referência P2-2-1 (Guimarães).
- G28: polígonos oficiais ICNF e MITECO, incluindo identificação de ZEC Alvão/Marão quando a etiqueta existe na fonte; fonte recortada, SHA256 e legalidade não presumida. **PIC permanece por identificar**.
- G30: três novas sequências geográficas de pesquisa autónomas (evitar interseções à superfície, hipótese de passar em túnel e diversificação geográfica), mantendo Vila Real/Bragança obrigatórias e Sanábria excluída.
- R1: ficheiro original Copernicus GLO30 de superfície (MDS), SHA256 \`a708b502b2eb86236c70f2d74322e9d8e2ea1417eb24094d0e43536845407bd9\`. Não é MDT solo nu nem levantamento geotécnico.
- G7: limiares geométricos indicativos de raio **1 500 / 2 400 / 3 700 m** para 160 / 200 / 250 km/h, deslocação lateral máxima de **3 km** e ensaio adicional a **6 km**; ensaios de rampa ilustrativa **18‰ misto e 25‰ passageiros**. Não são mínimos legais universalmente aplicáveis.

## Metodologia reproduzível

1. Projetar as quatro linhas originais para PT-TM06 (EPSG:3763), explicitando que o uso além-fronteira é apenas para investigação regional; não existe harmonização da referência altimétrica Portugal–Espanha.
2. Densificar com 400 m, suavizar com uma seleção conservadora de larguras gaussianas e testar curvatura *proxy* e deslocação lateral máxima à linha de estudo. A aceitação é estritamente **necessária mas não suficiente**: não há projeto de clotóides, curvas de transição, sobreelevação, gabaritos, plataforma, aparato de via ou transições de estação.
3. Se passar o teste horizontal, amostrar o **MDS original** e ajustar um perfil matemático do tipo Lipschitz sob gradiente 18‰ e 25‰, **sem impor cotas de estação nem curvas verticais**.
4. Quantificar a extensão da linha matemática situada 25 m e 50 m abaixo do MDS para representar **pressão topográfica potencial**. Não atribuir esse comprimento a **túneis reais**: o MDS inclui árvores/construções, faltam solos nus, formações geológicas, coberturas, portais e alinhamento longitudinal real.
5. Medir de novo a interseção Natura com as linhas suavizadas no G31: a deslocação em relação à malha 2 km pode alterar quais os sítios intercetados. Identificar separadamente a ZEC Alvão/Marão a partir da *etiqueta oficial* ICNF. Se a etiqueta não existir, devolver **UNKNOWN** e nunca zero presumido.
6. Associar à ZEC Alvão/Marão, apenas para orientar a revisão, os pontos de investigação com pressão de MDS negativa, distinguindo-os de qualquer conclusão de profundidade de túnel ou viabilidade de atravessamento protegido.

## Portões jurídicos e de engenharia após G31

- **Diretiva Habitats artigo 6.º**: túnel não é isenção; a avaliação adequada é necessária quando se verifiquem potenciais efeitos significativos. Aplicar regime e objetivos de conservação específicos da ZEC Alvão/Marão (DL 28/2025 e Portaria 135/2025/1), incluindo ecossistemas dependentes da água.
- **Novo traçado de engenharia:** linhas com curvas de transição, velocidades por troço, perfil e cotas de aproximação ferroviária obrigatórias a Vila Real e Bragança; verificar curvatura também nas zonas periurbanas e interfaces.
- **Hidrogeologia:** nascentes, turfeiras, aquíferos, linhas de drenagem, massas de água, permeabilidade, escombreiras/terras, poços/portais, galerias e métodos construtivos. Um túnel profundo pode ter menor ocupação superficial e elevado impacto indireto na água.
- **Serviço público:** confrontar a carteira com o acesso real em transporte rodoviário BGRI2021 e OSRM, tempo até interfaces, população e emprego, bem como oportunidades Guimarães, Amarante, Mirandela e Macedo de Cavaleiros.
- **Custos:** não precificar com base no MDS; obter geotecnia e secções de túnel/viaduto/terraplenagens, contingências, e análise benefício-custo antes da shortlist.

**Sem decisão de corredor**, sem qualificação jurídica de conformidade, sem custo/tempo de circulação inventados e sem publicação Fxx/Site.
