# G40 — Comparação de terreno IGN/CNIG original em quatro alternativas

## Resultado verificado em 1 de novembro de 2026

A execução de aquisição e QA da etapa G40, [GitHub Actions 41316662887](https://github.com/r-sousa/mobilidade-public-sources/actions/runs/41316662887), mediu **36 pontos** de terreno espanhol em quatro alternativas G10/G30, com **27 ficheiros GeoTIFF originais distintos**, sem falhas de fonte. Reutilizou-se terreno idêntico em **9 observações** porque as variantes de evitamento Natura à superfície e a hipótese de túnel **coincidem geometricamente nos 9 pontos orientais** entre 15 e 55 km de Zamora.

Nenhum dos dados transforma estes pontos de grelha de 2 km em ferrovias projetadas. As amostras são observações nativas de terreno de solo nu do **IGN/CNIG WCS Elevacion25830_25**, EPSG:25830, resolução **25 m**, entregues através de pedidos de 1 km². A geografia foi limitada a Espanha com margem de 1,5 km perante a fronteira NUTS0 GISCO generalizada, não uma fronteira cadastral.

| Corredor | Pontos de solo nu válidos | Cota mínima e máxima amostrada (m) |
|---|---:|---:|
| G10 P1-2-1 | 9 | 766–842 |
| G30 evitamento Natura | 9 | 719–820 |
| G30 hipótese de túnel | 9, dados originais reutilizados | 719–820 |
| G30 diversificação territorial | 9 | 677–853 |
| **Total** | **36 observações, 27 fontes distintas** | — |

### Conclusão geográfica

A maior separação entre alternativas nas posições de amostragem foi de **9,119 km** (aproximadamente 30 km antes de Zamora). Os resultados demonstram que existem diferenças relevantes de implantação territorial, mas que **a alternativa de túnel e a variante de evitamento superficial não são distintas no setor espanhol analisado**. O eventual mérito da opção subterrânea depende da geometria vertical, geologia e condições ambientais nos setores onde realmente divergir; não pode ser inferido destes dados.

A amostragem longitudinal de 5 km entre pontos de grelha não constitui verificação da pendente ferroviária. O perfil altimétrico de solo nu não identifica túnel, viaduto, terraplenagem ou custo; velocidade 160/200/250 km/h e qualidade de serviço continuam hipóteses a avaliar.

### Portefólio, restrições e aquisição seguinte

- Permanecem **27 corredores G10 + 3 G30** na carteira; quatro foram escolhidos apenas para testar e comparar a aquisição real do terreno espanhol.
- Os estudos anteriores G23–G27 dos **sete sítios de estação** de Vila Real e Bragança, e as **84 quadrículas DGT de 2m**, continuam a ser a referência em Portugal.
- A diferenciação de obras e de serviço exige traçados ferroviários horizontais/verticais contínuos, curvas de transição e estações com cota e acesso válidos; o modelo G10/G30 ainda é apenas uma grelha de investigação.
- O atravessamento Alvão–Marão depende de fonte oficial LNEG sobre geologia, hidrogeologia, falhas e sondagens, de efeitos sobre habitats e águas subterrâneas e de delimitação exata de portais e estruturas. **PIC não tem ainda uma delimitação oficial identificada**.
- A próxima aquisição de terreno deverá concentrar-se nas zonas com divergência geométrica relevante e, em Portugal, nos trechos críticos escolhidos depois de ensaiar faixas de traçado e reaproveitar o MDT2m arquivado. Não se autoriza a aquisição em massa das quadrículas de estudo do G37.

Os ficheiros G40 disponibilizam 36 registos, 27 GeoTIFF originais em ZIP com SHA individual, gráfico dos quatro perfis, mapa de pontos e matriz de distâncias entre hipóteses.

**Pré-viabilidade; sem Fxx, Site, viabilidade legal, proposta construtiva, custos ou tempos comerciais.**
