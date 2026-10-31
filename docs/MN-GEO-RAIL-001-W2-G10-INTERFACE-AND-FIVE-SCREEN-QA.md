# MN-GEO-RAIL-001 — W2 G10: ponte de inventário entre G08 e G07

**31 de outubro de 2026 · Evidência de catálogo, não cobertura altimétrica nativa.**

## Origem e procedimento

A [execução oficial anónima G10 #41193613101](https://github.com/r-sousa/mobilidade-public-sources/actions/runs/41193613101) completou **quatro consultas STAC HTTP 200** (duas áreas de revisão, duas coleções `MDT-2m` e `MDT-50cm`), sem credenciais, downloads de raster ou URLs assinados. As áreas foram `[-7.85,41.20,-7.75,41.30]` e `[-7.85,41.30,-7.75,41.40]`, preenchendo uma lacuna **longitudinal de consulta** entre G08 `[-8.65,41.05,-7.85,41.35]` e G07 `[-7.75,41.25,-7.25,41.55]`. Trata-se de **áreas de revisão de metadados**, sem escolha de alinhamento ferroviário.

A [execução de reconciliação #41193701251](https://github.com/r-sousa/mobilidade-public-sources/actions/runs/41193701251) recomputou, a partir dos cinco recibos com SHA256 preservado, todas as deduplicações e exceções geométricas, registadas no [relatório de cinco levantamentos](../reports/mn-geo-rail-001/pt-dgt-five-screen-catalogue-union-qa.json). Foram usados apenas campos permitidos da resposta oficial (identificador do produtor, envolvente recuperada de geometria, estado HTTP/paginação); não são armazenadas referências privadas nem elementos de autenticação.

| Medida de catálogo | Evidência |
| --- | ---: |
| G10, janelas verificadas / pedidos completos | 2 / 4 |
| G10, identificadores únicos por resolução | 230 |
| G10, IDs já presentes nos quatro levantamentos anteriores | 131 |
| **G10, novos identificadores por resolução** | **99** |
| G10, IDs em comum com G08 | 17 |
| G10, IDs em comum com G07 | 18 |
| G10, divergências bbox 2 m / 50 cm | 0 |
| União E01–E06, G07, G08, G09 e G10 | **7 169 identificadores por resolução** |
| Janelas totais / consultas completas totais | 58 / 116 |
| Exceções de envelope entre 2 m e 50 cm no conjunto | 54 |
| Pares de envelopes 2 m/50 cm idênticos | 7 115 |

**Controlo adicional de proveniência:** nos quatro pedidos G10, a resposta STAC comunicou `source_bbox_not_wgs84` para todos os 480 registos por coleção/janela acumulados, e o leitor seguro recuperou envelopes WGS84 da geometria. Os resultados da união verificam que o mesmo identificador de produtor mantém envelope consistente entre os vários levantamentos. Não se deve substituir os envelopes geométricos por coordenadas do campo `bbox` no sistema errado.

A presença de IDs comuns aos dois conjuntos G08/G07 e ao G10 confirma apenas a **continuidade do inventário consultado**, não continuidade de píxeis, disponibilidade física de produtos nem precisão vertical. Ainda não existe demonstração de superfície MDT contínua Porto–Zamora; os dados espanhóis exigem validação separada e não foi concluída harmonização de referenciais verticais.

**Segurança/governação:** 0 bytes raster novos adquiridos por G10; sem autorização Fxx, Site ou traçados ferroviários. As anteriores 13 quadrículas de fonte original DGT realmente ensaiadas continuam confinadas a **12+1 km² desconexos**.
