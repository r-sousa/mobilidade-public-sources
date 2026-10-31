# MN-GEO-RAIL-001 — Acesso autenticado ao CDD a partir do GitHub Actions

**Estado:** implementação proposta no PR público W2; **testada offline sem credenciais**. **Ainda não houve execução autenticada**, download nativo, preservação do GeoTIFF, publicação canónica nem Fxx atribuído.

## Objetivo e arquitetura

`DGT CDD (conta registada)` → `GitHub Actions no repositório público` → `aquisição direta de 1 MDT-2m` → `QA raster/sha256` → `recibo sanitizado como artefacto da Action`.

O utilizador **não descarrega nem reenvia ficheiros grandes**, e a palavra-passe **nunca é colocada no código, nas mensagens, nos logs ou em ficheiros de dados**. Os *secrets* ficam encriptados e segregados num **GitHub Environment**; são disponibilizados apenas ao job que declara o ambiente, após as regras de proteção configuradas.

### Configuração única pelo proprietário do repositório

1. Abrir **[Settings → Environments](https://github.com/r-sousa/mobilidade-public-sources/settings/environments)** no repositório público.
2. Selecionar **New environment** e criar **`dgt-cdd`** (correspondência exata com `environment: dgt-cdd` no workflow).
3. Em **Deployment branches and tags**, selecionar **Selected branches and tags**, adicionar apenas a branch **`main`**.
4. Em **Required reviewers**, incluir a pessoa responsável por aprovar o arranque das aquisições autenticadas. Se só o próprio proprietário pode rever, **não ativar** `Prevent self-review`. A cada execução protegida será necessário aprovar o job antes de aceder aos secrets.
5. Em **Environment secrets**, criar **dois** segredos, *nunca* variáveis públicas/repository secrets:
   - `DGT_CDD_USERNAME` — e-mail ou identificador do registo CDD;
   - `DGT_CDD_PASSWORD` — palavra-passe da conta no CDD.
6. **Proteger a branch `main`** de alterações não revistas aos workflows e scripts, sobretudo quando existem colaboradores com escrita. Rever qualquer PR que altere `.github/workflows/` ou `tools/geo_rail_pt_cdd_authenticated.py` antes do merge e da aprovação da execução.
7. Rever e incorporar o **[PR público W2 #10](https://github.com/r-sousa/mobilidade-public-sources/pull/10)**. O workflow de produção com `workflow_dispatch` só deverá ser lançado **após o código fiável estar na branch `main`**.
8. Abrir **[GitHub Actions](https://github.com/r-sousa/mobilidade-public-sources/actions)**, selecionar **`MN-GEO-RAIL-001 DGT CDD registered one-tile acquisition`** → **Run workflow** → branch **main** → `mirandela` (ou `amarante`). Aprovar o environment `dgt-cdd` quando o GitHub o solicitar.
9. Confirmar o resultado no *workflow run*. O ficheiro de QA é **exclusivamente o recibo JSON** no artefacto `mn-geo-rail-001-dgt-cdd-one-tile-receipt-<run-id>`. O recibo pode ser partilhado por GitHub; nenhum raster nem sessão sai do runner nesta etapa.

**Não inserir credenciais no ChatGPT** nem no código e **não confundir** um secret de ambiente com uma variável Actions. O GitHub Environment só protege o secret se as regras de proteção estiverem efetivamente configuradas. O utilizador pode revogar ou rodar as credenciais no mesmo ecrã.

### Proteções implementadas na primeira aquisição

- Apenas execução manual `workflow_dispatch`; **não** existe trigger `push`, `pull_request` ou `pull_request_target` que use credenciais.
- Restrição no workflow a **`r-sousa/mobilidade-public-sources`**, branch **`main`** e ambiente **`dgt-cdd`**. Atualizar o identificador do repositório se houver transferência para organização, após revisão dos riscos.
- O código de login usa Keycloak público do CDD `auth.cdd.dgterritorio.gov.pt`, método baseado no [cliente comunitário QGIS](https://github.com/qgispt/dgtcd_downer), **sem** copiar as opções de TLS sem validação. Todos os pedidos são HTTPS com verificação TLS e redirecionamentos validados num allowlist.
- O recurso é selecionado a partir de **STAC** e de **dois IDs pré-revistos**; não permite digitar URLs de origem, executar código ou solicitar coleções arbitrárias. Piloto apenas `MDT-2m`, Mirandela (`MDT-2m-282510-09-2024`) ou Amarante (`MDT-2m-200484-07-2025`).
- Download de **um único GeoTIFF**, limitado a **350 MB** e ao host oficial `cdd.dgterritorio.gov.pt`. Redirecionamentos para outros hosts, inclusive cloud CDN não previamente avaliada, terminam em falha sem os seguir. Caso sejam tecnicamente necessários, devem ser auditados e sujeitos a revisão própria.
- A validação verifica TIFF, SHA256, CRS horizontal, pixel de 2 m, extensão contra o item STAC, NoData, número de células e estatísticas, com base em `tools/geo_rail_pt_native_intake_qa.py`.
- **Os bytes do raster não são guardados** em GitHub Artifact nem GitHub Release; só um recibo sanitizado é conservado por 15 dias. O perfil vertical não é considerado validado pelos metadados horizontais.
- O CDD **não disponibiliza ainda uma API de aquisição oficial estabilizada para este fluxo**. Se exigir MFA/CAPTCHA ou alterar o Keycloak, o cliente falha explicitamente; **não contorna** esses controlos.

### Próxima etapa após primeiro download bem sucedido

Conservar apenas evidência técnica e rever o resultado no [PR privado canónico #26](https://github.com/r-sousa/EU-transp-weekly/pull/26). Para armazenar e disponibilizar os MDT sem intervenção manual, implementar **um segundo estágio de publicação em GitHub Releases**, com controlo do licenciamento CC BY 4.0, atribuição, tamanho do objeto, versionamento, integridade por SHA256, referência Fxx e aceitação canónica. Esse estágio **ainda não está autorizado nem implementado**, evitando confundir a prova de acesso com a publicação institucional de dados.

### Documentação de referência

- [GitHub — ambientes, secrets e regras de proteção](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments)
- [GitHub — limitações e uso de Actions secrets](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets)
- [QGIS community — DGT CDD Downloader](https://plugins.qgis.org/plugins/dgt_cdd_downloader/) (não é API oficial DGT)
- [DGT — dados abertos, CC BY 4.0](https://www.dgterritorio.gov.pt/dados-abertos)
- [DGT — Centro de Dados](https://cdd.dgterritorio.gov.pt/)

## Verificação de rede sem credenciais — 30/10/2026

[GitHub Actions #41144702809](https://github.com/r-sousa/mobilidade-public-sources/actions/runs/41144702809) **SUCCESS**, [recibo HTTPS anonimizado](../reports/mn-geo-rail-001/pt-dgt-anonymous-login-https-preflight.json).

- Portal CDD: **HTTP 200** com certificado HTTPS verificado.
- Endpoint Keycloak `auth.cdd.dgterritorio.gov.pt`: **HTTP 200**.
- Formulário `kc-form-login` detetado, `action` submetível exclusivamente a host HTTPS oficial.
- Um campo oculto detetado, **sem** qualquer valor guardado.
- Nenhum `POST` de login, nome de utilizador, palavra-passe, cookie, sessão ou ficheiro nativo foi enviado/obtido.

O [teste de segurança do adaptador #41144598774](https://github.com/r-sousa/mobilidade-public-sources/actions/runs/41144598774) passou depois de corrigida a identificação dos bytes TIFF. Não existe ainda prova de credenciais válidas nem de autorização de download do asset após login; esta validação exige o Environment `dgt-cdd` configurado e execução explicitamente aprovada na branch `main`.

## Diagnóstico de redirecionamento de armazenamento — 31/10/2026

Na [execução real #41148933020](https://github.com/r-sousa/mobilidade-public-sources/actions/runs/41148933020), a autenticação CDD e a pesquisa STAC progrediram até ao pedido do GeoTIFF. O [recibo técnico sanitizado da Action](https://github.com/r-sousa/mobilidade-public-sources/actions/runs/41148933020/artifacts/13021734140) identificou especificamente `safe_error_phase=native_geotiff_download`, `safe_error_code=unapproved_redirect_destination`, `redirect_scheme_class=https` e `redirect_port=9000`. **0 bytes nativos**. A documentação do [DGT CDD Downloader (QGIS Portugal)](https://github.com/qgispt/dgtcd_downer) alerta igualmente para as portas 8081 e **9000**; esta coincidência indica uma infraestrutura de armazenamento não servida pelo host principal do portal, sem estabelecer por si só o domínio de destino.

Na [prova anónima #41149135443](https://github.com/r-sousa/mobilidade-public-sources/actions/runs/41149135443), um `HEAD` ao asset público devolveu apenas um **302 interno para o host CDD**; sem autenticação, não é possível provar o hostname externo. [Recibo de autoridade de redirecionamento](../reports/mn-geo-rail-001/pt-dgt-cdd-anonymous-redirect-authority.json) na branch de auditoria `mn-geo-rail-001-cdd-download-host-audit-20261031`.

Para validar o download sem alterar as credenciais, o [adaptador](../tools/geo_rail_pt_cdd_authenticated.py) passa a considerar elegível **um único salto HTTPS na porta 9000, emitido diretamente pelo servidor CDD no pedido autenticado do GeoTIFF**. Antes do acesso, exige que o IP literal ou todos os registos DNS resolvidos sejam públicos; proíbe endereços internos, locais, reservados ou metadata-service, autenticação embebida na URL, esquemas não HTTPS, portas arbitrárias e redirecionamentos posteriores. O pedido exterior utiliza uma **nova sessão HTTP sem cookies da conta DGT**, sem os cabeçalhos de autorização, com validação do certificado TLS, limite de 350 MB e verificação do formato GeoTIFF. A URL assinada não é guardada nem impressa. Se o destino apresentar TLS inválido, segunda mudança de servidor ou resposta inesperada, o processo **falha fechado**, sem desativar TLS.

A primeira execução com esta alteração será ainda **um piloto com um único raster** e recibo sanitizado: nem os testes offline nem a confirmação da infraestrutura garantem antecipadamente um download bem-sucedido. Aquisições de maior dimensão, persistência em GitHub Releases e publicação no Site continuam dependentes dos gates de qualidade/canonicidade.

## Persistência automática dos rasters nativos — piloto controlado (31/10/2026)

O [sucesso nativo W2 #41149632416](https://github.com/r-sousa/mobilidade-public-sources/actions/runs/41149632416) provou a aquisição autenticada de **um** GeoTIFF `MDT-2m-282510-09-2024` (1 219 159 bytes, SHA-256 `761bc7ee18ef9377cca97556b6dececc14b8765c017c168dbf15552d8c9d78ba`, EPSG:3763, 2m, 500×500). O runner apagou os bytes depois da QA; [recibo de proveniência permanente](../reports/mn-geo-rail-001/pt-dgt-mdt2m-mirandela-validated-native-sample.json).

Esta atualização acrescenta ao workflow manual protegido `mn-geo-pt-cdd-registered.yml` a opção `preserve_native`, por omissão **true**, apenas para a área `mirandela`. O adaptador copia para `RUNNER_TEMP` o **raster original e completo** depois de verificações SHA-256, GeoTIFF, CRS, resolução e cobertura. Antes de qualquer publicação, `tools/geo_rail_pt_cdd_preserve_manifest.py` impõe **exatamente o checksum original já validado** e as propriedades geométricas do piloto. Ficheiros novos ou alterados **não** são automaticamente publicados: ficam pendentes de análise e novo plano de preservação.

O segundo passo usa exclusivamente o `GITHUB_TOKEN` limitado ao job `dgt-cdd`, nunca os segredos da conta DGT, para criar uma **GitHub Release pública de pré-aceitação**, com etiqueta determinística pelo hash original, um asset `.tif` e um manifesto `.json` com proveniência, licença e QA. São acrescentadas notas que atribuem explicitamente à **Direção-Geral do Território** a origem e a licença **CC BY 4.0**. Se a Release já existir, descarrega o objeto publicado e confirma o SHA-256; **não reescreve nem substitui** assets. Não são criados artefactos Actions contendo píxeis ou segredos; apenas recibos de aquisição e publicação com 15 dias de retenção. O raster fica retido na Release, não no Site.

Para executar, após merge **iniciar nova ação** GitHub Actions na branch `main`, com `site=mirandela` e `preserve_native=true`. **Não utilizar Re-run jobs de uma execução antiga** (usa o código antigo). A revisão do ambiente `dgt-cdd` e a proteção da `main` continuam obrigatórias. A condição `site=amarante` mantém o modo diagnóstico sem persistência até revisão específica do tile.

**Âmbito de aceitação:** esta publicação é um arquivo técnico do ficheiro-fonte nativo, **não** equivale a confirmar cobertura contínua de Porto–Trás-os-Montes–Zamora, referencial vertical, mosaico de dados, compatibilização com a fonte espanhola, código Fxx ou publicação do Site. Esses gates permanecem separados e abertos.
