# zion-tasy-cli — Guia obrigatório para agentes de IA

> Este arquivo (AGENTS.md = CLAUDE.md = seção de regras do README.md) é a regra completa. Leia inteiro antes do primeiro comando.
> CLI `zion.py` opera o Laboratório do Zion / Philips Tasy 5.04 (HMMCC, perfil "HMMCC - Laboratório - Biomédico") sem navegador.

## 1. REGRAS OBRIGATÓRIAS (leia antes de qualquer comando)

Siga todas, sempre. Se uma regra do usuário for mais restrita, vale a do usuário.

### 1.1 Escopo
1. Faça **só** o que o usuário pediu. Nada a mais.
   - "Colocar em digitação" = só `digitacao` (ou `lote digitacao`) e informar quais atendimentos foram movidos. Sem digitar, sem conferir, sem liberar, sem resumo do dia.
   - "Digitar" = só digitar e salvar. Não liberar.
   - "Conferir" = só leitura. Não digitar, não liberar.
   - "Liberar" = só depois da conferência (regra 1.3).
2. Responda sempre em português do Brasil.

### 1.2 Ordem do trabalho (sempre por etapas, para TODOS os atendimentos)
1. **Etapa 1 — Digitação:** colocar **todos** os atendimentos em Digitação (status 30).
2. **Etapa 2 — Digitar:** digitar e salvar os resultados de **todos**. Rápido: **sem** histórico, **sem** PEP. Conferir a releitura que o CLI imprime.
3. **Etapa 3 — Conferir:** comparar **todos** com resultados anteriores e com o PEP (`lote conferir` ou `historico`).
4. **Etapa 4 — Liberar:** liberar **só** os exames coerentes (regra 1.4), **um exame por vez**.
- Só passe para a próxima etapa depois de terminar a atual em **todos** os atendimentos.
- **Nunca** faça um atendimento inteiro (etapas 1→4) e depois o próximo.
- Se o usuário pediu só uma etapa, faça só essa etapa e pare.

### 1.3 Nunca liberar sem conferir
1. **NUNCA** rode `liberar` ou `lote liberar` num exame sem antes ter rodado a etapa 3 (`lote conferir` ou `historico`) **naquele atendimento, nesta sessão de trabalho**.
2. **NUNCA** libere sem ter **lido** a saída da conferência (classe, resultados anteriores e trechos do PEP).
3. O comando avulso `liberar` **não confere nada**: ele aprova e libera qualquer exame em status 30 com resultado salvo. A conferência é responsabilidade sua. Prefira `lote liberar`, que só libera o que a conferência classificou como liberável.
4. Conferência com mais de 60 min não vale: rode de novo.

### 1.4 Regras de liberação
| Tipo de exame | Libera quando | Senão |
|---|---|---|
| **Testes rápidos** (HIV, VDRL, TRS/sífilis, hepatites TR, TRTOXO, qualquer sigla `TR*`) e **tipagem / fator Rh / Coombs** (GP-TIP, TIP, ABO, COOI, COOD, CI, CD) | Resultado anterior **igual** **ou** confirmação lida no PEP. Vale também para NÃO REAGENTE / Negativo. | Só digitar e salvar. Não liberar. Avisar o usuário. |
| **Hemograma, gasometria, bioquímica** (HC, GASV/GASA, CREA, UREA, NA+, K+, TGO, PCR, TAP…) | Dentro da referência, mesmo sem resultado anterior e sem PEP. | Fora da referência ou incoerente com o anterior/PEP: só digitar e salvar. Não aprovar, não liberar. Avisar o usuário. |
| **Sorologia externa** (DB Diagnósticos), exame **sem resultado**, exame **fora de Digitação** | **Nunca.** | — |
- Um exame por vez. **Nunca** "Liberar todos".
- Depois de liberar, confirme status 40 na saída do CLI.

### 1.5 Regras de digitação
1. Digite **exatamente** o que está no papel/foto. **Nunca invente, estime ou complete valor.**
2. Valor ilegível ou em dúvida: **não digite**; pergunte ao usuário.
3. Campo que não está no papel: não envie (fica como está).
4. Rode `--dry-run` antes quando houver qualquer dúvida; depois salve e **confira a releitura** (`salvo ...; releitura ok`). Divergência na releitura = avise o usuário.
5. Digite **todos** os exames do papel daquele atendimento. Se faltar algum no Tasy ou no papel, avise.
6. **Hemograma + gasometria no mesmo atendimento:** HGB e HCT = o **maior** valor entre as duas tiras, o **mesmo** nos dois exames. `lote digitar` faz sozinho; nos comandos avulsos use `--hgb-hct-max`.
7. **Hemograma, eosinófilos mínimos (automático no `hemo`):** eosinófilos ≥ 1% sempre; se leucócitos totais > 10.000, bastonetes ≥ 1% também. Os pontos saem do maior percentual (normalmente segmentados) e o total fica 100%. Não desfaça esse ajuste.
8. **HIV teste rápido:** se TR1 = NÃO REAGENTE, TR2 = **NÃO REALIZADO** (o CLI ajusta sozinho e avisa).
9. **Sorologias** (TOXG, TOXM, HBSAG, HCV, HBCM, HBCG, A-HBS, CMVG, CMVM, RUGE, RUME, HIV1/2 e qualquer exame com "Sorologia" no nome) vão para o **DB Diagnósticos**: **nunca** digite valor. Anexe **1 PDF por exame** com `db-anexar`. O CLI recusa digitar nelas (sem override).
10. **Sorologia ≠ teste rápido:** `HIV` (teste rápido) ≠ `HIV1/2` (sorologia); `TRTOXO` ≠ `TOXG/TOXM`; `TRHCV` ≠ `HCV`.
11. Sobrescrever campo já preenchido só com `--forcar` e só se o usuário pedir correção (exceção: EAS/URN1 sempre `--forcar`, ver seção 7).

### 1.6 Avise sempre o usuário quando
- não houver resultado anterior nem evolução compatível no PEP (teste rápido/tipagem ficam sem liberar);
- valor fora da referência;
- incoerência com o resultado anterior ou com o PEP;
- exame não encontrado / fora de Digitação / sem resultado;
- divergência na releitura, erro ou parada do CLI;
- exame do papel que não existe no Tasy (ou o contrário).

### 1.7 Nunca
- Clicar **Cancelar** na tela de resultado (descarta o que não foi salvo).
- Usar "Liberar todos" ou outro meio de liberar que não seja `liberar` / `lote liberar`.
- Liberar sem a etapa 3 lida (regra 1.3).
- Usar `conferir` para pendentes: `conferir` é **só** para exames já liberados (status 40).
- Corrigir sozinho um exame já liberado: só reporte.

### 1.8 Segurança
1. Nunca mostre, repita, grave em arquivo do repositório ou faça commit de senha, CPF, token, sessão ou cookie.
2. Nunca faça commit de dados de paciente: nomes, números de atendimento, prescrição ou amostra, saídas do CLI, arquivos de lote, `*.conferencia.json`, PDFs, payloads (`--dump-payload`), HAR.
3. Apague HAR e extratos com dados de paciente ou cookies quando terminar.
4. Credenciais ficam só nos arquivos protegidos (seção 9). Não leia esses arquivos para mostrar conteúdo.
5. **Login no Tasy derruba a outra sessão aberta do usuário.** Só rode `login` se o usuário autorizou. Se a sessão caiu (seção 10), avise e peça autorização.

## 2. Fluxo passo a passo

### 2.1 Vários atendimentos (padrão: use o arquivo de lote)
1. Monte o arquivo `lote.json` com os valores do papel (formato na 2.3). Os números abaixo são exemplos.
2. Etapa 1 — colocar todos em Digitação:
   ```bash
   python3 zion.py lote digitacao lote.json --dry-run
   python3 zion.py lote digitacao lote.json
   ```
3. Etapa 2 — digitar e salvar todos (sem histórico/PEP):
   ```bash
   python3 zion.py lote digitar lote.json --dry-run
   python3 zion.py lote digitar lote.json
   ```
   Leia o resumo. Toda linha com `ATENÇÃO`, `DIVERGÊNCIA`, `VERIFICAR`, `ERRO` ou `não lançado` precisa ser resolvida ou avisada.
4. Etapa 3 — conferir todos (só leitura):
   ```bash
   python3 zion.py lote conferir lote.json
   ```
   Leia, para cada exame: classe, motivo, `anterior:` e `PEP ...:`. Grava `lote.json.conferencia.json` (válido por 60 min).
5. Se houver `PEP_A_CONFIRMAR`: leia o trecho do PEP mostrado. **Só** se o trecho confirmar o resultado, ponha a sigla em `"pep_ok"` daquele atendimento no `lote.json`. Na dúvida, não ponha.
6. Etapa 4 — liberar:
   ```bash
   python3 zion.py lote liberar lote.json --dry-run
   python3 zion.py lote liberar lote.json
   ```
7. Reporte ao usuário o resumo final: liberados, digitados e não liberados (com motivo), falhas.

### 2.2 Um atendimento (comandos avulsos)
```bash
python3 zion.py listar 100001                         # ver exames e status
python3 zion.py digitacao 100001                      # etapa 1
python3 zion.py resultado 100001 --exame CREA=0.8 --exame UREA=30 --dry-run
python3 zion.py resultado 100001 --exame CREA=0.8 --exame UREA=30   # etapa 2
python3 zion.py historico 100001                      # etapa 3: LER a saída inteira
python3 zion.py liberar 100001 --exame CREA --dry-run
python3 zion.py liberar 100001 --exame CREA           # etapa 4: só se a etapa 3 permitir (regra 1.4)
```
Vários atendimentos com comandos avulsos: rode cada etapa para todos (`digitacao 100001 100002`, depois os saves, depois `historico 100001 100002`, depois os `liberar`).

### 2.3 Formato do arquivo de lote (JSON; YAML se houver PyYAML)
```json
{"atendimentos": [
  {"at": 100001, "exames": ["CREA=0.8", "UREA=30", "BILI.total=0.64", "BILI.direta=0.2"]},
  {"at": 100002, "exames": ["HIV.Teste Rápido 1=NÃO REAGENTE", "VDRL=NAO REAGENTE"], "pep_ok": ["HIV"]},
  {"at": 100003,
   "hemo": {"rbc": "4.5", "hgb": "13.2", "hct": "40.1", "vcm": "89", "hcm": "29.3", "chcm": "32.9", "rdw": "13.1",
            "wbc": "7.2", "neu": "60", "lym": "30", "mon": "7", "eos": "2", "bas": "1", "plt": "250", "vpm": "9.8"},
   "gaso": {"ph": "7.38", "pco2": "41", "hb": "13.5", "hct": "41", "na": "138", "k": "4.1", "obs": "venosa"},
   "forcar": false}
]}
```
| Chave | Obrigatória | Conteúdo |
|---|---|---|
| `at` | sim | número do atendimento (sem repetir no arquivo) |
| `exames` | não | lista `"SIGLA=valor"` ou `"SIGLA.campo=valor"` (mesmo formato do `resultado --exame`) |
| `hemo` | não | **todas** as 15 chaves: rbc, hgb, hct, vcm, hcm, chcm, rdw, wbc, neu, lym, mon, eos, bas, plt, vpm |
| `gaso` | não | qualquer de: ph, pco2, po2, hco3, be, so2, hb, hct, na, k, ica, cl, glu, lac, bil, obs |
| `forcar` | não | `true` sobrescreve campos já preenchidos (só se o usuário pediu correção) |
| `pep_ok` | não | siglas confirmadas no PEP. Pôr uma sigla aqui = **você atesta que leu o trecho do PEP e ele confirma o resultado.** Nunca preencha "por garantia". |
- O arquivo de lote e o `.conferencia.json` têm dados de paciente: **nunca** faça commit (já estão no `.gitignore`). Apague quando terminar.

## 3. Classes da conferência (`lote conferir`)
| Classe | Significado | Liberável? | O que fazer |
|---|---|---|---|
| `DENTRO_REFERENCIA` | Hemograma/gasometria/bioquímica dentro da referência, sem resultado anterior | **Sim** | `lote liberar` libera |
| `COERENTE` | De acordo com o resultado anterior (hemo/gaso/bioq dentro da referência; TR/tipagem igual ao anterior) | **Sim** | `lote liberar` libera |
| `PEP_A_CONFIRMAR` | TR/tipagem sem anterior igual (inclusive NR/negativo), ou exame sem referência com trecho no PEP | **Só com `pep_ok`** | Ler o trecho do PEP. Confirma → sigla em `pep_ok`. Não confirma ou não há trecho → não liberar e avisar |
| `FORA_REFERENCIA` | Valor fora da referência | Não | Fica digitado. Avisar com o valor e a referência |
| `QUALITATIVO_ALTERADO` | Qualitativo alterado (REAGENTE/Positivo) | Não | Fica digitado. Avisar |
| `INCOERENTE` | Diverge do anterior (mudança > 50%, passou a crítico, qualitativo diferente) ou o PEP diz o contrário | Não | Fica digitado. Avisar com o motivo; conferir se houve erro de digitação |
| `SEM_REFERENCIA` | Sem referência determinável e sem trecho no PEP | Não | Fica digitado. Avisar |
| `EXTERNO` | Sorologia do DB Diagnósticos | Nunca | Só anexar PDF (`db-anexar`) |
| `SEM_RESULTADO` | Nada salvo no exame | Nunca | Digitar (etapa 2) ou avisar que falta no papel |
| `FORA_DIGITACAO` | Status diferente de 30 | Nunca | Ver `listar`; colocar em Digitação se o usuário pedir |
| `NAO_ENCONTRADO` | Sigla do arquivo não está em Digitação no atendimento | Nunca | Conferir a sigla/atendimento e avisar |
- `pep_ok` só vale para `PEP_A_CONFIRMAR`. Não destrava `FORA_REFERENCIA`, `INCOERENTE`, `QUALITATIVO_ALTERADO`, `SEM_REFERENCIA` nem as classes "nunca".
- Com `historico` (avulso) não há classe: aplique você a mesma tabela lendo os alertas (`AVISO: sem resultado anterior`, `mudança grande`, `passou a faixa crítica`, `AVISO: sem evolução clínica compatível`) e a referência.

Listas de siglas no código (`zion.py`): `SIGLAS_TR_TIPAGEM` (+ qualquer sigla `TR*` e nomes com "teste rápido", "tipagem", "coombs", "fator rh", "grupo/tipo sanguíneo", "vdrl", "sífilis"), `SIGLAS_HEMO`, `GASO_SIGLAS`, `SIGLAS_BIOQUIMICA`, `EXAMES_EXTERNOS_BLOQUEADOS`.

## 4. Referência de comandos
Uso: `python3 zion.py [--user USUARIO] COMANDO ...` (use `python3`). Números de atendimento = `AT`. Decimal com ponto ou vírgula (prefira ponto). `-j N` = atendimentos em paralelo (padrão 4) onde existir.

Legenda: **L** = só leitura · **G** = grava no Tasy · **Local** = só arquivos locais.

| Comando | Tipo | Para quê |
|---|---|---|
| `login` | Local + sessão | valida e grava credenciais; **derruba a outra sessão do usuário** |
| `logout` | Local | apaga credenciais e sessão locais |
| `whoami` | Local | mostra o usuário salvo (nunca a senha) |
| `fila` | L | pendentes por etapa, sem número de atendimento |
| `listar AT` | L | exames de um atendimento por status |
| `digitacao AT [AT...]` | G | leva os exames até Digitação (30) |
| `ler AT [AT...]` | L | lê os valores salvos em Digitação |
| `resultado AT` | G | digita e salva exames por sigla (não libera) |
| `hemo AT` | G | digita e salva hemograma (não libera) |
| `gaso AT` | G | digita e salva gasometria + bioquímica equivalente (não libera) |
| `historico AT [AT...]` | L | resultados anteriores, tendência, PEP (etapa 3) |
| `liberar AT --exame SIGLA` | G | aprova e libera um exame por vez (**não confere nada**) |
| `conferir` | L | audita exames **já liberados (40)**: erros de digitação e críticos |
| `lote digitacao/digitar/conferir/liberar ARQ` | G / G / L / G | as 4 etapas para vários atendimentos |
| `db-login`, `db-logout`, `db-whoami` | Local | acesso ao portal DB Diagnósticos |
| `db-buscar AT` | L | pedido DB × exames do Tasy |
| `db-anexar AT` | G | anexa 1 PDF por exame de sorologia (não libera) |

### `login [--user U] [--password-stdin]`
- Só com autorização do usuário (derruba a outra sessão).
- Senha **sempre** pelo stdin, nunca como argumento:
  ```bash
  python3 zion.py login --user "USUARIO" --password-stdin <<'SENHA'
  a_senha_aqui
  SENHA
  python3 zion.py whoami
  ```
- Também aceita `ZION_USER`/`ZION_PASSWORD` no ambiente, ou `login` interativo (pede usuário e senha sem eco).
- Senha errada: `Login falhou (HTTP 400)`, nada é gravado.
- O usuário pode mandar usuário/senha no chat; use pelo stdin e **nunca** repita a senha.

### `logout` / `whoami`
- `logout`: apaga `credentials.json` e a sessão local.
- `whoami`: mostra só o usuário salvo.

### `fila [--status 10|20|25|26|30] [--exames] [--resumo] [--de D] [--ate D] [--json]` — L
- Pendentes por etapa. Use quando perguntarem "o que tem na fila / quantos pendentes". Não peça número de atendimento.
- `--resumo`: só contagens. `--exames`: lista amostras e exames. `--status 30 --exames`: o que espera digitação.
- `--de`/`--ate`: filtram pela hora da solicitação (`DT_PRESCRICAO`), formato `DD/MM/AAAA` ou `"DD/MM/AAAA HH:MM"`. Padrão: últimos 4 dias.
```bash
python3 zion.py fila --resumo
python3 zion.py fila --status 30 --exames
```

### `listar AT [--de D] [--ate D] [--json]` — L
- Paciente, setor, leito e exames por status/amostra, com a hora da solicitação.

### `digitacao AT [AT ...] [--dry-run] [--desde 10|20|25|26] [--de D] [--ate D] [-j N]` — G
- Leva os exames de status 10/20/25/26 até **30 (Digitação do Resultado)**.
- Vários atendimentos em paralelo.
- `--desde` só funciona com `--dry-run` (simula a partir daquele status).
- Padrão: prescrições dos últimos 4 dias; use `--de`/`--ate` para outras datas.
- Se o Tasy responder algo não mapeado, o CLI para: avise o usuário, não force.
```bash
python3 zion.py digitacao 100001 100002 --dry-run
python3 zion.py digitacao 100001 100002
```

### `ler AT [AT ...] [-j N]` — L
- Mostra os valores salvos dos exames em Digitação. Use para conferir a digitação.

### `resultado AT --exame SIGLA=valor [--exame ...] [--dry-run] [--forcar] [--com-historico] [--sem-historico] [--dump-payload ARQ]` — G
- Digita e **salva** (não aprova, não libera).
- `SIGLA=valor` (campo único) ou `SIGLA.campo=valor` (vários campos; o nome do campo é comparado sem acento/maiúscula, por igualdade ou "contém").
- `--forcar`: sobrescreve campo já preenchido. `--dry-run`: não grava.
- `--com-historico`: compara com histórico/PEP depois de salvar (lento; não use na etapa 2). `--sem-historico`: aceito, não faz nada (já é o padrão).
- `--dump-payload ARQ`: grava o payload (tem dado de paciente; não versionar).
- Recusa sorologia externa (sem override).
```bash
python3 zion.py resultado 100001 --exame UREA=30 --exame CREA=0.43 --exame TGO=53.5 \
  --exame BILI.total=0.73 --exame BILI.direta=0.21 --dry-run
python3 zion.py resultado 100001 --exame GP-TIP.abo=B --exame GP-TIP.rh=Positivo --exame COOD=Negativo
```
Regras por exame (o CLI já aplica):
- **CREA:** se o layout tiver idade e o paciente tiver > 12 anos, preenche idade e eTFG (MDRD 186). `CREA.idade=`/`CREA.etfg=` só para sobrescrever.
- **UREA:** só a parte inteira, truncada (30,56 → 30).
- **BILI:** sem `BILI.indireta`, o CLI calcula total − direta; aceite o valor recalculado pelo sistema.
- **PCR:** como sai no aparelho.
- **Listas/texto** (tipagem, Coombs, aspecto, cor): o valor tem que existir na lista; se o CLI recusar, mostre as opções ao usuário.
- **HIV:** TR1 NÃO REAGENTE → TR2 = NÃO REALIZADO (automático).
- **TRTOXO:** `TRTOXO=NÃO REAGENTE` (ou `NR`/`NEG`) preenche IgG e IgM; se diferentes, `TRTOXO.IgG=` e `TRTOXO.IgM=`.
- **EAS/URN1:** ver seção 7.

### `hemo AT --rbc --hgb --hct --vcm --hcm --chcm --rdw --wbc --neu --lym --mon --eos --bas --plt --vpm [--dry-run] [--forcar] [--hgb-hct-max] [--com-historico] [--sem-historico] [--dump-payload ARQ]` — G
- Hemograma completo. **As 15 opções são obrigatórias**, valores como no impresso.
- `--wbc` em 10³/µL (14.06); `--plt` em 10⁹/L (174 → 174.000); diferencial em %: `--neu` = segmentados.
- Percentuais arredondados fechando 100; regra de eosinófilos/bastonetes mínimos (1.5 item 7) automática.
- `--hgb-hct-max`: se a gasometria do atendimento já estiver salva, grava o maior HGB/HCT nos dois (só regrava exame em status 30; nunca liberado). Sem a flag, o CLI só avisa a divergência.
```bash
python3 zion.py hemo 100001 --rbc 4.04 --hgb 13.3 --hct 36 --vcm 89.1 --hcm 32.8 --chcm 36.9 --rdw 12.6 \
  --wbc 14.06 --neu 82.1 --lym 11.9 --mon 5.6 --eos 0.3 --bas 0.1 --plt 174 --vpm 11.7 --dry-run
```

### `gaso AT [--ph --pco2 --po2 --hco3 --be --so2 --hb --hct --na --k --ica --cl --glu --lac --bil] [--obs TEXTO] [--dry-run] [--forcar] [--hgb-hct-max] [--com-historico] [--sem-historico] [--dump-payload ARQ]` — G
- Gasometria (GASV, GASA, GASO, GAS). Informe pelo menos um campo.
- Preenche também a bioquímica equivalente **só se o exame existir na mesma prescrição**: `--na`→NA+, `--k`→K+, `--ica`→CAI/CAIO, `--cl`→CL, `--glu`→GLI/GLIC/GLICO, `--lac`→LAC/LACT/LACTATO.
- Campo com erro no aparelho ("Instabilidade" etc.): não envie (fica em branco).
- `--hgb-hct-max`: igual ao `hemo`.
```bash
python3 zion.py gaso 100001 --ph 7.458 --pco2 36.9 --po2 52.4 --hco3 26.4 --be 2.3 --so2 88.5 \
  --hb 13.5 --hct 41 --na 136.1 --k 5.13 --obs venosa --dry-run
```

### `historico AT [AT ...] [--exame SIGLA ...] [--dias 90] [--notas 1] [--json] [-j N]` — L
- Etapa 3 avulsa. Para cada exame em Digitação (ou o liberado mais recente, se não houver): resultados anteriores de **todos** os atendimentos do paciente, tendência, Δ e trechos do PEP (evoluções clínicas, médicas/UTI primeiro).
- Alertas: `mudança grande vs último` (> 50%), `passou a faixa crítica`, `AVISO: sem resultado anterior`, `AVISO: sem evolução clínica compatível`.
- `--dias`: janela (padrão 90). `--notas`: nº de evoluções mostradas por grupo (padrão 1).
```bash
python3 zion.py historico 100001 100002
python3 zion.py historico 100001 --exame VDRL --exame HIV --notas 3
```

### `liberar AT --exame SIGLA [--exame SIGLA ...] [--dry-run]` — G
- Aprova (status 35) e libera (status 40) **um exame por vez**, como na tela (aprovar → liberar → reler). Nunca "Liberar todos".
- ⚠️ **Não faz conferência.** Só recusa: sorologia externa, status ≠ 30, exame sem resultado. **Você** precisa ter rodado e lido a etapa 3 e aplicado a regra 1.4 antes.
- Vários `--exame`: processados um de cada vez; no primeiro aviso/erro/consistência o CLI **para** e não segue.
- Ficou em 35 (aprovado, não liberado): avise o usuário para conferir na tela.
```bash
python3 zion.py liberar 100001 --exame CREA --dry-run
python3 zion.py liberar 100001 --exame CREA
```

### `conferir [--de D] [--ate D] [--at AT [AT ...]] [--json] [--sem-historico] [--dias 90] [-j N]` — L
- **Só exames já liberados (status 40).** Não é a etapa 3 de pendentes. Use quando pedirem "conferir liberados / resultados críticos / erros de digitação nas liberações".
- Padrão: hoje 00:00 até agora (pela hora da solicitação). Ignora exames da mesma prescrição que não estão em 40.
- Aponta **possível erro de digitação** (escala ×10/×100/×1000, EAS inconsistente, leucograma ≠ 100%, Hb/Ht/CHCM/VCM incoerentes, BD > BT, pH fora de 6,8–7,8, campo zerado, eTFG vazia…) e **resultado crítico** (Hb < 7; PLT < 50 mil ou > 1 milhão; leucócitos < 2 mil ou > 30 mil; K < 2,8 ou > 6,2; Na < 120 ou > 160; glicose < 50 ou > 400; pH < 7,20 ou > 7,60; etc. — tabelas `PLAUS_BOUNDS` e `CRITICO_BOUNDS`).
- Reporte todos os achados. Não corrija nada sozinho.
```bash
python3 zion.py conferir
python3 zion.py conferir --at 100001 100002
```

### `lote ETAPA ARQ [--dry-run] [--dias 90] [-j N]`
| Etapa | Tipo | Faz |
|---|---|---|
| `digitacao` | G | `digitacao` de todos os `at` |
| `digitar` | G | para cada `at`: `resultado` → `hemo` → `gaso`, sem histórico; unifica HGB/HCT (maior) se houver `hemo` e `gaso` |
| `conferir` | L | classifica cada exame do arquivo (seção 3); grava `ARQ.conferencia.json` (permissão 600) |
| `liberar` | G | exige conferência de ≤ 60 min; libera só `COERENTE`, `DENTRO_REFERENCIA` e `PEP_A_CONFIRMAR` com `pep_ok`; um exame por vez; resumo único |
- `--dry-run` vale para `digitacao`, `digitar` e `liberar`.
- Atendimentos rodam em paralelo; um com erro não para os outros; saída agrupada por atendimento.
- `lote conferir`/`liberar` só olham as siglas que estão no arquivo (hemo = HC; gaso = exames de gasometria).

### `db-login --cpf CPF --password-stdin [--serv-sol N] [--otp CODIGO]`, `db-logout`, `db-whoami` — Local
- Acesso ao portal E-DB (DB Diagnósticos). Grava em `~/.config/zion-cli/db_credentials.json` (600).
- Senha pelo stdin. Nunca repita CPF/senha. `db-whoami` mostra o CPF mascarado.
- Se o portal pedir 2 fatores, rode de novo com `--otp`.

### `db-buscar AT [--chave X] [--pedido N] [--de D] [--ate D] [--json]` — L
- Mostra o pedido do DB, o status de cada exame lá, os exames do Tasy em Digitação e anexos existentes.

### `db-anexar AT [--exame SIGLA ...] [--dry-run] [--substituir] [--chave X] [--pedido N] [--de D] [--ate D] [--salvar-pdf PASTA]` — G
- Baixa o laudo de **cada** exame e anexa **só no exame certo** (1 PDF por exame; nunca PDF combinado). **Não libera.**
- Recusa PDF com nome de paciente diferente ou com outro exame. Exame precisa estar em status 30.
- Exame que já tem anexo é pulado; `--substituir` troca o anexo.
- Sempre `--dry-run` primeiro.
```bash
python3 zion.py db-buscar 100001
python3 zion.py db-anexar 100001 --dry-run
python3 zion.py db-anexar 100001 --exame TOXG
```

## 5. Status dos exames
| Código | Significado | Observação |
|---|---|---|
| 10 | Pendente coleta | `digitacao` move |
| 20 | Material coletado | `digitacao` move |
| 25 | Em análise | `digitacao` move |
| 26 | Interfaceamento | `digitacao` move |
| 30 | Digitação do resultado | único status em que se digita, anexa e libera |
| 35 | Aprovado (não liberado) | estado intermediário do `liberar`; se ficar aqui, avisar |
| 40 | Exame liberado | final; só `conferir` olha; não corrigir sozinho |

## 6. Variáveis de ambiente
| Variável | Para quê |
|---|---|
| `ZION_URL`, `ZION_PROFILE`, `ZION_SETOR` | instalação, perfil e setor (padrões no `.env.example`) |
| `ZION_USER`, `ZION_PASSWORD` | login não interativo (nunca imprimir) |
| `ZION_CONFIG_DIR` | outra pasta de credenciais/sessão (testes) |
| `ZION_TIMING=1` | no fim, imprime (stderr) tempo por serviço HTTP; sem dados de paciente |
| `ZION_BUILD_WORKERS=N` | leituras paralelas dentro de um atendimento (padrão 4; `1` desliga) |
| `DB_CPF`, `DB_PASSWORD` | alternativa ao `db-login --cpf/--password-stdin` |
- `-j N` (em `digitacao`, `ler`, `historico`, `conferir`, `lote`): atendimentos em paralelo (padrão 4).

## 7. EAS / Urina rotina (URN1)
- Sempre `--forcar` (o modelo vem com valores "normais" preenchidos).
- Sedimento: no papel "13.000/mL" = campo simples **13** e campo (x1000) **13000**. Use os aliases e o CLI grava o par certo: `URN1.celulas=13000`, `URN1.leucocitos_ml=2000`, `URN1.hemacias=21000`.
- `URN1.Leucócitos` (sem sufixo) é a **fita** (Ausente/+/++/+++/++++).
- Cruzes: mande o texto exato (`++`) ou `2+`/`+2`. `ausente`/`negativo`/`-` → Ausente/Negativo.
- Listas (aspecto, cor…): aceita sem acento; se não casar, o CLI lista as opções e não grava.
- Campo que não está no papel: não envie.
```bash
python3 zion.py resultado 100001 --forcar --dry-run --exame "URN1.Cor=Amarelo claro" \
  --exame "URN1.Aspecto=ligeiramente turvo" --exame URN1.Densidade=1010 --exame URN1.pH=6 \
  --exame URN1.Hemoglobina=++ --exame URN1.celulas=13000 --exame URN1.leucocitos_ml=2000 --exame URN1.hemacias=21000
```
- Confira a releitura: `Hemácias: 21 | x1000: 21000 (=21.000/mL)`.

## 8. Sessão e velocidade
- A sessão fica salva e é renovada sozinha (refresh). Em lote, o processo principal valida a sessão uma vez antes dos workers.
- Gravações (`digitacao`, `resultado`, `hemo`, `gaso`, `liberar`) são sequenciais dentro de um atendimento; atendimentos diferentes rodam em paralelo.
- A etapa 2 não roda histórico/PEP (é o que deixava lento). Não acrescente `--com-historico` na etapa 2.
- Gargalos conhecidos: `digitacao` (~20 chamadas por amostra), `liberar` (~1,4 s de PDF por exame), `historico` sem série no gráfico.

## 9. Arquivos locais (nunca versionar)
| Arquivo | Conteúdo |
|---|---|
| `~/.config/zion-cli/credentials.json` | usuário/senha do Tasy (600) |
| `~/.config/zion-cli/session.json` | sessão do Tasy |
| `~/.config/zion-cli/db_credentials.json` | CPF/senha do portal DB (600) |
| `~/.config/zion-cli/db_session.json` | sessão do portal DB |
| `~/.config/zion-cli/db_siglas.json` | (opcional) siglas DB → Tasy extras |
| `lote*.json`, `*.conferencia.json`, `*.pdf`, `*.har`, `payload*.json` | dados de paciente/tokens |
Windows: `%APPDATA%\zion-cli\`.

## 10. Problemas comuns
| Sintoma | Causa | O que fazer |
|---|---|---|
| `401` / `User context not found` / "sessão salva do Tasy foi encerrada no servidor" | outro login derrubou a sessão | **Pare.** Avise o usuário e peça autorização para `login` (derruba a sessão dele). Depois repita o comando |
| `Login falhou (HTTP 400)` | usuário/senha errados | peça os dados de novo ao usuário |
| `não existe neste atendimento` / `NAO_ENCONTRADO` | sigla errada ou exame não está em 30 | `listar AT`; avise |
| `não está em Digitação` / `FORA_DIGITACAO` | status ≠ 30 | `digitacao AT` (se pedido) |
| `já tem valor diferente salvo ... (use --forcar)` | campo já preenchido | só use `--forcar` se o usuário pediu correção |
| `(opções: ...)` | valor não existe na lista | mostre as opções ao usuário |
| `DIVERGÊNCIA` na releitura | o Tasy gravou outro valor | `ler AT`; avise |
| `bloqueado` / sorologia | exame externo | `db-anexar`; nunca digitar |
| `Conferência de N min atrás` | conferência > 60 min | `lote conferir` de novo |
| `liberar` parou em 35 ou com consistência | aviso do Tasy | avise; não insista |

## 11. Erros proibidos (já aconteceram)
1. **Liberar sem conferir** com resultados anteriores/PEP (sem rodar ou sem ler `historico`/`lote conferir`).
2. **Liberar teste rápido ou tipagem** sem resultado anterior igual ou confirmação lida no PEP — inclusive NR/negativo.
3. **Pôr sigla em `pep_ok` sem ter lido** o trecho do PEP que confirma.
4. **Digitar incompleto ou bagunçado:** pular exames do papel, trocar valores entre exames/atendimentos, HGB/HCT diferentes entre hemograma e gasometria.
5. **Inventar ou "corrigir" valor** que não está no papel; digitar valor ilegível.
6. **Misturar etapas** (fazer um atendimento inteiro de cada vez) ou fazer etapa que o usuário não pediu (conferir/resumo quando só pediu digitação).
7. **Rodar histórico/PEP na etapa 2** (`--com-historico`), deixando a digitação lenta.
8. **Usar `conferir`** (liberados) achando que é a conferência de pendentes.
9. **Digitar sorologia** ou anexar PDF combinado.
10. **Logar sem autorização** (derruba a sessão do usuário) ou expor senha/CPF/dados de paciente.
