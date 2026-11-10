# zion-tasy-cli

## 🔐 Login: a IA pode fazer pela pessoa

- A pessoa pode mandar o **usuário e a senha direto no chat** da IA. Não precisa de formulário nem campo seguro.
- A IA usa os dois direto, passando a senha **pelo stdin** (nunca como argumento):
  ```bash
  python3 zion.py login --user "USUARIO" --password-stdin <<'SENHA'
  a_senha_aqui
  SENHA
  # ou: printf '%s' 'a_senha_aqui' | python3 zion.py login --user "USUARIO" --password-stdin
  ```
- Depois de logar, a IA confere com `python3 zion.py whoami`.
- O CLI valida no Zion e grava em `~/.config/zion-cli/credentials.json` (permissão 600). As credenciais ficam **só** nesse arquivo protegido.
- A IA **não** repete a senha nas respostas, **não** grava a senha em arquivos do repositório nem em logs e **não** faz commit dela.
- Continuam valendo: variáveis `ZION_USER`/`ZION_PASSWORD` (`printf '%s' "$ZION_PASSWORD" | python3 zion.py login --user "$ZION_USER" --password-stdin`) e o `python3 zion.py login` interativo no terminal.
- Senha errada: o CLI sai com `Login falhou (HTTP 400): ...`, sem mostrar a senha e sem gravar nada.
- Trocar de usuário: `python3 zion.py logout` e depois `login` de novo.

> **Nota:** a senha enviada no chat fica no histórico da conversa. Recomenda-se trocá-la periodicamente.


> **Para IAs e usuários:** URL, perfil e setor padrão já estão em `.env.example`. Na **primeira vez**, rode `python3 zion.py login` — o CLI pede usuário e senha, valida e grava em `~/.config/zion-cli/credentials.json` (não precisa digitar de novo). IAs/CI: exporte `ZION_USER` e `ZION_PASSWORD`. Leia `AGENTS.md` antes de operar. Fila: `python3 zion.py fila --resumo`.


CLI em Python para operar o módulo de Laboratório do **Zion / Philips Tasy 5.04** (web) sem navegador. Com ele você:

- coloca atendimentos em **Digitação do Resultado**;
- digita e **salva** resultados (bioquímica, campos com várias partes, listas/texto, gasometria e hemograma);
- relê os valores depois de salvar e compara com o que foi enviado;
- **confere** todos os exames liberados do dia (erros de digitação e resultados críticos) — só leitura.

> ⚠️ O CLI **nunca libera** resultado. Ele só salva. Quem libera/laudo é sempre o profissional, pelo sistema.

> ⚠️ **sorologia ≠ teste rápido.** Sorologias (Toxoplasmose IgG/IgM, Anti-HCV, HBsAg, CMV, Rubéola, Sorologia HIV 1/2, etc.) vão para **laboratório externo** — o CLI **recusa** qualquer digitação nelas (nem `--forcar` libera). Testes rápidos (`TRTOXO`, `HIV`, `TRS`, `TRHCV`, …) continuam normais.

## Instalação

```bash
python3 -m pip install -r requirements.txt   # só precisa de requests
```

## Primeiro uso / trocar de usuário

1. `pip install -r requirements.txt`
2. Na primeira vez (ou para trocar de conta):
   ```bash
   python3 zion.py login
   ```
   O CLI pede **usuário** e **senha** (a senha não ecoa), valida no Zion, escolhe o perfil (usa o padrão do `.env.example` ou o único disponível; se houver vários e o padrão não existir, lista e pergunta) e grava tudo em:
   - Linux/macOS: `~/.config/zion-cli/credentials.json` (permissão `600`)
   - Windows: `%APPDATA%\zion-cli\credentials.json`
3. Próximos comandos reutilizam o arquivo em silêncio. Sessão em `~/.config/zion-cli/session.json`.
4. Trocar de usuário: `python3 zion.py login` de novo (sobrescreve). Sair: `python3 zion.py logout`. Ver quem está salvo: `python3 zion.py whoami`.

Precedência de usuário/senha: `--user` / `ZION_USER`+`ZION_PASSWORD` (ambiente) → arquivo salvo → prompt interativo. Se a senha salva falhar (senha trocada), o CLI pede de novo e regrava. IAs e scripts: variáveis de ambiente ou `login --user U --password-stdin` (sem prompt).

## Variáveis de ambiente (opcionais; sobrescrevem o arquivo salvo)

| Variável | Exemplo | Descrição |
|---|---|---|
| `ZION_URL` | `https://sbsj.zion-srv.com` | URL base do Zion (default no `.env.example`) |
| `ZION_USER` | `nome.sobrenome` | Usuário do Tasy |
| `ZION_PASSWORD` | — | Senha. Nunca é impressa; se o login ok, também é gravada no arquivo local de credenciais |
| `ZION_PROFILE` | `HMMCC - Laboratório - Biomédico` | Nome do perfil ativado após o login |
| `ZION_SETOR` | `HMMCC - Serv. Laboratório Análises Clínicas` | (opcional) setor, só para conferência/aviso |
| `ZION_CONFIG_DIR` | `/tmp/zion-test` | (opcional) pasta das credenciais/sessão — útil em testes |

A senha **nunca** vai para o git. Não versionar `credentials.json` nem `.env`.

## Comandos

Todos aceitam o número do atendimento (`AT`). Os valores podem usar ponto ou vírgula como decimal (prefira ponto no shell). Flag global: `--user NOME` (equivalente a `ZION_USER`).

### `login`
Pede usuário/senha (ou usa env), valida, grava credenciais e troca de perfil.
```bash
python3 zion.py login
```

### `logout`
Apaga o arquivo de credenciais e a sessão local.
```bash
python3 zion.py logout
```

### `whoami`
Mostra só o usuário salvo (nunca a senha).
```bash
python3 zion.py whoami
```

### `fila [--status N] [--exames] [--resumo] [--de] [--ate] [--json]`
**Pendentes por etapa** (não é conferência), sem número de atendimento. Cada linha mostra a **hora exata da solicitação** (`DT_PRESCRICAO`, formato `dd/mm/aaaa HH:MM`, fuso America/Sao_Paulo). Ordena por essa hora. `--de` / `--ate` filtram por `DT_PRESCRICAO` (aceitam `DD/MM/AAAA` ou `DD/MM/AAAA HH:MM`). Sem essas opções: últimos 4 dias. `--json` inclui `dt_prescricao` / `dt_prescricao_iso`.
```bash
python3 zion.py fila --resumo
python3 zion.py fila --status 30 --exames
python3 zion.py fila --de "27/10/2026 08:00" --ate "27/10/2026 12:00"
python3 zion.py fila --status 30 --json
```

### `listar AT [--de] [--ate] [--json]`
**Pendentes do atendimento** (não é conferência). Mostra paciente, setor, leito e os exames por fase/status, com a hora da solicitação (`DT_PRESCRICAO`) em cada amostra. `--de` / `--ate` / `--json` iguais aos da `fila`.
```bash
python3 zion.py listar 123456
python3 zion.py listar 123456 --de "27/10/2026" --ate "27/10/2026 12:00"
```

### `digitacao AT [--dry-run] [--desde STATUS] [--de] [--ate]`
**Pendentes → Digitação** (não é conferência). Leva os exames do atendimento até **Digitação do Resultado** (status 30), passando pelas fases intermediárias (10 Pendente coleta → 20 Material Coletado → 25 Em Análise → 26 Interfaceamento → 30). Filtra por `DT_PRESCRICAO` com `--de` / `--ate` (padrão: últimos 4 dias).
Quando o sistema responde `IE_GERAR_AMOSTRA=S`, o CLI segue a mesma sequência que o navegador faz (sem gerar amostra nova). Qualquer outra resposta não mapeada faz o CLI **parar**.
```bash
python3 zion.py digitacao 123456 --dry-run
python3 zion.py digitacao 123456
python3 zion.py digitacao 123456 --de "27/10/2026 08:00" --ate "27/10/2026 12:00" --dry-run
```

### `ler AT`
Lê os valores salvos de todos os exames em Digitação.
```bash
python3 zion.py ler 123456
```

## Conferir ≠ Pendentes

| Pedido do usuário | Comando | O que faz |
|---|---|---|
| "conferir / verificar resultados críticos / erros nas liberações / o que foi liberado" | `python3 zion.py conferir` | Só leitura dos exames **já liberados (status 40)**. Não digita, não salva, não altera. |
| "o que falta digitar / pendentes / fila / o que tem pra fazer" | `python3 zion.py fila` (ou `listar AT` / `digitacao AT`) | Lista ou move exames **ainda não liberados**. |

**Não misture.** `conferir` ignora qualquer exame da mesma prescrição que ainda não esteja em status 40 (ex.: HCV/HBsAg em Digitação). Quem confere **não digita nem altera nada**.

### `conferir [--de DD/MM/AAAA[ HH:MM]] [--ate ...] [--at AT] [--json] [--sem-historico] [--dias N]`
**Só leitura.** Lista absolutamente todos os exames com status **Exame Liberado** (40) no período (padrão: hoje 00:00 → agora). O período e a hora mostrada em cada linha usam **`DT_PRESCRICAO`** (hora da solicitação, `dd/mm/aaaa HH:MM`, America/Sao_Paulo); `--json` inclui `dt_prescricao` / `dt_prescricao_iso` e `campo_hora`. Abre cada prescrição, lê **somente** os campos dos exames em status 40 (ignora pendentes da mesma presc) e classifica achados em:

- **Possível erro de digitação** — escala ×10/×100/×1000, pares de sedimento EAS inconsistentes, leucograma ≠ 100%, Ht/Hb/CHCM/VCM incoerentes, BD > BT, pH sanguíneo fora de 6,8–7,8, campo principal zerado, conclusão vs valor (Beta HCG), eTFG vazia com creatinina e idade > 12, heurística “> 10× referência”.
- **Resultado crítico** — valores de pânico (Hb < 7; PLT < 50 mil ou > 1 milhão; leucócitos totais < 2 mil ou > 30 mil; K < 2,8 ou > 6,2; Na < 120 ou > 160; iCa < 0,8 ou > 1,6; glicose < 50 ou > 400; creatinina > 5 adulto; BT > 15 em RN; pH < 7,20 ou > 7,60; pCO₂ < 20 ou > 70; lactato > 4; RNI > 4; sorologias reagentes).

Limites ficam em tabelas editáveis no código (`PLAUS_BOUNDS`, `CRITICO_BOUNDS`). **Nunca** salva, aprova nem libera. Informe no relatório os totais de prescrições/exames/campos conferidos.
```bash
python3 zion.py conferir
python3 zion.py conferir --de "27/10/2026" --ate "27/10/2026 23:59"
python3 zion.py conferir --de "27/10/2026 08:00" --ate "27/10/2026 12:00"
python3 zion.py conferir --at 123456
python3 zion.py conferir --json
```

### `resultado AT --exame SIGLA=valor [...] [--dry-run] [--forcar] [--dump-payload ARQ]`
Digita exames por sigla (a sigla do exame no Tasy: `NA+`, `K+`, `CREA`, `UREA`, `TGO`, `TGP`, `PCRP`, `FAL`, `P+`, `MG+`, `CA+`, `DTRIG`, `AURS`, `LDH`...).

- **Campo único:** `--exame CREA=0.51`
- **Campos DV** (ex.: TGO, TGP, AURS): mesmo formato, o CLI cuida do envio como texto. A tela do Tasy mostra com ponto (5.01), é só exibição.
- **Exames com vários campos:** `SIGLA.campo=valor`. O nome do campo é comparado de forma flexível (sem acento/maiúsculas, por igualdade ou "contém"):
  ```bash
  --exame BILI.total=0.73 --exame BILI.direta=0.21
  ```
  Se `BILI.indireta` não for informada, o CLI calcula total − direta. O próprio Zion recalcula a indireta; aceite o valor do sistema.
- **CREA / eTFG:** se o layout tiver campo de idade e o paciente tiver > 12 anos, o CLI preenche a idade (pela data de nascimento) e a eTFG (MDRD) sozinho. Use `CREA.idade=` / `CREA.etfg=` só para sobrescrever.
- **Listas/texto** (tipagem, Coombs): o valor precisa existir na lista do sistema; se não existir, o CLI recusa e mostra as opções válidas.
  ```bash
  python3 zion.py resultado 123456 --exame GP-TIP.abo=B --exame GP-TIP.rh=Positivo --exame COOD=Negativo
  ```
- **EAS / URN1 (urina rotina):** ver seção detalhada em `AGENTS.md`. Resumo: sedimento em pares (papel `13.000/mL` → simples `13` + x1000 `13000`); o CLI corrige se você mandar `13000` no simples. Cruzes (`++`, `2+`) casam por texto exato. Sempre `--forcar`. Exemplo:
  ```bash
  python3 zion.py resultado 123456 --forcar --exame URN1.Hemoglobina=++ \
    --exame URN1.celulas=13000 --exame URN1.leucocitos_ml=2000 --exame URN1.hemacias=21000
  ```
- **Sorologias / exames externos (BLOQUEADO):** qualquer exame cujo nome contenha "Sorologia" (ignora maiúsculas/acentos) ou cuja sigla esteja em `EXAMES_EXTERNOS_BLOQUEADOS` (`TOXG`, `TOXM`, `HBSAG`, `HCV`, `HBCM`, `HBCG`, `A-HBS`, `CMVG`, `CMVM`, `RUGE`, `RUME`, `HIV1/2`, …) é **recusado**. Sem override. **sorologia ≠ teste rápido.**
- **Teste Rápido HIV (`HIV`):** o Teste Rápido 2 só se realiza se o Teste Rápido 1 for **REAGENTE**. Se TR1 = **NÃO REAGENTE**, o CLI grava TR2 = **NÃO REALIZADO** (mesmo que mandem NR) e avisa; se TR2 for omitido, também preenche NÃO REALIZADO.
- **Teste Rápido Toxo (`TRTOXO`):** o campo principal *Teste Rápido Toxo IgG/IgM* tem **opções vazias** no cadastro do Tasy. Os valores ficam nos subcampos **Anticorpos IgG** e **Anticorpos IgM** (`REAGENTE` / `NÃO REAGENTE`). `TRTOXO=NÃO REAGENTE` (ou `NR`/`NEG`) propaga para IgG **e** IgM. Se forem diferentes:
  ```bash
  python3 zion.py resultado 123456 --exame TRTOXO.IgG=NÃO REAGENTE --exame TRTOXO.IgM=REAGENTE --dry-run
  ```
  Não confundir com sorologia `TOXG`/`TOXM` (bloqueadas).
- `--forcar`: sobrescreve campos que já têm valor (sem ele, campos preenchidos são preservados).
- `--dry-run`: mostra o que seria enviado, sem salvar.
- `--dump-payload ARQ`: grava o payload do save (útil para depuração; **não versionar**, contém dados de paciente).

Exemplo completo:
```bash
python3 zion.py resultado 123456 --exame UREA=30 --exame CREA=0.43 --exame TGO=53.5 \
  --exame TGP=59.2 --exame BILI.total=0.73 --exame BILI.direta=0.21 --exame PCRP=14.3 --dry-run
```

### `gaso AT [--ph --pco2 --po2 --hco3 --be --so2 --hb --hct --na --k --ica --cl --glu --lac --bil] [--obs TEXTO] [--dry-run] [--forcar]`
Digita a **gasometria** (venosa/arterial: GASV, GASA, GASO...) e, junto, a **bioquímica equivalente** que existir na prescrição:

| Opção | Bioquímica equivalente |
|---|---|
| `--na` | NA+ |
| `--k` | K+ |
| `--ica` | CAI / CAIO |
| `--cl` | CL |
| `--glu` | GLI / GLIC / GLICO |
| `--lac` | LAC / LACT / LACTATO |

Só preenche exames que existem na prescrição. Campos não informados (ex.: Hct com "Instabilidade") ficam em branco.
```bash
python3 zion.py gaso 123456 --ph 7.458 --pco2 36.9 --po2 52.4 --hco3 26.4 --be 2.3 --so2 88.5 \
  --na 136.1 --k 5.13 --ica 1.14 --cl 97.2 --glu 171 --lac 2.5 --dry-run
```

### `hemo AT --rbc --hgb --hct --vcm --hcm --chcm --rdw --wbc --neu --lym --mon --eos --bas --plt --vpm [--dry-run] [--forcar]`
Digita o **Hemograma Completo** com os valores **exatamente como no impresso do analisador**:

**Regra obrigatória do hemograma (automática no `hemo`):** Eosinófilos ≥ 1% sempre; se Leucócitos Totais > 10.000, também Bastonetes ≥ 1%. Os pontos acrescentados saem do maior percentual (normalmente segmentados) e o Total porcentagem Leucograma fica em 100. O CLI imprime o ajuste feito.

- `--wbc` em 10³/µL (ex.: 14.06). Leucócitos Totais = WBC × 1000; os absolutos o sistema calcula.
- `--plt` em 10⁹/L (ex.: 174). O servidor multiplica por 1000 (→ 174.000).
- `--neu --lym --mon --eos --bas` em %: arredondados meio-para-cima; se a soma passar de 100, o basófilo é reduzido primeiro, fechando 100.
```bash
python3 zion.py hemo 123456 --rbc 4.04 --hgb 13.3 --hct 36 --vcm 89.1 --hcm 32.8 --chcm 36.9 --rdw 12.6 \
  --wbc 14.06 --neu 82.1 --lym 11.9 --mon 5.6 --eos 0.3 --bas 0.1 --plt 174 --vpm 11.7 --dry-run
```

## Histórico do paciente (só leitura) — `historico`

Todo resultado digitado (normal **ou** alterado, qualquer exame) deve ser comparado com os
resultados anteriores do paciente e com a evolução clínica antes de reportar. O CLI faz isso
sozinho depois de `resultado`, `hemo` e `gaso`, e também no `conferir`.

### `historico AT [--exame SIGLA ...] [--dias 90] [--notas 1] [--json]`
- Só leitura: nada é salvo, aprovado ou liberado.
- Exames atuais = os que estão em Digitação (30); se não houver, usa o liberado mais recente de cada exame.
- Para cada campo numérico mostra: valores anteriores com data/hora de coleta e atendimento
  (cruza **todos os atendimentos** do paciente), tendência (subindo/caindo/estável) e Δ vs último.
- Alertas: `mudança grande vs último` (> 50%), `passou a faixa crítica (antes não era)` (tabela
  `CRITICO_BOUNDS`) e `AVISO: sem resultado anterior`.
- No fim imprime o **resumo**: exames sem resultado anterior, com mudança grande/crítica e sem evolução clínica compatível.

```bash
python3 zion.py historico 123456                 # todos os exames do atendimento
python3 zion.py historico 123456 --exame CREA --exame UREA --dias 30
```

Fontes no Tasy (descobertas nos bundles da tela, sem HAR):
- `CorLabF3/getChartRecords` — dados do gráfico **Resultados anteriores** da própria digitação
  (até 6 prescrições por chamada; o CLI pagina para trás até a janela `--dias`).
- `CorLabF3/ativarExameLabResultItemAsHashMap` — datas (coleta/aprovação) e status de cada prescrição.
- `CorLabF0/loadPatientData` (Consulta de Resultados, feature 7008) — atendimento de cada prescrição.
- Exames sem série no gráfico (ex.: gasometria) → lê os **liberados (40)** do mesmo atendimento
  (até 3 prescrições, como o `conferir`).
- **Notas clínicas do PEP: ainda não mapeadas.** O CLI imprime
  `AVISO: sem evolução clínica compatível (notas clínicas do PEP não disponíveis no CLI…)` e segue;
  confira a evolução no PEP (Notas clínicas → Filtrar). Os mapas de palavras-chave por grupo
  (`HIST_GRUPOS`: renal → FUNÇÃO RENAL/DIURESE/diálise; hemato → sangramento/transfusão;
  eletrólitos → reposição/diálise; hepático; infeccioso; metabólico) já estão prontos para
  destacar o trecho da evolução quando o serviço for mapeado (`notas_clinicas()`).

### Depois de salvar (`resultado`, `hemo`, `gaso`)
- Após cada save bem-sucedido o CLI imprime uma comparação compacta por exame salvo.
- **Nunca bloqueia nem pula o save:** sem resultado anterior ou sem evolução compatível, o
  resultado é salvo normalmente e sai `AVISO: sem resultado anterior` /
  `AVISO: sem evolução clínica compatível`, mais o resumo final listando esses exames.
- `--sem-historico` desliga a comparação. Em `--dry-run` não há comparação (nada foi salvo).

### No `conferir`
- Cada exame liberado ganha a mesma comparação (só os campos com histórico ou alerta) e o resumo no fim.
- `--sem-historico` desliga; `--dias N` muda a janela (padrão 90). Em `--json` vai na chave `historico`.

## Laudos do DB Diagnósticos (E-DB) → anexar no Tasy

As sorologias (TOXG, TOXM…) são feitas pelo **DB Diagnósticos**. Nelas o CLI **não digita valores**. Ele baixa o laudo em PDF no portal E-DB e **anexa** ao exame do Tasy, pela mesma ação do menu *Anexar exame PDF* (tabela `RESULT_LABORATORIO`). **Nada é liberado.**

### ⚠️ Regra: um PDF por exame
Cada exame do Tasy recebe **só o PDF dele**:
- o PDF do TOXG vai para o exame *Toxoplasmose IgG*;
- o PDF do TOXM vai para o exame *Toxoplasmose IgM*.

**Nunca** anexe um PDF único com vários exames. O CLI pede ao portal o laudo de **um** procedimento por vez (`SeqProcedimento`) e lê o texto do PDF (`pdftotext`, pacote poppler-utils). Ele **recusa** o PDF quando:
- o nome do paciente não é o mesmo do Tasy;
- o PDF traz outro exame do mesmo pedido.

### Passo a passo
1. **Acesso ao portal DB.** Faça uma vez; depois o CLI renova a sessão sozinho:
   ```bash
   printf '%s' "$DB_SENHA" | python3 zion.py db-login --cpf 00000000000 --password-stdin
   # serviço solicitante padrão: 2517530 (troque com --serv-sol)
   # se o portal pedir 2 fatores, o código chega por e-mail/SMS; rode de novo com --otp CODIGO
   ```
   O CPF e a senha ficam em `~/.config/zion-cli/db_credentials.json` (permissão 600), fora do repositório. Para apagar: `python3 zion.py db-logout`. Para conferir: `python3 zion.py db-whoami` (mostra o CPF mascarado).
2. **Ver o que existe** (só leitura):
   ```bash
   python3 zion.py db-buscar 123456
   ```
   Lista o pedido do DB e o status de cada exame, os exames do Tasy em Digitação (status 30) com o par DB de cada um, e o anexo que já existe.
3. **Ensaio**: baixa e confere cada PDF, mas não grava nada no Tasy:
   ```bash
   python3 zion.py db-anexar 123456 --dry-run [--exame TOXG] [--salvar-pdf /tmp/laudos]
   ```
4. **Anexar de verdade:**
   ```bash
   python3 zion.py db-anexar 123456            # todos os exames do DB em Digitação
   python3 zion.py db-anexar 123456 --exame TOXM
   ```
   Para cada exame, o CLI faz o seguinte:
   1. baixa só o PDF daquele exame e confere o paciente;
   2. envia o arquivo como `SIGLA_DBpedido.pdf`;
   3. grava o anexo no exame;
   4. **relê** o exame: precisa haver **exatamente 1** anexo, e é o arquivo certo;
   5. confirma que o status continua 30.

   O exame que já tem anexo é **pulado**. Para trocar o anexo, use `--substituir`: o CLI faz *Desfazer exame PDF* e anexa o novo.

### Opções úteis
- **Vínculo com o pedido DB.** O CLI procura o pedido pelo número do atendimento, pelas prescrições e pelo nome do paciente, e só aceita o nome **idêntico**. Se a busca falhar, use `--chave X` ou `--pedido N`.
- **Período.** A busca de exames no Tasy cobre, por padrão, os últimos 30 dias. Use `--de` e `--ate` para mudar.
- **Siglas DB → Tasy.** A tabela padrão é `DB_SIGLAS` em `zion.py` (`TOXG→TOXG`, `TOXM→TOXM`, `PTUR→PTU24`; a chave é a sigla do Tasy e a lista traz as siglas do DB). Para acrescentar siglas sem mexer no código, crie `~/.config/zion-cli/db_siglas.json`, por exemplo `{"HBSAG": ["HBSAG"], "CMVG": ["CMVG"]}`.
- **Pré-requisito.** O exame precisa estar em **Digitação (30)**. O Tasy só permite anexar com status < 35.

## Segurança

- **Nunca libera** resultados; só salva.
- Rode sempre `--dry-run` antes de salvar.
- Depois de salvar, o CLI relê e compara; confira a releitura.
- Avisos de valor fora da referência / consistência / eTFG são esperados e **não** cancelam o save.
- Laudos DB: **um PDF por exame**, nunca um PDF combinado; o anexo não libera.
- Não versionar `.session.json`, `db_credentials.json`, PDFs de laudo, HARs, backups ou payloads: contêm tokens e dados de pacientes.

## templates.json

Contém os modelos dos payloads das telas do Tasy (códigos de ação/painel, filtros), extraídos de capturas HAR do navegador e **sanitizados**: números de atendimento, prescrição, amostra, paciente e pessoa foram anulados; o CLI preenche esses campos em tempo de execução. Para outra instalação/versão do Tasy pode ser preciso recapturar: faça o fluxo no navegador com DevTools → salvar HAR, copie o corpo das requisições `WCPanel`/`CorLabF3` correspondentes para as mesmas chaves e **apague o HAR** (ele contém tokens).

## Para agentes de IA

Leia [`AGENTS.md`](AGENTS.md).
