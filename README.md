# zion-tasy-cli

> **Para IAs e usuários:** URL, perfil e setor padrão já estão em `.env.example`. Na **primeira vez**, rode `python3 zion.py login` — o CLI pede usuário e senha, valida e grava em `~/.config/zion-cli/credentials.json` (não precisa digitar de novo). IAs/CI: exporte `ZION_USER` e `ZION_PASSWORD`. Leia `AGENTS.md` antes de operar. Fila: `python3 zion.py fila --resumo`.


CLI em Python para operar o módulo de Laboratório do **Zion / Philips Tasy 5.04** (web) sem navegador. Com ele você:

- coloca atendimentos em **Digitação do Resultado**;
- digita e **salva** resultados (bioquímica, campos com várias partes, listas/texto, gasometria e hemograma);
- relê os valores depois de salvar e compara com o que foi enviado.

> ⚠️ O CLI **nunca libera** resultado. Ele só salva. Quem libera/laudo é sempre o profissional, pelo sistema.

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

Precedência de usuário/senha: `--user` / `ZION_USER`+`ZION_PASSWORD` (ambiente) → arquivo salvo → prompt interativo. Se a senha salva falhar (senha trocada), o CLI pede de novo e regrava. IAs e scripts devem usar só as variáveis de ambiente (sem prompt).

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

### `listar AT`
Mostra paciente, setor, leito e os exames do atendimento por fase/status.
```bash
python3 zion.py listar 123456
```

### `digitacao AT [--dry-run] [--desde STATUS]`
Leva os exames do atendimento até **Digitação do Resultado** (status 30), passando pelas fases intermediárias (10 Pendente coleta → 20 Material Coletado → 25 Em Análise → 26 Interfaceamento → 30).
Quando o sistema responde `IE_GERAR_AMOSTRA=S`, o CLI segue a mesma sequência que o navegador faz (sem gerar amostra nova). Qualquer outra resposta não mapeada faz o CLI **parar**.
```bash
python3 zion.py digitacao 123456 --dry-run
python3 zion.py digitacao 123456
```

### `ler AT`
Lê os valores salvos de todos os exames em Digitação.
```bash
python3 zion.py ler 123456
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
