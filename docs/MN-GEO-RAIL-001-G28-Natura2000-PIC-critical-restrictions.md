# G28 — Rede Natura 2000 e PIC: condicionantes estruturantes

## Missão recuperada
O estudo MN-GEO-RAIL-001 compara conectividades ferroviárias Porto/AFSC–Vila Real–Bragança–Zamora; Vila Real e Bragança são obrigatórias, Sanábria excluída. Guimarães, Amarante, Mirandela e Macedo de Cavaleiros continuam mercados opcionais cujo serviço deve ser apurado. As estações não têm de estar nos centros urbanos; terreno, acesso rodoviário e áreas legalmente disponíveis determinam a localização.

Os G10/G11/G12/G13/G23–G27 são estudos preliminares de geometria, terreno, acessibilidade e sete interfaces urbanos, **não** traçados reais construíveis. O G27 cruza REN/RAN/CRUS indicativos em sete áreas, mas não é uma triagem ambiental dos 27 corredores.

## Portões ambientais prioritários
1. **Natura 2000 Portugal e Espanha**: utilizar geometrias originais oficiais de sítios da diretiva Habitats (ZEC/SIC) e Aves (ZPE/ZEPA); identificar interseções e distâncias por corredor e interface. Privilegiar fortemente o evitamento, antes de comparar custos e tempos. Verificar os objetivos de conservação e potenciais efeitos directos, indirectos e cumulativos. O artigo 6.º, n.os 3 e 4, da Diretiva Habitats define a avaliação apropriada e eventual derrogação — não aplicar uma proibição absoluta automática.
2. **PIC**: registar como **restrição maior pendente**. Não há no material recuperado expansão da sigla ou delimitação oficial confirmada; é incorreto inventar o significado, a legislação ou os polígonos. Enquanto não for identificada a fonte PIC, nenhuma alternativa recebe aprovação ambiental final.
3. Outros níveis cumulativos: RNAP, REN/RAN, PDM vigentes, PEAP, domínio hídrico, áreas de risco, património e servidões de infraestruturas; o facto de uma região estar vazia numa resposta WFS não prova inexistência legal.
4. A linha G10 central das quadrículas (±250 m de faixa ilustrativa) não define área de obra. Um cruzamento com Natura 2000 identifica **risco forte e necessidade de evitar ou aprofundar**, não determina aprovação, recusa ou custos de túnel.
5. Nenhuma aquisição adicional automática dos 6/30/135 MDT DGT 2m condicionais até delimitar o conjunto dos corredores mais promissores com limites ambientais, funcionalidade e geometria ferroviária.

Fontes primárias:
- ICNF: https://sigservices.icnf.pt/server/rest/services/Areas_classificadas/FeatureServer/layers — camada rn2000_merge; https://geocatalogo.icnf.pt/catalogo.html
- MITECO/IEPNB: https://datos.gob.es/es/catalogo/e05068001-espacios-protegidos-de-la-red-natura-2000 — WFS, ficheiros e metadata RN2000.
- CE: https://environment.ec.europa.eu/topics/nature-and-biodiversity/natura-2000/permitting-procedure_en

Produto G28: cruzamento exploratório source-only das 27 linhas originais G10, com os sete círculos de estudo G27 (3 Vila Real, 4 Bragança), registos de fonte, SHA e respostas UNKNOWN onde o produtor não foi verificável. Proibir Fxx/Site até QA legal/ambiental.

## Primeiros resultados cruzados, fontes reais G28 (01/11/2026)

**Proveniência primária:** ICNF `rn2000_merge`, resposta GeoJSON oficial verificada, **23 geometrias** no perímetro solicitado, SHA256 `661525285a69885101c079de231e0e6d794ea66a12c833d3b5602fde022a3443`. Espanha: WFS oficial devolveu HTTP 403; usado com sucesso o **arquivo nacional SHP oficial do MITECO (118 038 973 bytes; SHA256 `ab463a477184eeadb1ef077d06766063627d1fdbd9e4629055ec3bfa7556d54e`)**, com **31 geometrias** recortadas ao perímetro em processamento efémero. O ficheiro nacional não é redistribuído. A edição de ficheiros espanhola tem `202412` no nome; a página apresenta dados de atualização 2025, o que **não autoriza assumir geometrias atualizadas em 2026**; a recência legal depende de confirmação autonómica/municipal por sítio.

**Resultado:** **27/27** cadeias G10 de centros de quadrículas exploratórias intersetam polígonos de Natura 2000 em Portugal e **27/27** também do lado espanhol. O primeiro cruzamento português apresenta 30,498 a 52,554 km de interseção nas linhas exploratórias. Estes valores **não são** comprimentos de ferrovias viáveis e **não** representam as áreas exatas de impacte; impõem procurar geometrias alternativas e investigar os objetivos de conservação.

| Família em discussão | Interseção PT (km de linha de investigação) | Interseção ES (km de linha de investigação) | Soma PT + ES (km) |
|---|---:|---:|---:|
| P1-2-1 (Amarante) | 35,421 | 0,309 | 35,730 |
| P2-2-1 (Guimarães) | 32,432 | 0,309 | 32,741 |
| P2-2-3 (variante fronteiriça) | 49,565 | 21,188 | 70,753 |

A comparação permite identificar **conflito particularmente pronunciado na P2-2-3**, mas não classificar a P2-2-1 como ambientalmente adequada: o valor ecológico dos habitats e a possibilidade de evitamento não são proporcionais aos quilómetros de interseção. Verificados no ICNF, entre outros, `Alvão/Marão`, `Montesinho/Nogueira`, `Rios Sabor e Maçãs`, `Morais` e `Douro Internacional`, variando com a alternativa.

Os sete círculos exploratórios de 400 m (três Vila Real e quatro Bragança) não intersetaram os polígonos oficiais portugueses consultados. Um setor de Bragança está a **6,6 m** da geometria Natura 2000 e um setor de Vila Real a **207,8 m**. São distâncias do limite do círculo de investigação, não de futuras obras, e não eliminam afetações indiretas nem outras servidões. As áreas de estudo continuam por verificar no terreno e perante planos e direitos fundiários.

**Implicação para a decisão macro:** a carteira G10 está excessivamente concentrada em geometrias com conflito observado e deve ser *reaberta* para novas famílias territoriais que procurem reduzir a afetação Natura **antes** de limitar a shortlist a três alternativas, cruzando as distâncias e a funcionalidade dos nós e sem supor desníveis de ferrovia ou custos inventados. O bloqueio PIC mantém-se em todas.

**Ficheiro reutilizável:** GeoJSON com polígonos oficiais recortados ao perímetro, identificadores/nome tal como disponíveis no produtor e hashes de origem, publicado sob o G28 (após ensaios e fusão). Permite nova triagem ambiental sem descarregar novamente os 118 MB do ficheiro nacional do MITECO. Permanecem obrigatórias as validações de restrições/autorização legal e geometrias ferroviárias reais.
