# MN-GEO-RAIL-001 — B1: 32 km² de MDT terrestre DGT2m realmente adquiridos e auditados

**31 de outubro de 2026 — pós-execução protegida, pré-aceitação para engenharia ferroviária.**

## 1. Evidência de aquisição e salvaguardas

A [execução GitHub Actions #41209791341](https://github.com/r-sousa/mobilidade-public-sources/actions/runs/41209791341) em `main` protegido completou **5/5 trabalhos**, incluindo controlo de proteção, aquisição autenticada independente em `dgt-cdd` para Vila Real e Bragança e publicação com verificação independente das fontes, em jobs sem credenciais DGT.

- **Vila Real:** [Release B1 original DGT](https://github.com/r-sousa/mobilidade-public-sources/releases/tag/mn-geo-rail-001-b1-DGT2m-vila_real-native-source-preacceptance-41209791341), 16 originais de 1 km², quatro mosaicos exatos de 2×2 km, recibo SHA256 `c9eb23b7d04a5847508816babeabd8487e9edf629db7e5ae566d53b65a3b1dff`, 19 010 472 bytes originais.
- **Bragança:** [Release B1 original DGT](https://github.com/r-sousa/mobilidade-public-sources/releases/tag/mn-geo-rail-001-b1-DGT2m-braganca-native-source-preacceptance-41209791341), 16 originais de 1 km², quatro mosaicos exatos, recibo SHA256 `57a7bd1ea927436f6125fa5f5869ad268f60555dd282e0fff23bc084fe67c69f`, 18 689 874 bytes originais.

**Auditoria independente nesta sessão:** descarregaram-se ambos os arquivos autorizados e reabriram-se **32 GeoTIFF originais e oito mosaicos** com `rasterio`. Para cada original recalcularam-se hashes e verificaram-se EPSG:3763, 2×2 m, 500×500 píxeis, **250 000 células válidas e 0 NoData**. Para cada mosaico confrontou-se o `bbox` e os IDs com a [seleção B1 de fontes aprovada](https://github.com/r-sousa/mobilidade-public-sources/releases/tag/mn-geo-rail-001-b1-review-source-tiles-after-road-DSM-join-41201246809), incluindo os oito quadrantes. As **32 junções interquadrícula** têm 500 pares de células vizinhas válidos cada (16 000 pares no conjunto). **A diferença de cotas entre células adjacentes não deve ser zero**: mede-se continuidade de presença dos valores, não igualdade de altitude.

**Resultado: 32 km² novos (8 000 000 células), não sobrepostos aos 12+1 km² já preservados no setor de Mirandela. Total português DGT2m efetivamente conservado: 45 km² distintos, descontínuos.**

## 2. Relevo terrestre e acessibilidade preliminar

A tabela usa **percentis P05 e P95 de altitudes reais do MDT2m**, calculados em cada mosaico completo; o seu diferencial mede relevo terrestre no painel, **não a rampa de um alinhamento ferroviário**. Para comparação, inclui-se a amplitude do MDS Copernicus anteriormente usado na triagem, e as distâncias geométricas mínimas às vias OSM cartografadas; **nenhuma é um tempo de acesso por rede viária**.

| Nó obrigatório | Setor relativo | BBOX EPSG:3763 (m) | MDT2m P95–P05 (m) | MDS30 P95–P05 (m) | A via principal local, retilínea (m) | A motorway/trunk, retilínea (m) |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| Vila Real | W | `20000, 180000, 22000, 182000` | 162.1 | 164.7 | 220 | 1701 |
| Vila Real | E | `40000, 184000, 42000, 186000` | 71.7 | 68.4 | 145 | 1014 |
| Vila Real | N | `34000, 184000, 36000, 186000` | 121.9 | 122.2 | 1077 | 989 |
| Vila Real | S | `34000, 176000, 36000, 178000` | 160.2 | 162 | 319 | 441 |
| Bragança | W | `110000, 234000, 112000, 236000` | 62.8 | 63 | 803 | 334 |
| Bragança | E | `116000, 238000, 118000, 240000` | 92.4 | 90.4 | 22 | 947 |
| Bragança | N | `110000, 242000, 112000, 244000` | 102 | 100.9 | 646 | 3386 |
| Bragança | S | `110000, 232000, 112000, 234000` | 87.9 | 88.1 | 440 | 198 |

**Aviso metodológico:** setores geométricos comparáveis na mesma quadrícula, mas diferenças elevadas de P95–P05 não provam inviabilidade ferroviária; a análise de continuidade, gradiente longitudinal por hipóteses e necessidades de túnel/viaduto terá de atravessar os **intervalos entre quadrículas**, ainda não adquiridos. A acessibilidade de uma estação exige acesso legal por vias conectadas, localização de entroncamentos e tempos efetivos, não distância ao eixo da autoestrada. Aferição vertical com marcos de nivelamento e transformação coerente PT–ES continuam pendentes.

## 3. Continuidade, localização e qualidade: fronteiras reais do resultado

1. **Vila Real e Bragança são mercados obrigatórios de serviço ferroviário**, sem imposição de estação nos centros urbanos. Os oito setores resultam de triagem, **não são locais de estação aprovados**.
2. A linha **Sanábria permanece excluída**. A referência rodoviária prioritária é a A4/IP4 e N-122, utilizada como hipótese de organização espacial e acessibilidade, não como eixo ferroviário.
3. **Continuidade da fonte:** provada internamente em cada bloco de 2×2 km, **não** entre os oito blocos nem ao longo de toda a área Porto–Vila Real–Bragança–Zamora.
4. **Precisão vertical:** ter valores reais de MDT2m não estabelece precisão/erro altimétrico absoluto nem compatibilidade dos referenciais PT–ES; o QA produtor e o modelo de datum exigem auditoria própria.
5. **Governança:** estes dados podem já sustentar a seleção de novas aquisições e comparações de relevo; ainda não se autoriza integração definitiva Fxx, publicação no Site como traçado ou estimativa de custos ferroviários.

**Próxima aquisição com maior valor:** preencher corredores/elos de ligação de solo nu de forma incremental, priorizando zonas críticas do Marão, aproximações a Vila Real, Vila Real–Bragança e Bragança–Quintanilha; comparar alternativas ferroviárias sob parâmetros de velocidade, raio e inclinação com o serviço efetivo de ambos os nós antes de multiplicar blocos isolados.
