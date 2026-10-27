# Guia para agentes de IA — zion-tasy-cli

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


Você vai operar o laboratório no Zion/Tasy via `zion.py`. Siga estas regras sem exceção.

## Configuração (LEIA PRIMEIRO)
### Primeiro uso / trocar de usuário
- URL / perfil / setor padrão vêm do `.env.example` (HMMCC). **Não** há usuário fixo no repositório.
- **Humanos (1ª vez):** `python3 zion.py login` — pede usuário e senha (getpass, sem eco), valida, grava em `~/.config/zion-cli/credentials.json` (perm. 600). Próximos comandos reutilizam o arquivo. Trocar: `login` de novo. Sair: `logout`. Ver usuário: `whoami`.
- **IAs / modo não-interativo:** defina `ZION_USER` e `ZION_PASSWORD` no ambiente (nunca imprima). O CLI grava o usuário no arquivo local após login ok, para não quebrar o fluxo. Para gravar: `printf '%s' "$ZION_PASSWORD" | python3 zion.py login --user "$ZION_USER" --password-stdin`. Nunca escreva a senha no chat/arquivos/logs.
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

## Fluxo padrão
1. `python3 zion.py listar AT` para ver o que existe.
2. `python3 zion.py digitacao AT` para levar os exames a Digitação (`--dry-run` antes se houver dúvida).
3. Leia os valores do papel/foto do analisador e monte o comando (`resultado`, `gaso` ou `hemo`).
4. **Sempre** rode com `--dry-run` primeiro e confira.
5. Salve (sem `--dry-run`).
6. **Sempre** confira a releitura que o CLI imprime (ou `ler AT`) e reporte ao usuário os valores gravados.

## Regras de digitação
- **Nunca liberar** resultado. O CLI só salva; não tente liberar por nenhum outro meio. Se aparecer confirmação de mudança para "Resultado Aprovado (Laudado)", cancele essa confirmação.
- **⚠️ sorologia ≠ teste rápido.** Sorologias (nome contendo "Sorologia", ou siglas em `EXAMES_EXTERNOS_BLOQUEADOS`: TOXG, TOXM, HBSAG, HCV, HBCM, HBCG, A-HBS, CMVG, CMVM, RUGE, RUME, HIV1/2, …) vão para **outro laboratório**. O CLI **recusa** digitar nelas em `resultado`/`hemo`/`gaso` — **sem override**, nem com `--forcar`. Não invente valor nem zere. Testes rápidos (`TRTOXO`, `HIV`, `TRS`, `TRHCV`) seguem normais.
- **Teste Rápido HIV (`HIV`):** TR2 só é feito se TR1 = REAGENTE. Se TR1 = NÃO REAGENTE, grave TR2 = **NÃO REALIZADO** (o CLI troca sozinho e avisa, inclusive se TR2 vier omitido ou como NR). Não confundir `HIV` (teste rápido) com `HIV1/2` (sorologia, bloqueada).
- **Teste Rápido Toxo (`TRTOXO`):** o campo principal (*Teste Rápido Toxo IgG/IgM*) tem **lista de opções vazia** no Tasy — por isso `TRTOXO=NÃO REAGENTE` falhava com `(opções: )`. Os valores reais são **Anticorpos IgG** e **Anticorpos IgM** (`REAGENTE` / `NÃO REAGENTE`). O CLI: `TRTOXO=NÃO REAGENTE` (também `NR`/`NEG`) → preenche IgG **e** IgM; se forem diferentes use `TRTOXO.IgG=` / `TRTOXO.IgM=`. **Não** é sorologia (`TOXG`/`TOXM`, bloqueadas).
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
**Nunca liberar.**

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
