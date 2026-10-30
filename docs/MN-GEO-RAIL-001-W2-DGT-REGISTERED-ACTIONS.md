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
