# MN-GEO-RAIL-001 — Plano operacional de aquisição por cobertura útil

## Objetivo e sequência

**Missão:** recolher dados suficientes para caracterizar **alternativas regionais de conectividade ferroviária** entre Porto, Amarante, Vila Real, Mirandela, Macedo de Cavaleiros, Bragança e Zamora. As coordenadas de localidades indicam áreas de interesse, **não constituem um alinhamento aprovado**. Não aceitar valores de declive longitudinal de ferrovia, cálculo de túneis/viadutos ou engenharia até à verificação dos critérios físicos e das limitações de modelação.

| Ordem | Fonte | Área/unidade de aquisição | Produto utilizável | Dependência e critério de conclusão |
| --- | --- | --- | --- | --- |
| **A1 imediata** | Copernicus DEM GLO-30 público, 1 arc-second, MDS | 4 quadrículas de 1° N41 W009-W006; recorte WGS84 `[-8.65,41.08,-5.55,41.92]` | **Um GeoTIFF regional de MDS 30 m contínuo**, verificável e com licença/atribuição | Quatro fontes bytes completos com SHA256; QA de dimensão e CRS; quantidade real de píxeis válidos; três fronteiras de quadrícula; publicar recorte na Release sem distribuir ficheiros fonte de 1° |
| **B1** | DGT MDT-2m, fonte autenticada sob `dgt-cdd` | **Lotes pequenos** selecionados pelo relevo/alternativas depois de A1; não todo o corredor às cegas | MDT terrestre genuíno, cobertura e NoData locais, metadados oficiais e hashes | Executar exclusivamente via workflow protegido em `main`, sem segredos em PR. Preservação CC BY 4.0 em Release separada, decisão de custo/volume antes de lotes seguintes |
| **C1** | IGN/CNIG Espanha MDT5 m, WCS público | Blocos de 2–8 km², priorizando áreas da ligação a Zamora, fora dos três ensaios anteriores | GeoTIFF de respostas WCS e QA de continuidade de blocos adjacentes; distinguir saída WCS e arquivos originais | Sem credenciais; fonte e licença registradas; registrar datum específico do serviço sem inventar validação geodésica |
| **D1** | Harmonização geoespacial | Interseção real das áreas A1/B1/C1 e alternativas objeto de análise | Índice de cobertura e ausência de dados, máscaras, referenciais documentados | Comparar somente valores com sistema e semântica compatíveis; G4 contínua até marcos físicos independentes e prova vertical |

## Executar sem travagens desnecessárias

A1 já possui em `reports/mn-geo-rail-001/r1-20261030-producer-list-and-head.geojson` os quatro identificadores oficiais N41 e os `Content-Length` do produtor: **161 565 323 bytes cumulativos**. Não é preciso nova pesquisa em catálogo. Uma execução GitHub Actions descarrega as quatro fontes oficiais e cria o MDS no mesmo runner; o derivado e o recibo de qualidade passam para um segundo job **sem segredos** e são publicados em Release com atribuição correta. Não há transferência manual pelo utilizador.

Ao contrário dos controlos anteriores, esta aquisição passa de cabeçalhos/representações para **píxeis reais numa extensão regional**. G3 pode registar continuidade do **MDS** no retângulo pesquisado, sem dizer que existe um MDT bare-earth contínuo ou precisão vertical ferroviária. O MDS inclui casas, estruturas e vegetação.

**Licença:** [Copernicus DEM GLO-30, catálogo oficial](https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM), com aviso expresso de atribuição para derivados. Produto oficial vertical nominal: EGM2008 (EPSG:3855); saída TIFF permanece com CRS horizontal EPSG:4326 e sem comprovação independente do datum de cada pixel. A legislação, direitos e licença da fonte não são equivalentes a validação para projeto de engenharia.

## Indicadores de execução

Acompanhar **área válida real do raster**, fração NoData, contagem de píxeis, continuidade entre quadrículas originais, tamanhos, SHA256, licença e disponibilização da Release — e não quantidade de metadados STAC. **Sem Fxx nem Site** antes de um controlo de aceitação para dados de relevo no Mobilidade Norte.


## A1 — execução efetiva e aceitação do primeiro mosaico territorial (31/10/2026)

**Estado: adquirido e validado por píxeis reais; a fonte é MDS e não MDT.** Execução original [#41195781919](https://github.com/r-sousa/mobilidade-public-sources/actions/runs/41195781919) concluiu quatro downloads de fonte e detetou no ficheiro derivado uma coluna vazia (3 024 células) no extremo oriental — **recorte substituído e não usar como base de trabalho**. A execução **corrigida** [#41196011697](https://github.com/r-sousa/mobilidade-public-sources/actions/runs/41196011697) adicionou margem de leitura à direita, recortou os píxeis até ao limite exato e passou critérios com **zero NoData**.

| Métrica da aquisição corrigida | Resultado |
| --- | --- |
| Fontes originais completas descarregadas, hasheadas e verificadas | 4 COG, 161 565 323 bytes |
| Quadrículas fonte | N41 W009, W008, W007 e W006 |
| Bounding box WGS84 de saída | `[-8.65,41.08,-5.55,41.92]` |
| Grelha de saída | 11 160 × 3 024, 1 segundo de arco (sem redução da resolução espacial nominal) |
| Células válidas | **33 747 840 / 33 747 840 (100%)** |
| Células NoData | **0**, após correção do extremo leste |
| Controlos de continuidade | Meridianos −8°, −7°, −6°: 3 024 pares válidos e 0 pares em falta por meridiano |
| Dimensão do GeoTIFF derivado comprimido | 82 508 645 bytes |
| SHA256 do GeoTIFF corrigido | `52845032afedda302a32f56c9dcd3f070b6b5c970f9fd84a43b8d284f1bcbbe2` |
| Altimetria | Fonte nominal EGM2008 (EPSG:3855); sem transformação vertical realizada |
| Tipo | **Modelo Digital de Superfície — edifícios/vegetação incluídos** |

As quatro fontes provêm de um arquivo oficial aberto, sem token. As quatro *fontes originais de 1 grau* foram usadas para inspeção, cobertura e SHA256 mas **não foram redistribuídas**. Apenas o recorte MDS de cobertura regional é destinado à Release, com o aviso de atribuição exigido pelo [Copernicus](https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM).

O facto de todos os píxeis existirem no **MDS** **não significa** que o solo nu tenha continuidade comprovada, que o relevo terrestre esteja livre de artefactos ou que seja possível estimar diretamente gradientes de via férrea, túneis, muros de suporte ou escavações. A1 elimina a lacuna de **base digital regional de superfície**, não os controlos técnicos de B1/C1/D1.

**Recomendação operacional seguinte:** usar a grelha 30m real como **índice de priorização de blocos** de DGT2m e CNIG5m em vez de descarregar milhares de quadrículas de alta resolução sem áreas prioritárias verificadas. Documentar precisamente o perímetro, grelha e source ID dos blocos futuros.
