# zion-tasy-cli

CLI em Python para operar o módulo de Laboratório do **Zion / Philips Tasy 5.04** (web) sem navegador:
colocar exames em Digitação, digitar e salvar resultados (bioquímica, hemograma, gasometria, testes rápidos, EAS),
conferir com resultados anteriores e PEP, liberar um exame por vez, anexar laudos do DB Diagnósticos e auditar os exames liberados.

> **IAs:** as regras abaixo são obrigatórias. `AGENTS.md` e `CLAUDE.md` têm o mesmo conteúdo.

## Instalação e primeiro uso
```bash
python3 -m pip install -r requirements.txt   # só precisa de requests
python3 zion.py login                         # pede usuário e senha (sem eco), grava em ~/.config/zion-cli/
python3 zion.py whoami
python3 zion.py fila --resumo
python3 zion.py referencias                   # confere a tabela de referência em uso (deve mostrar 50+ exames)
```
- **Sempre rode o zion.py de dentro do clone** (`git pull` antes de trabalhar). Ele lê `referencias.json` e `templates.json` da pasta real do script (symlink em `~/bin` funciona). Copiado sozinho para outro lugar, ele avisa com `!!! ATENÇÃO` e usa a cópia da tabela embutida no próprio zion.py.
- URL, perfil e setor padrão estão no `.env.example`. Não há usuário fixo no repositório.
- `pdftotext` (poppler-utils) é necessário só para `db-anexar`.

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
3. O `liberar` **sempre confere sozinho** antes de aprovar (mesma classificação do `lote conferir`, feita na hora: referência, resultados anteriores e PEP). Só libera `DENTRO_REFERENCIA` e `COERENTE`; `PEP_A_CONFIRMAR` só com `--pep-ok SIGLA`. Qualquer outra classe: **nada é aprovado** e sai com código 1. Não existe opção para pular essa conferência.
4. Mesmo assim, **leia** a conferência que o `liberar` imprime e informe o usuário. `--pep-ok` só depois de ler o trecho do PEP e ele confirmar.
5. Conferência do lote com mais de 60 min não vale: rode `lote conferir` de novo.

### 1.4 Regras de liberação

> **O que está liberável DEVE ser liberado.** Quando o usuário pediu para liberar (ou o fluxo completo), todo exame que a conferência classificou como **`DENTRO_REFERENCIA` ou `COERENTE`** **deve** ser liberado com `python3 zion.py liberar AT --exame SIGLA` (ou `lote liberar ARQ`). **Não precisa de PEP nem de resultado anterior** para isso: a referência (Tasy + tabela do laboratório, seção 3A) basta. Não deixe exame liberável parado "por cautela". Digitar e conferir **não** liberam nada.
> - `--pep-ok` é só para `PEP_A_CONFIRMAR`. Nas outras classes não liberáveis, deixe digitado e avise o usuário com o motivo que o CLI imprimiu.
> - Antes de liberar, a primeira linha do `liberar`/`lote conferir` deve mostrar `Tabela de referência: .../referencias.json (50 exames)`. Se aparecer `EMBUTIDA` ou `!!! ATENÇÃO`, faça `git pull` no clone e rode de lá.

| Tipo de exame | Libera quando | Senão |
|---|---|---|
| **Testes rápidos** (HIV, VDRL, TRS/sífilis, hepatites TR, TRTOXO, qualquer sigla `TR*`) e **tipagem / fator Rh / Coombs** (GP-TIP, TIP, ABO, COOI, COOD, CI, CD) | Resultado anterior **igual** **ou** confirmação lida no PEP. Vale também para NÃO REAGENTE / Negativo. | Só digitar e salvar. Não liberar. Avisar o usuário. |
| **Hemograma, gasometria, bioquímica** (HC, GASV/GASA, CREA, UREA, NA+, K+, TGO, PCR, TAP…) | Dentro da referência (Tasy e tabela do laboratório, seção 3A), mesmo sem resultado anterior e sem PEP. | Fora da referência ou incoerente com o anterior/PEP: só digitar e salvar. Não aprovar, não liberar. Avisar o usuário. |
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
python3 zion.py liberar 100001 --exame CREA --dry-run   # confere de novo e mostra a decisão, sem liberar
python3 zion.py liberar 100001 --exame CREA           # etapa 4: confere e só libera se for liberável
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
| `CAMPO_PENDENTE` | Falta preencher campo que o Tasy usa para calcular (ex.: Idade da creatinina em ≥ 18 anos → eTFG não calculado) | Não | Avisar; preencher o campo (etapa 2) e conferir de novo |
| `REF_DIVERGENTE` | Faixa do Tasy e tabela do laboratório (`referencias.json`) discordam para este valor | Não | Fica digitado. Avisar com as duas faixas (seção 3A) |
| `QUALITATIVO_ALTERADO` | Qualitativo alterado (REAGENTE/Positivo) | Não | Fica digitado. Avisar |
| `INCOERENTE` | Diverge do anterior (mudança > 50%, passou a crítico, qualitativo diferente) ou o PEP diz o contrário | Não | Fica digitado. Avisar com o motivo; conferir se houve erro de digitação |
| `SEM_REFERENCIA` | Sem referência determinável e sem trecho no PEP | Não | Fica digitado. Avisar |
| `EXTERNO` | Sorologia do DB Diagnósticos | Nunca | Só anexar PDF (`db-anexar`) |
| `SEM_RESULTADO` | Nada salvo no exame | Nunca | Digitar (etapa 2) ou avisar que falta no papel |
| `FORA_DIGITACAO` | Status diferente de 30 | Nunca | Ver `listar`; colocar em Digitação se o usuário pedir |
| `NAO_ENCONTRADO` | Sigla do arquivo não está em Digitação no atendimento | Nunca | Conferir a sigla/atendimento e avisar |
- `pep_ok` só vale para `PEP_A_CONFIRMAR`. Não destrava `FORA_REFERENCIA`, `REF_DIVERGENTE`, `CAMPO_PENDENTE`, `INCOERENTE`, `QUALITATIVO_ALTERADO`, `SEM_REFERENCIA` nem as classes "nunca".
- Com `historico` (avulso) não há classe: aplique você a mesma tabela lendo os alertas (`AVISO: sem resultado anterior`, `mudança grande`, `passou a faixa crítica`, `AVISO: sem evolução clínica compatível`) e a referência.

Listas de siglas no código (`zion.py`): `SIGLAS_TR_TIPAGEM` (+ qualquer sigla `TR*` e nomes com "teste rápido", "tipagem", "coombs", "fator rh", "grupo/tipo sanguíneo", "vdrl", "sífilis"), `SIGLAS_HEMO`, `GASO_SIGLAS`, `SIGLAS_BIOQUIMICA`, `EXAMES_EXTERNOS_BLOQUEADOS`.

## 3A. Valores de referência (Tasy + tabela do laboratório)
A conferência (`liberar`, `lote conferir`, `historico`) decide "dentro/fora da referência" assim, campo a campo:
1. **Faixa do Tasy:** `qtMinima`/`qtMaxima` (ou `prMinimo`/`prMaximo`) do campo. Campo numérico sem nenhuma delas: usa o texto da referência do Tasy se tiver **uma** faixa clara "A a B" na mesma escala do valor (ex.: Hct "37% a 47%"; aviso na saída).
2. **Tabela do laboratório (DB Diagnósticos):** arquivo `referencias.json`, ao lado do `zion.py` (pasta real do script; também `ZION_REFERENCIAS`, diretório atual ou `~/.config/zion-cli/`). Sem o arquivo, usa a **cópia embutida** no zion.py com aviso `!!! ATENÇÃO`. `python3 zion.py referencias` mostra qual está em uso. Ao editar o JSON, rode `python3 zion.py referencias --embutir` e faça commit dos dois. Faixas por **sexo** e **idade na data da coleta** (dias/meses/anos completos), calculadas pela data de nascimento e pelo sexo do paciente no Tasy.
3. **Como combina:**
   | Situação | Resultado |
   |---|---|
   | Tasy tem faixa e a tabela tem faixa | o valor precisa estar dentro das **duas**. As duas dizem dentro → dentro; as duas dizem fora → `FORA_REFERENCIA`; uma diz dentro e a outra fora → **`REF_DIVERGENTE`** (não libera; mostra as duas faixas) |
   | Só a tabela tem faixa | usa a tabela |
   | Só o Tasy tem faixa (tabela sem faixa para o sexo/idade, ou exame fora da tabela) | usa o Tasy |
   | Nenhuma das duas, ou sexo/idade desconhecidos e a faixa depende deles | `SEM_REFERENCIA` (não libera) |
   | Exame com `"prioridade": "tabela"` no `referencias.json` (hoje: **creatinina**) | vale **só a tabela**; a faixa do Tasy aparece como "só informativo" e nunca gera `REF_DIVERGENTE`. Sem faixa na tabela (sexo/idade desconhecidos) → `SEM_REFERENCIA` |
   | Unidade do campo no Tasy diferente da tabela | a tabela é **ignorada** naquele campo (aviso na saída). Unidade vazia ou "." no Tasy: procura a unidade no texto da referência; se não achar, usa a da tabela e avisa. mEq/L = mmol/L (Na, K); µg/dL = ug/dL |
4. Faixa do Tasy vazia ou **"0,00 a 0,00"** (mínimo e máximo zero/ausentes) = **sem faixa no Tasy** → vale a tabela.
5. Campo numérico **= 0**, sem faixa no Tasy e fora da tabela:
   - **campo auxiliar** (nome com volume, diurese, peso, altura, idade, tempo de coleta, período, 24h) = campo vazio: ignorado, só aparece como nota (ex.: "Volume Ácido Úrico" no soro);
   - **célula que normalmente é 0** no hemograma (blastos, promielócitos, mielócitos, metamielócitos, atípicos) = normal (dentro);
   - **qualquer outro 0** (eosinófilos, bastonetes, plaquetas, HCO3, Hct, cálcio iônico...) **NÃO é ignorado**: fica `SEM_REFERENCIA` ("valor 0 sem referência — confira").
   Campo com valor diferente de 0 e sem referência continua `SEM_REFERENCIA`.
6. EAS (URN1): o campo simples do sedimento (Células epiteliais, Leucócitos (Piócitos), Hemácias) é só a cópia do par; vale a faixa do campo **(x1000)**. Sem o (x1000) preenchido, o simples sem faixa bloqueia.
7. **Hemograma (HC):** entradas `hc_*` do `referencias.json` (laudo oficial do laboratório), com `"prioridade": "tabela"` — a faixa do Tasy no HC só aparece como informativa (ela diverge do laudo, ex.: HCM do RN 30–36 no Tasy × 27–31 no laudo; plaquetas 150–450 em mil no Tasy). Percentual e absoluto separados pela unidade do campo; "Leucócitos" (em mil) e "Leucócitos Totais" (absoluto) avaliados cada um na sua escala; plaquetas gravadas em mil (< 2000) são comparadas ×1000. Faixas por sexo (série vermelha adulta/infantil ≥ 3 anos, VPM) → sexo desconhecido = `SEM_REFERENCIA`. Blastos, promielócitos, mielócitos, metamielócitos, prolinfócitos, células imaturas, atípicos/reativos não têm faixa: 0 = normal, outro valor trava. Criança < 15 anos: o laudo pede bastonetes ≥ 2% e eosinófilos ≥ 4% (até 15 anos) — bastão 0 ou eos baixo sai `FORA_REFERENCIA`.
6. A saída mostra a faixa usada e a fonte, por exemplo `Creatinina 0.8 (ref 0.6–1.1 mg/dL (tabela DB, F 30 anos); Tasy 0.31–0.92)`.

**Exames na tabela** (sigla do Tasy neste hospital → faixa): Ácido úrico `AURS`; Ureia `UREA`; Creatinina `CREA`; Bilirrubina total/direta/indireta `BILI` (campos); TGO `TGO`; TGP `TGP`; Gama GT `GGT`; PCR `PCRP` (só se a unidade for mg/L); DHL `LDH2`; Albumina `ALBU`; Fosfatase alcalina `FAL`; Fósforo `P+`; Ferro `FERO`; Cálcio total `CA+`; Magnésio `MG+`; Lipase `LIPA`; Amilase `AMIL`; Lactato `LACT`; Sódio `NA+`; Potássio `K+`; Glicose `GLI`; Colesterol total, HDL, Triglicérides, CPK (por sigla/nome quando existirem). Na gasometria (GASV/GASA): Na, K, glicose e lactato pelo nome do campo.

**Decisões de interpretação** (editáveis no `referencias.json`):
- Limites de idade: `de` inclusivo, `ate` exclusivo, em idade completa. Ex.: "18–60 anos" = 18 a 60 anos completos; "61–90" = 61 a 90; ">90" = 91 ou mais. "RN até 4 dias" = 0 a 4 dias; "5 dias–3 anos" = 5 dias a 3 anos completos.
- "Inferior a X" = valor < X (X já é fora). "Superior a X" (HDL) = valor > X.
- Creatinina: vale a tabela do laboratório (prioridade sobre o Tasy); mulher 18–60 anos: 0,60–1,10. Glicose: 70–99 (jejum). Triglicérides: limite **com jejum**. PCR: < 5,00 mg/L.
- Lactato: venoso 0,5–2,2 / arterial 0,5–1,6, pelo exame (GASV/GASA) ou pelo nome/material ("arterial"/"venoso"); sem identificação → arterial (mais restrito).
- Bilirrubina direta < 0,20 e indireta < 1,10 em qualquer idade (no recém-nascido a indireta quase sempre sai fora → fica só digitado).
- Ureia < 1 ano: 9–41 para todos (a faixa "prematuro 6–54" não é usada: o CLI não sabe se é prematuro; 9–41 é mais restrita).
- Ferro: RN = até 27 dias; criança < 7 anos = 28 dias a 6 anos; criança > 7 anos = 7 a 17 anos; adulto (homem/mulher) = 18 anos ou mais.
- Colesterol, HDL e triglicérides: adulto = 20 anos ou mais.
- Cálcio: < 1 ano; 1–18 anos; 19 anos ou mais. Magnésio: 0–4 meses (inclui < 1 mês) 1,5–2,2; 5 meses–5 anos; 6–12 anos; 13 anos ou mais = faixa adulta 1,7–2,4.
- Sódio: 136–145 até 90 anos (inclui < 18 anos); 91 anos ou mais: 132–146.
- Fosfatase alcalina: adulto (19 anos ou mais) 30–120 para homem e mulher.
- **eTFG da creatinina:** paciente < 18 anos → eTFG 0/vazio é esperado (conta como dentro). Paciente ≥ 18 anos → o Tasy calcula o eTFG quando o campo **Idade** da creatinina está preenchido; eTFG 0/vazio = `CAMPO_PENDENTE` (não libera; preencha a Idade). eTFG com valor → avaliado pela referência do Tasy (≥ 60). Idade desconhecida → não libera.

**Como acrescentar ou mudar uma referência:** edite `referencias.json` (sem dado de paciente) nos dois repositórios:
```json
{"id": "exemplo", "nome": "Nome do exame", "siglas": ["SIGLA_DO_TASY"], "nomes": ["palavradonomedoexame"],
 "excluir": ["urina"], "campo": [], "unidade": "mg/dL",
 "faixas": [{"sexo": "M", "de": "18a", "ate": "61a", "min": 1.0, "max": 2.0},
            {"sexo": "F", "de": "18a", "min": 0.5, "max_excl": true, "max": 1.5}]}
```
- `siglas`: CD_EXAME do Tasy. `nomes`: pedaço do nome do exame sem acento/espaço (usado se a sigla não bater). `excluir`: palavras no nome/material/campo que impedem o uso (urina, clearance…).
- `campo`: para exame com vários campos (ex.: `["direta"]`); vazio = campo principal. `campo_excluir`: palavras que o campo não pode ter. `gaso`: nome do campo dentro da gasometria.
- Faixa: `sexo` M/F (sem = ambos); `de`/`ate` com `d`, `m` ou `a`; `min`/`max` inclusivos; `min_excl`/`max_excl` = estrito. `material` só para venoso/arterial.
- `"prioridade": "tabela"`: a tabela vence o Tasy naquele exame (o Tasy fica só informativo). Sem esse campo, Tasy e tabela precisam concordar.
- A primeira faixa que servir é usada. Teste com `historico AT` ou `liberar AT --exame SIGLA --dry-run`.

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
| `liberar AT --exame SIGLA` | G | confere na hora (referência/anteriores/PEP) e só então aprova e libera, um exame por vez. `DENTRO_REFERENCIA`/`COERENTE` **devem** ser liberados (sem PEP) |
| `referencias [--embutir]` | L | sem Tasy: mostra a tabela de referência em uso e de onde veio |
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

### `liberar AT --exame SIGLA [--exame SIGLA ...] [--pep-ok SIGLA ...] [--dias 90] [--dry-run]` — G
1. **Primeiro confere** (só leitura), na hora, cada exame pedido: mesma classificação do `lote conferir` (seção 3) — referência, resultados anteriores e PEP. Imprime para cada exame: classe, motivo, valores, campos dentro/fora da referência, resultados anteriores, incoerências e trechos do PEP, e a **decisão** (LIBERÁVEL / RECUSADO).
2. Liberável: `DENTRO_REFERENCIA`, `COERENTE`, e `PEP_A_CONFIRMAR` **só** se a sigla vier em `--pep-ok`.
3. Testes rápidos, tipagens e Coombs **nunca** passam só pela referência: precisam de resultado anterior igual (`COERENTE`) ou `--pep-ok`.
4. Se **qualquer** exame pedido for recusado: **nada** é aprovado, o CLI imprime `Resumo: SIGLA: recusado na conferência (CLASSE)` e sai com código 1.
5. Se todos forem liberáveis: aprova (35) e libera (40) **um exame por vez**, como na tela; no primeiro aviso/erro/consistência para e não segue. Nunca "Liberar todos".
6. `--dry-run`: faz a conferência e mostra a decisão, sem aprovar nem liberar.
7. `--pep-ok SIGLA`: você atesta que **leu** o trecho do PEP e ele confirma o resultado. Nunca use "por garantia". Não destrava `FORA_REFERENCIA`, `REF_DIVERGENTE`, `CAMPO_PENDENTE`, `INCOERENTE`, `QUALITATIVO_ALTERADO`, `SEM_REFERENCIA`, `EXTERNO`, `SEM_RESULTADO`, `FORA_DIGITACAO`, `NAO_ENCONTRADO`.
8. Não existe opção para pular a conferência.
- Ficou em 35 (aprovado, não liberado): avise o usuário para conferir na tela.
```bash
python3 zion.py liberar 100001 --exame CREA --dry-run
python3 zion.py liberar 100001 --exame CREA
python3 zion.py liberar 100002 --exame HIV --pep-ok HIV   # só depois de LER o PEP e ele confirmar
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
| `liberar` | G | exige conferência de ≤ 60 min; libera só `COERENTE`, `DENTRO_REFERENCIA` e `PEP_A_CONFIRMAR` com `pep_ok` (passado como `--pep-ok`); cada `liberar` ainda **refaz a conferência na hora** e recusa o que mudou; um exame por vez; resumo único |
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
| Nenhum exame liberado / quase tudo `SEM_REFERENCIA` | clone antigo (sem `referencias.json` atualizado) ou zion.py copiado sozinho | `git pull` no clone; `python3 zion.py referencias` deve mostrar o arquivo do clone e 50+ exames. Hemograma de criança < 15 anos com bastonetes < 2% ou eosinófilos < 4% sai `FORA_REFERENCIA` (laudo): avise o usuário |
| `recusado na conferência (CLASSE)` | exame não liberável pela regra 1.4 | deixe digitado e avise o usuário com o motivo; `--pep-ok` só se a classe for `PEP_A_CONFIRMAR` e você leu o PEP confirmando |

## 11. Erros proibidos (já aconteceram)
1. **Liberar sem conferir** com resultados anteriores/PEP (sem rodar ou sem ler `historico`/`lote conferir`).
2. **Liberar teste rápido ou tipagem** sem resultado anterior igual ou confirmação lida no PEP — inclusive NR/negativo.
3. **Pôr sigla em `pep_ok` / `--pep-ok` sem ter lido** o trecho do PEP que confirma.
4. **Digitar incompleto ou bagunçado:** pular exames do papel, trocar valores entre exames/atendimentos, HGB/HCT diferentes entre hemograma e gasometria.
5. **Inventar ou "corrigir" valor** que não está no papel; digitar valor ilegível.
6. **Misturar etapas** (fazer um atendimento inteiro de cada vez) ou fazer etapa que o usuário não pediu (conferir/resumo quando só pediu digitação).
7. **Rodar histórico/PEP na etapa 2** (`--com-historico`), deixando a digitação lenta.
8. **Usar `conferir`** (liberados) achando que é a conferência de pendentes.
9. **Digitar sorologia** ou anexar PDF combinado.
10. **Logar sem autorização** (derruba a sessão do usuário) ou expor senha/CPF/dados de paciente.

## templates.json
Modelos dos payloads das telas do Tasy, extraídos de capturas HAR e **sanitizados** (números de atendimento, prescrição, amostra e paciente anulados; o CLI preenche em tempo de execução). Para outra versão do Tasy pode ser preciso recapturar; apague o HAR depois (tem tokens).

## Licença
Ver `LICENSE`.
