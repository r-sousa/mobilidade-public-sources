# MN-GEO-RAIL-001 · G26 — COS2025 e gatilhos de nova aquisição MDT

## Resultados verificados das fontes

- Inventário do repositório público `r-sousa/mobilidade-public-sources`: não existia ficheiro, especificação ou release identificável como COS 2018/2023/2025 ou COSc, antes do G26. A ausência no repositório público não prova ausência de arquivo privado.
- Fonte primária COS2025: DGT, Série 2, `COS2025v1-S2`, referência 2025; disponibilizada em 2026, 102 classes e unidade mínima cartográfica de 0,5 ha. A COS2018v4 é a edição comparável segundo as especificações oficiais atuais; não misturar com edições anteriores sem ressalvas.
- OGC API `https://ogcapi.dgterritorio.gov.pt/collections/cos2025v1/items`: o inventário de coleções responde, mas o endpoint de entidades em produção devolveu HTTP 500 mesmo para `limit=1` ou a menor janela testada. Não inventar valores COS provenientes dessa API, não marcar os polígonos como adquiridos.
- Alternativa pública oficial: `https://geo2.dgterritorio.gov.pt/cos/S2/COS2025/COS2025v1-S2-gpkg.zip`, cujo HEAD confirmou `Content-Length: 876190334` bytes, `Accept-Ranges: bytes` e `Last-Modified: Wed, 29 Jul 2026 03:24:04 GMT`. Licença DGT CC BY 4.0. O G26C **concluiu com sucesso** a aquisição temporária do arquivo nacional, controlou tamanho, SHA256, CRC ZIP e GeoPackage fonte, e extraiu apenas sete círculos de 400 m (246 polígonos COS2025 originais recortados, cobertura completa em todos). O arquivo nacional nunca é publicado ou persistido no GitHub; a publicação pequena e separada no ramo principal é validada pelo mesmo hash do código recortador. SHA256 original do ZIP: `220bbdc5a25fa2bf927de37479314eb082a9cffcc2f5a6d644702795493e3f04`.
- COS descreve ocupação e uso do solo, não direitos sobre prédios, compatibilidade PDM, servidões SRUP, áreas REN/RAN, estabilidade geotécnica ou acessos legalmente possíveis. Nunca elevar COS isolada a aprovação/recusa de estação.

## Primeira caracterização da COS2025 para os sete setores

No raio de 400 m, percentagem de território artificializado nos três setores de Vila Real: aproximadamente **80%, 15% e 18%**; nos quatro de Bragança: aproximadamente **70%, 91%, 52% e 17%**. Estes são valores de uso/ocupação do solo, não disponibilidade de terrenos ou parcela de plataforma. Recomenda-se cruzamento posterior com restrições legais e cartográficas e com a geometria ferroviária contínua.

## MDT original de 2 m: situação

O G26B validou o conjunto de quadrículas originais DGT 1×1 km: **45** existentes antes do G21 + **39** obtidas e validadas no G21 = **84 quadrículas nominais (84 km²)**, descontando sempre NoData nas medições altimétricas. As quadrículas **2×2 km** são a trama exploratória G3/G10, não ficheiros 2 m da DGT.

O G23B foi executado com cobertura válida para 327 das 351 configurações locais de faixas hipotéticas de estação 400×50 m e aproximação 1000×60 m. Não se devem repetir os downloads de terreno usados nesse estudo.

Para 7 posições distintas, 16 eixos de orientação da shortlist G25, cálculo condicional apenas de interseção entre faixas retas hipotéticas de análise e quadrículas originais 1×1 km já conservadas:

| Extensão aproximada a partir do centro | Meia largura de faixa | Quadrículas necessárias, união | Já adquiridas, união | Lacuna condicional |
|---|---:|---:|---:|---:|
| ±1,5 km | 300 m | 37 | 31 | 6 |
| ±3 km | 300 m | 64 | 34 | 30 |
| ±6 km | 1 000 m | 183 | 48 | 135 |

Estas necessidades correspondem a **manter todas as 16 orientações**, algo que não foi decidido. São limites geográficos exploratórios (não estimativas de obra, comprimento ferroviário ou pedidos ao produtor).

## Gatilhos para próxima aquisição

1. Completar o cruzamento COS2025 com os sete setores e validar independentemente PDM, SRUP, REN, RAN, domínio hídrico, solo ocupado e rede rodoviária, para reduzir o número de locais/rumos.
2. Esboçar alternativas de aproximação com **continuidade horizontal e vertical ferroviária**, raios/cant/transições e faixas apropriadas por hipótese de serviço/velocidade (160, 200, 250 km/h), evitando tomar o eixo G10 de 2 km como caminho de ferro construível.
3. Intersetar o corredor de engenharia **efetivamente selecionado** com a quadrícula DGT de 1×1 km, retirar as 84 quadrículas já validadas e confirmar IDs oficiais STAC dos ficheiros em falta. Só então desencadear a aquisição adicional protegida, mantendo credenciais apenas no `dgt-cdd` quando necessárias.
4. Quando se estender o estudo para traçados interurbanos completos além dos setores urbanos, exigir novas aquisições em **faixas estreitas** após triagem do MDS Copernicus 30 m; não adquirir em bloco toda a área AFSC–Zamora.

**Estado de governança:** pré-aceitação do estudo geoespacial, sem promoção de fonte canónica Fx nem atualização do Site. Vila Real e Bragança obrigatórias, Sanábria excluída. Guimarães, Amarante, Mirandela e Macedo de Cavaleiros mantêm-se interfaces opcionais a avaliar.

Fontes primárias: Direção-Geral do Território (COS2025, MDT2m e metadados), INE BGRI2021 e fontes verificadas G19–G25. Dados de transporte público sistemáticos insuficientes: indisponibilidade de dados não equivale a inexistência de serviços.
