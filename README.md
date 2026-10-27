# zion-tasy-cli

## 🔐 Login: a IA pode fazer pela pessoa

- A IA **pode** fazer o login. A senha chega por um **canal secreto**: o formulário seguro / campo secreto da plataforma da IA, ou as variáveis de ambiente `ZION_USER` e `ZION_PASSWORD`.
- Comando (a senha vai pelo stdin, sem eco, nunca no argv):
  ```bash
  printf '%s' "$ZION_PASSWORD" | python3 zion.py login --user "$ZION_USER" --password-stdin
  ```
  Também funciona só com o ambiente: `ZION_USER=... ZION_PASSWORD=... python3 zion.py login` (valores vindos do canal secreto).
- O CLI confere o login no Zion e grava em `~/.config/zion-cli/credentials.json` (permissão 600). A senha nunca aparece na saída.
- A IA **nunca** escreve a senha no texto do chat, em arquivos do repositório, em comandos com a senha literal nem em logs.
- Se o formulário seguro falhar (ex.: perdeu os campos), a IA tenta de novo ou pede para a pessoa rodar `python3 zion.py login` no terminal.
- Senha errada: o CLI sai com `Login falhou (HTTP 400): ...`, sem mostrar a senha e sem gravar nada.
- Quem está logado: `python3 zion.py whoami`. Trocar de usuário: `python3 zion.py logout` e depois `login` de novo.
- Quem digita usuário e senha é a **pessoa**, direto no terminal dela: `python3 zion.py login`.
- A IA **nunca** preenche o login, **nunca** pede a senha no chat e **nunca** abre "formulário seguro", "tela de login" ou navegador para isso.
- Se aparecer pedido de usuário/senha, a IA **para** e diz à pessoa: "rode `python3 zion.py login` no seu terminal".
- Quem está logado: `python3 zion.py whoami`. Trocar de usuário: `python3 zion.py logout` e depois `python3 zion.py login`.
- Sem terminal interativo e sem credencial salva, o CLI falha com mensagem clara pedindo para rodar `login` no terminal.


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

### `conferir [--de DD/MM/AAAA[ HH:MM]] [--ate ...] [--at AT] [--json]`
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

## Segurança

- **Nunca libera** resultados; só salva.
- Rode sempre `--dry-run` antes de salvar.
- Depois de salvar, o CLI relê e compara; confira a releitura.
- Avisos de valor fora da referência / consistência / eTFG são esperados e **não** cancelam o save.
- Não versionar `.session.json`, HARs, backups ou payloads: contêm tokens e dados de pacientes.

## templates.json

Contém os modelos dos payloads das telas do Tasy (códigos de ação/painel, filtros), extraídos de capturas HAR do navegador e **sanitizados**: números de atendimento, prescrição, amostra, paciente e pessoa foram anulados; o CLI preenche esses campos em tempo de execução. Para outra instalação/versão do Tasy pode ser preciso recapturar: faça o fluxo no navegador com DevTools → salvar HAR, copie o corpo das requisições `WCPanel`/`CorLabF3` correspondentes para as mesmas chaves e **apague o HAR** (ele contém tokens).

## Para agentes de IA

Leia [`AGENTS.md`](AGENTS.md).
