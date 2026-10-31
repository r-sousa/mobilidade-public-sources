# MN-GEO-RAIL-001 — preservar os originais MDT da grelha DGT de 12 km²

A DGT confirma que a informação geográfica descarregada do seu Centro de Dados é de **acesso aberto, sob licença CC BY 4.0**, exigindo o reconhecimento expresso da Direção-Geral do Território. Referências: [dados abertos DGT](https://www.dgterritorio.gov.pt/dados-abertos) e [política do Centro de Dados](https://cdd.dgterritorio.gov.pt/dgt-fe/sobre?language=en).

A grelha previamente indexada de **3 × 4 km**, em Mirandela, compreende 12 GeoTIFF originais MDT de 2 m. O ensaio protegido da [grelha de 12 quadrículas](../.github/workflows/mn-geo-pt-cdd-grid12.yml) verifica os 12 ficheiros, os limites exatos PT-TM06, 3 milhões de células e 17 interfaces internas, com 8 500 pares de células vizinhas. São guardados hashes SHA-256 por objeto e um recibo técnico sem endereços assinados ou dados de conta.

## Duas modalidades, na mesma execução manual

O parâmetro booleano `preserve_native_preacceptance` tem o valor predefinido **false**.

- **false**: adquirir e verificar as 12 quadrículas; conservar somente um recibo sanitizado (15 dias) no Actions. Os ficheiros GeoTIFF são eliminados quando o runner termina.
- **true**: depois de todos os testes reais passarem, copiar os **12 ficheiros originais**, verificar novamente cada SHA-256, transportar temporariamente os objetos para um job **sem credenciais DGT**, validar novamente as somas de controlo e publicar os GeoTIFF e o recibo numa **GitHub Release pública de pré-aceitação** com atribuição DGT / CC BY 4.0. Não criar Fxx ou novos dados no Site.

A Release é imutável e tem uma tag exclusiva com o ID da execução. Uma falha em qualquer aquisição, SHA-256, grelha ou fronteira impede a publicação. A autorização do Environment `dgt-cdd` e o bloqueio à `main` desprotegida permanecem em vigor. O job de publicação utiliza o token do próprio GitHub, com permissões de escrita apenas nesse job e **sem acesso às credenciais DGT**.

O objetivo é evitar a perda dos rasters após cada execução e, simultaneamente, conservar uma distinção inequívoca entre **fonte nativa preservada**, **teste de qualidade concluído**, **aceitação no catálogo canónico** e **adequação a análise ferroviária**. Estes dois últimos estados continuam negativos. O datum vertical português mantém-se identificado por documentação mas não confirmado por pontos de controlo nem harmonizado com o datum espanhol.

[Executar workflow protegido da grelha](https://github.com/r-sousa/mobilidade-public-sources/actions/workflows/mn-geo-pt-cdd-grid12.yml) — seleccionar `main` e, se se pretender preservar os originais, activar `preserve_native_preacceptance` antes de iniciar.
