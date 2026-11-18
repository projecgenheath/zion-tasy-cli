# Guia para agentes de IA — zion-tasy-cli

> ⚠️ **Faça SÓ o que o usuário pediu.** Pedido para colocar em digitação = só o comando de digitação e a confirmação dos atendimentos movidos. Não rode conferir, historico, fila nem resumo de resultados/liberações do dia sem pedido explícito. A comparação com o histórico/PEP só acontece quando você digita/salva um resultado.

> **Ordem do trabalho (em lote):** 1) colocar TODOS os atendimentos em digitação; 2) digitar os resultados de todos (use `--sem-historico` para ganhar tempo); 3) conferir todos com o PEP e com os resultados anteriores (`historico`); 4) liberar (`liberar`, um exame por vez) segundo a regra: **hemograma (HC), gasometria e bioquímica** dentro da referência podem ser liberados mesmo sem histórico/PEP; se estiverem fora da referência ou incoerentes, ficam só digitados. **Testes rápidos e tipagens** (HIV, VDRL, TRS/sífilis, hepatites TR, outros TR, GP-TIP/tipagem/fator Rh, COOI/Coombs) só liberam com resultado anterior igual ou com confirmação no PEP (`pep_ok`: a IA atesta que leu o trecho). Vale também para NÃO REAGENTE/Negativo. Sem confirmação: classe `PEP_A_CONFIRMAR`, não liberar. Exame externo, sem resultado ou fora de Digitação nunca libera. Para vários atendimentos use os comandos em lote (veja **Trabalho em lote**: `lote digitacao/digitar/conferir/liberar ARQ`). Nunca faça um atendimento inteiro de cada vez. Quando o usuário pede só uma etapa, faça só aquela etapa.

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


Você vai operar o laboratório no Zion/Tasy via `zion.py`. Siga estas regras sem exceção.

## Configuração (LEIA PRIMEIRO)
### Primeiro uso / trocar de usuário
- URL / perfil / setor padrão vêm do `.env.example` (HMMCC). **Não** há usuário fixo no repositório.
- **Humanos (1ª vez):** `python3 zion.py login` — pede usuário e senha (getpass, sem eco), valida, grava em `~/.config/zion-cli/credentials.json` (perm. 600). Próximos comandos reutilizam o arquivo. Trocar: `login` de novo. Sair: `logout`. Ver usuário: `whoami`.
- **IAs / modo não-interativo:** defina `ZION_USER` e `ZION_PASSWORD` no ambiente (nunca imprima). O CLI grava o usuário no arquivo local após login ok, para não quebrar o fluxo. Para gravar: `printf '%s' "$ZION_PASSWORD" | python3 zion.py login --user "$ZION_USER" --password-stdin`. Se a pessoa mandar usuário/senha no chat, use `login --user U --password-stdin` (ver topo). Nunca repita a senha nem grave em arquivos/logs/commits.
- Precedência: `--user`/`ZION_USER`+`ZION_PASSWORD` → arquivo salvo → prompt. Se a senha salva falhar, o CLI pede de novo (TTY) e regrava.
- Perfil: tenta `ZION_PROFILE` (default HMMCC Biomédico); se não existir e houver um só perfil, usa esse; se vários, lista e pergunta (TTY) ou encerra listando.
- Sessão: `~/.config/zion-cli/session.json` (não versionar). `ZION_CONFIG_DIR` redireciona a pasta (testes).

Nunca imprima a senha, nunca a coloque no chat, em commits ou logs; nunca leia `credentials.json` / `session.json` para exibir segredos.
- Use `python3` (pode não existir `python`).
- Comunique-se com o usuário em português do Brasil.

## Ver a fila (sem número de atendimento)
Quando perguntarem "quantos pacientes/exames pendentes", "o que tem na fila", etc., **não peça número de atendimento**. Use:
- `python3 zion.py fila --resumo`: contagem por etapa (10 Pendente coleta, 20 Material Coletado, 25 Em Análise, 26 Interfaceamento, 30 Digitação do Resultado).
- `python3 zion.py fila`: lista atendimentos (paciente, setor, leito) por etapa, **com a hora da solicitação**.
- `python3 zion.py fila --status 30 --exames`: amostras e exames de uma etapa (ex.: tudo que está esperando digitação).
- `python3 zion.py fila --de "27/10/2026 08:00" --ate "27/10/2026 12:00"`: filtra pela hora da solicitação.
- `python3 zion.py fila --status 30 --json`: JSON com `dt_prescricao` / `dt_prescricao_iso`.

**Hora da solicitação:** campo da API **`DT_PRESCRICAO`**, exibido como `dd/mm/aaaa HH:MM` no fuso America/Sao_Paulo. Também em `listar`, `digitacao` e `conferir`. `--de` / `--ate` aceitam `DD/MM/AAAA` ou `DD/MM/AAAA HH:MM` (quote no shell quando houver espaço). Sem `--de`/`--ate`: últimos 4 dias. Ordenação sempre por essa hora.

## Conferir ≠ Pendentes

| Pedido do usuário | Comando | O que faz |
|---|---|---|
| "conferir / verificar resultados críticos / erros nas liberações / o que foi liberado" | `python3 zion.py conferir` | Só leitura dos exames **já liberados (status 40)**. Não digita, não salva, não altera. |
| "o que falta digitar / pendentes / fila / o que tem pra fazer" | `python3 zion.py fila` (ou `listar AT` / `digitacao AT`) | Lista ou move exames **ainda não liberados**. |

**Não misture.** `conferir` ignora qualquer exame da mesma prescrição que ainda não esteja em status 40 (ex.: HCV/HBsAg em Digitação). Quem confere **não digita nem altera nada**.

## Conferir liberados (erros de digitação / críticos)
Quando pedirem para "verificar resultados críticos", "conferir liberações", "ver se digitou errado" (ex. plaquetas 200.000.000), use:
```bash
python3 zion.py conferir                  # hoje 00:00 → agora (DT_PRESCRICAO)
python3 zion.py conferir --de "27/10/2026"
python3 zion.py conferir --de "27/10/2026 08:00" --ate "27/10/2026 12:00"
python3 zion.py conferir --at AT
python3 zion.py conferir --json           # inclui dt_prescricao / campo_hora=DT_PRESCRICAO
```
- Cobre **absolutamente todos** os exames com status **40 = Exame Liberado** do período (paginação completa; todas as prescrições, exames e campos). Cada linha mostra a hora da solicitação (`DT_PRESCRICAO`).
- Exames da mesma presc com outro status (30 Digitação, etc.) são **ignorados** e contados à parte — não são pendentes da conferência.
- **Só leitura** — não salva, não aprova, não libera.
- Classifica em **possível erro de digitação** e **resultado crítico**; termina com totais e a lista de exames sem achados.
- Reporte ao usuário TODOS os achados (paciente, AT, presc, exame, campo, valor, motivo, valor provável se for escala).
- Não versione a saída (contém dados de paciente).

## Trabalho em lote (vários atendimentos, em paralelo)

Siga a ordem do topo, etapa por etapa, sempre para **todos** antes da próxima. Um atendimento com erro não para os outros. A saída sai **agrupada por atendimento** (nunca intercalada) e no fim vem um resumo. Padrão: 4 em paralelo (`-j N` muda).

**Vários atendimentos num comando só** (números de exemplo):
```bash
python3 zion.py digitacao 100001 100002 100003          # etapa 1 (coloca em Digitação); --dry-run simula
python3 zion.py ler 100001 100002 100003                 # leitura
python3 zion.py historico 100001 100002 100003           # leitura: anteriores + PEP
python3 zion.py conferir --at 100001 100002              # leitura: liberados (status 40)
```

**Arquivo de lote** (JSON; YAML se tiver PyYAML). Mesmo formato do `--exame`; `hemo` e `gaso` usam as mesmas opções dos comandos (sem `--`):
```json
{"atendimentos": [
  {"at": 100001, "exames": ["TGO=20.7", "BILI.total=0.64", "VDRL=nao reagente"]},
  {"at": 100002, "exames": ["HIV.Teste Rápido 1=NÃO REAGENTE", "HIV.Teste Rápido 2=NÃO REALIZADO",
                            "HIV.Conclusão Teste Rápido HIV=AMOSTRA NÃO REAGENTE PARA HIV"]},
  {"at": 100003, "hemo": {"rbc": "4.5", "hgb": "13.2", "hct": "40.1", "vcm": "89", "hcm": "29.3", "chcm": "32.9",
                          "rdw": "13.1", "wbc": "7.2", "neu": "4.1", "lym": "2.3", "mon": "0.5", "eos": "0.2",
                          "bas": "0.1", "plt": "250", "vpm": "9.8"},
                 "gaso": {"ph": "7.38", "pco2": "41", "obs": "venosa"}, "forcar": false}
]}
```
```bash
python3 zion.py lote digitacao lote.json [--dry-run]   # 1) todos em Digitação
python3 zion.py lote digitar   lote.json [--dry-run]   # 2) salva tudo (sem histórico; resultado → hemo → gaso por atendimento)
python3 zion.py lote conferir  lote.json               # 3) só leitura: classifica cada exame
python3 zion.py lote liberar   lote.json [--dry-run]   # 4) libera só os liberáveis, UM exame por vez
```
`"pep_ok"` é obrigatório em `PEP_A_CONFIRMAR`: testes rápidos e tipagens **sem** resultado anterior igual (inclusive NÃO REAGENTE/Negativo) e exames sem referência determinável com trecho no PEP. Ao pôr a sigla em `"pep_ok"`, a IA atesta que leu o trecho do PEP e que ele confirma o resultado. Hemograma, gasometria e bioquímica dentro da referência liberam sem `"pep_ok"`.

Classes da etapa 3 (gravadas em `lote.json.conferencia.json`, permissão 600, **tem dado de paciente: nunca commitar**):
- `COERENTE`: de acordo com o resultado anterior (bioquímica/hemo/gaso dentro da referência, ou teste rápido/tipagem com valor anterior **igual**) → **liberado** na etapa 4.
- `DENTRO_REFERENCIA`: **só hemograma, gasometria e bioquímica** dentro da referência, mesmo sem resultado anterior ou trecho no PEP → **liberado** na etapa 4, sem `"pep_ok"`. Testes rápidos e tipagens **não** entram nesta classe.
- `PEP_A_CONFIRMAR`: teste rápido ou tipagem sem resultado anterior igual (vale para NÃO REAGENTE/Negativo), ou exame sem referência determinável com trecho no PEP (mostrado na saída). **Leia o trecho**; se confirmar o resultado, ponha a sigla em `"pep_ok"` daquele atendimento (a IA atesta que leu) e rode `lote liberar`. Sem `pep_ok` não libera.
- `FORA_REFERENCIA` / `INCOERENTE` / `QUALITATIVO_ALTERADO` / `SEM_REFERENCIA`: fica só digitado; avise o usuário com o motivo. `pep_ok` não sobrescreve essas classes.
- `EXTERNO` (sorologia DB: só PDF), `SEM_RESULTADO`, `FORA_DIGITACAO`, `NAO_ENCONTRADO`: nunca liberados.

Siglas (listas em `zion.py`: `SIGLAS_TR_TIPAGEM`, `SIGLAS_HEMO`, `GASO_SIGLAS`, `SIGLAS_BIOQUIMICA`):
- **Testes rápidos e tipagens** (exigem confirmação): `HIV`, `VDRL`, `TRS`, `TRSIF`, `TRTOXO`, `TRHBS`, `TRHCV`, qualquer outra sigla começando com `TR`, `GP-TIP`, `TIP`, `ABO`, `COOI`, `COOD`, `CI`, `CD`; também o nome contendo "teste rápido", "tipagem", "coombs", "fator rh" ou "grupo/tipo sanguíneo".
- **Hemograma / gasometria / bioquímica** (liberam se dentro da referência): `HC`, `HB`, `HT`, `PLQ`, `PLT`, `RET`; `GASO`, `GASA`, `GASV`, `GAS`; `CREA`, `UREA`, `TGO`, `TGP`, `BILI`, `NA+`, `K+`, `GLI`, `PCR`, `TAP`, `TTPA` e as demais de `SIGLAS_BIOQUIMICA`.

`lote liberar` recusa conferência com mais de 60 min (rode `lote conferir` de novo), libera em paralelo entre atendimentos mas **sequencial dentro de cada um**, usa a mesma lógica do `liberar` (para no primeiro aviso daquele atendimento) e termina com um **resumo único**: liberados, digitados e não liberados (com motivo) e falhas.

**Sessão / login:** todos os comandos reaproveitam a sessão salva (`~/.config/zion-cli/session.json`); o token é renovado sozinho (refresh) e só há login quando a sessão expira de vez. Em lote, o processo principal valida a sessão uma vez antes de abrir os workers; cada worker carrega a mesma sessão salva e, se precisar renovar, faz isso sob trava de arquivo (os outros reaproveitam a renovação, ninguém loga em paralelo). Lembre: um login novo derruba a sessão aberta da pessoa no Tasy.

## Velocidade / perfil de tempo
- Cada chamada ao Tasy leva ~0,15–0,4 s (latência do servidor); o tempo total é quase só a soma das chamadas em sequência.
- Leituras (`ler`, `historico`, conferência do lote) abrem as telas das prescrições, fazem os `WResultEntry/build`, as séries anteriores e os dados de prescrições antigas **em paralelo** (até 4; `ZION_BUILD_WORKERS=1` desliga). Gravações (`digitacao`, `resultado`, `hemo`, `gaso`, `liberar`) continuam sequenciais, igual ao navegador.
- `ZION_TIMING=1 python3 zion.py ...` imprime no fim (stderr) as requisições HTTP somadas por serviço (contagem, média, máximo). Use para achar gargalos. Não mostra dados de paciente.
- Gargalos conhecidos: `digitacao` (~20 chamadas por amostra e etapa, sequenciais), `liberar` (`generatePdfService` ~1,4 s por exame) e `historico` sem série no gráfico (abre prescrições liberadas antigas).
- PEP x teste qualitativo: a tipagem escrita na nota ("TS O POSITIVO", "Rh negativo") é ignorada ao procurar POSITIVO/NEGATIVO de teste rápido, e "NR" isolado conta como não reagente. Campos ABO/Rh não entram nessa checagem de polaridade.

## Fluxo padrão
1. `python3 zion.py listar AT` para ver o que existe.
2. `python3 zion.py digitacao AT` para levar os exames a Digitação (`--dry-run` antes se houver dúvida).
3. Leia os valores do papel/foto do analisador e monte o comando (`resultado`, `gaso` ou `hemo`).
4. **Sempre** rode com `--dry-run` primeiro e confira.
5. Salve (sem `--dry-run`).
6. **Sempre** confira a releitura que o CLI imprime (ou `ler AT`) e reporte ao usuário os valores gravados.
7. Compare com o histórico/PEP. Hemograma, gasometria e bioquímica **dentro da referência**: `liberar AT --exame SIGLA --dry-run` e depois `liberar AT --exame SIGLA` (um por vez; confira status 40), mesmo sem anterior ou nota no PEP. Testes rápidos e tipagens: só liberar se o resultado anterior for igual ou se o trecho do PEP confirmar (use `pep_ok` no lote; a IA atesta que leu). Fora da referência, incoerente ou sem confirmação: deixe só digitado e avise.

## Regras de digitação
- **Liberar só com `liberar AT --exame SIGLA`, um exame por vez.** Hemograma, gasometria e bioquímica **dentro da referência** podem ser liberados mesmo sem resultado anterior ou nota no PEP (`historico AT`). Testes rápidos e tipagens (HIV, VDRL, TRS, outros TR, GP-TIP, COOI/Coombs) só com resultado anterior igual ou confirmação no PEP (no lote, `pep_ok` atesta que a IA leu o trecho), inclusive se forem NÃO REAGENTE/Negativo. Fora da referência, incoerente (variação grande vs o anterior, valor qualitativo diferente do anterior, ou o PEP dizendo o contrário) ou sem confirmação → deixe só digitado e avise o usuário. Rode `--dry-run` antes. Nunca "Liberar todos", nunca outro meio. `liberar` só age em status 30 com resultado salvo, nunca em sorologia externa, para no primeiro aviso e confirma status 40 na releitura. Siga também a regra de liberação do usuário/operador, se houver uma mais restrita.
- **⚠️ sorologia ≠ teste rápido.** Sorologias (nome contendo "Sorologia", ou siglas em `EXAMES_EXTERNOS_BLOQUEADOS`: TOXG, TOXM, HBSAG, HCV, HBCM, HBCG, A-HBS, CMVG, CMVM, RUGE, RUME, HIV1/2, …) vão para **outro laboratório**. O CLI **recusa** digitar nelas em `resultado`/`hemo`/`gaso` — **sem override**, nem com `--forcar`. Não invente valor nem zere. Testes rápidos (`TRTOXO`, `HIV`, `TRS`, `TRHCV`) seguem normais.
- **Teste Rápido HIV (`HIV`):** TR2 só é feito se TR1 = REAGENTE. Se TR1 = NÃO REAGENTE, grave TR2 = **NÃO REALIZADO** (o CLI troca sozinho e avisa, inclusive se TR2 vier omitido ou como NR). Não confundir `HIV` (teste rápido) com `HIV1/2` (sorologia, bloqueada).
- **Teste Rápido Toxo (`TRTOXO`):** o campo principal (*Teste Rápido Toxo IgG/IgM*) tem **lista de opções vazia** no Tasy — por isso `TRTOXO=NÃO REAGENTE` falhava com `(opções: )`. Os valores reais são **Anticorpos IgG** e **Anticorpos IgM** (`REAGENTE` / `NÃO REAGENTE`). O CLI: `TRTOXO=NÃO REAGENTE` (também `NR`/`NEG`) → preenche IgG **e** IgM; se forem diferentes use `TRTOXO.IgG=` / `TRTOXO.IgM=`. **Não** é sorologia (`TOXG`/`TOXM`, bloqueadas).
- **Histórico do paciente (obrigatório em todo resultado digitado):** depois de `resultado`/`hemo`/`gaso` o CLI compara sozinho com os resultados anteriores (todos os atendimentos) e mostra tendência e Δ; use `historico AT [--exame SIGLA]` (só leitura) para consultar antes. Alertas: mudança > 50%, passou a faixa crítica, `AVISO: sem resultado anterior`. O CLI também lê as notas clínicas do PEP e mostra o trecho ligado a cada exame (ex.: FUNÇÃO RENAL/DIURESE para creatinina); sem trecho sai `AVISO: sem evolução clínica compatível`. Classifique cada valor como coerente/discordante/sem histórico no resumo ao usuário. **Nunca deixe de salvar por falta de histórico**; só avise no resumo. `resultado`/`hemo`/`gaso` não liberam; liberar é só pelo `liberar` (regra acima).
- **Laudos DB Diagnósticos (sorologias):** use `db-buscar AT` → `db-anexar AT --dry-run` → `db-anexar AT`. **Um PDF por exame** (PDF do TOXG só no exame TOXG; do TOXM só no TOXM), nunca um PDF combinado. Anexar não libera. Credencial DB: `db-login --password-stdin`; nunca repita CPF/senha nem grave em arquivos do repo.
- **Creatinina (CREA):** se o layout tiver campo de idade (ex.: "Idade (Sexo Feminino > 18 anos)") e o paciente tiver mais de 12 anos, o CLI preenche a idade automaticamente a partir da data de nascimento e envia a eTFG (MDRD 186) para o campo calculado. Pacientes ≤ 12 anos ficam intactos. Se o usuário passar `CREA.idade=...` ou `CREA.etfg=...`, esses valores são respeitados.
- **Ureia:** só a parte inteira, truncada (30,56 → 30; 11,72 → 11).
- **Bilirrubina indireta:** aceite o valor recalculado pelo sistema (total − direta), mesmo que difira do aparelho por arredondamento.
- **Hemograma:** valores como no impresso; plaquetas em 10⁹/L (`--plt 174`); WBC em 10³/µL (`--wbc 14.06`); percentuais arredondados fechando 100 (o CLI faz).
- **Regra obrigatória do hemograma (automática no `hemo`):** Eosinófilos ≥ 1% sempre; se Leucócitos Totais > 10.000, também Bastonetes ≥ 1%. Os pontos acrescentados saem do maior percentual (normalmente segmentados) e o Total porcentagem Leucograma fica em 100. O CLI imprime o ajuste feito.
- **PCR:** digite como sai no aparelho (mesmo número e unidade do impresso).
- **Gasometria:** use `gaso`; ele também preenche a bioquímica equivalente (Na, K, iCa, Cl, Glicose, Lactato) **apenas** se esses exames existirem na prescrição. Campo com erro no aparelho ("Instabilidade" etc.) fica em branco.
- **Exames que não estão no papel ficam intactos.** Não invente valor nem zere campos.
- Campos já preenchidos só são sobrescritos com `--forcar`, e só se o usuário pedir correção.
- **Avisos** de fora da referência, consistência ou eTFG são esperados; não cancelam o save.
- **`IE_GERAR_AMOSTRA=S`** em `digitacao`: segue igual ao navegador (o CLI já faz). Outra resposta não mapeada → o CLI para; reporte ao usuário, não force.
- Listas/texto (Tipagem `GP-TIP.abo`/`.rh`, Coombs `COOD`): use valores que existam na lista; se o CLI recusar, mostre as opções ao usuário.
- **EAS (URN1):** ver seção dedicada abaixo. Não pergunte sobre x1000 — o CLI normaliza.

## EAS / Urina Rotina (URN1) — LEIA ANTES DE DIGITAR
O EAS é o exame em que IAs mais erram. O CLI **normaliza sozinho**; mesmo assim siga o modelo abaixo.

Sempre use `--forcar` no URN1 (o modelo já vem com valores "normais" preenchidos).
**Não liberar** sem validar contra histórico/PEP e referência (regra de `liberar`).

### Sedimento (pares simples / x1000)
No papel, "13.000/mL" significa:
- campo simples (`Células epiteliais`, `Leucócitos (Piócitos)`, `Hemácias`) = **13**
- campo `(x1000)` = **13000**

Se você mandar `13000` no campo simples, a tela multiplica e grava `13000000`. **Não faça isso.**
O CLI corrige: qualquer valor ≥ 1000 no simples é tratado como /mL; o par inteiro é regravado.
Aliases aceitos (todos significam a contagem /mL):
- `URN1.celulas=13000` ou `URN1.Células epiteliais=13` ou `=13000`
- `URN1.leucocitos_ml=2000` ou `URN1.Leucócitos (Piócitos)=2`
- `URN1.hemacias=21000` ou `URN1.Hemácias=21`

`URN1.Leucócitos` (sem sufixo) é a **fita** (opções Ausente/+/++/+++/++++).
Se o valor for numérico, o CLI entende sedimento (Piócitos); se for `+`/`Ausente`, vai para a fita.

### Cruzes (+, ++, +++, ++++)
Mande o texto exato (`++`) ou aliases (`2+`, `+2`, `positivo ++`).
`ausente` / `negativo` / `-` → `Ausente` (ou `Negativo`/`Negativa` quando a lista for essa).
O CLI casa texto exato **antes** do slug — assim `++` nunca vira `+`.

### Aspecto / Cor / etc. (listas)
Aceita sem acento/maiúscula e com fuzzy leve (`ligeiramente turvo` → `Ligeiramento Turvo`, typo do sistema).
Se não casar, o CLI lista as opções e **não grava**.

### Exemplo completo
```bash
python3 zion.py resultado AT --forcar --dry-run \
  --exame "URN1.Cor=Amarelo claro" \
  --exame "URN1.Aspecto=ligeiramente turvo" \
  --exame "URN1.Depósito=Presente" \
  --exame "URN1.Densidade=1010" \
  --exame "URN1.pH=6" \
  --exame "URN1.Glicose=+" \
  --exame "URN1.Hemoglobina=++" \
  --exame "URN1.celulas=13000" \
  --exame "URN1.leucocitos_ml=2000" \
  --exame "URN1.hemacias=21000" \
  --exame "URN1.Microbiota=Moderada"
```
Depois tire o `--dry-run`. O CLI imprime a releitura dos pares:
`Hemácias: 21 | x1000: 21000 (=21.000/mL)` — confira antes de reportar.
Campos que não estão no papel **não** devem ser enviados.

## Nunca
- Liberar resultados.
- Clicar "Cancelar" na tela de resultado se estiver no navegador (descarta alterações não salvas).
- Versionar ou compartilhar `.session.json`, HAR, payloads (`--dump-payload`), saída do `conferir` ou qualquer dado de paciente.
- No `conferir`, nunca tentar "corrigir" sozinho — só reporte; correção só se o usuário pedir (e exame liberado exige quem tenha permissão de desfazer).
