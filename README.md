# zion-tasy-cli

> **Para IAs e usuários:** URL, usuário, perfil e setor já estão em `.env.example` e são carregados automaticamente. **Só falta a senha**: crie `.env` com `ZION_PASSWORD=...` e rode `python3 zion.py login`. Leia `AGENTS.md` antes de operar.


CLI em Python para operar o módulo de Laboratório do **Zion / Philips Tasy 5.04** (web) sem navegador. Com ele você:

- coloca atendimentos em **Digitação do Resultado**;
- digita e **salva** resultados (bioquímica, campos com várias partes, listas/texto, gasometria e hemograma);
- relê os valores depois de salvar e compara com o que foi enviado.

> ⚠️ O CLI **nunca libera** resultado. Ele só salva. Quem libera/laudo é sempre o profissional, pelo sistema.

## Instalação

```bash
python3 -m pip install -r requirements.txt   # só precisa de requests
```

## Variáveis de ambiente (obrigatórias)

| Variável | Exemplo | Descrição |
|---|---|---|
| `ZION_URL` | `https://seuhospital.zion-srv.com` | URL base do Zion, sem barra no final |
| `ZION_USER` | `nome.sobrenome` | Seu usuário do Tasy |
| `ZION_PASSWORD` | — | Sua senha. Nunca é impressa nem gravada |
| `ZION_PROFILE` | `Laboratório - Biomédico` | Nome **exato** do perfil que será ativado após o login |
| `ZION_SETOR` | `Serv. Laboratório Análises Clínicas` | (opcional) nome do setor, só para conferência/aviso |

A sessão fica em `.session.json` (permissão 600), ao lado do `zion.py`. O token é renovado e o login refeito automaticamente. Esse arquivo **nunca** deve ir para o git (já está no `.gitignore`).

## Comandos

Todos aceitam o número do atendimento (`AT`). Os valores podem usar ponto ou vírgula como decimal (prefira ponto no shell).

### `login`
Testa login e troca de perfil.
```bash
python3 zion.py login
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
- **Listas/texto** (tipagem, Coombs, EAS...): o valor precisa existir na lista do sistema; se não existir, o CLI recusa e mostra as opções válidas.
  ```bash
  python3 zion.py resultado 123456 --exame GP-TIP.abo=B --exame GP-TIP.rh=Positivo --exame COOD=Negativo
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
