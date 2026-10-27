# Guia para agentes de IA — zion-tasy-cli

Você vai operar o laboratório no Zion/Tasy via `zion.py`. Siga estas regras sem exceção.

## Configuração (LEIA PRIMEIRO)
**Não pergunte URL, usuário, perfil nem setor ao usuário.** Eles já estão no arquivo `.env.example` deste repositório, e o `zion.py` carrega esse arquivo sozinho:
- URL: `https://sbsj.zion-srv.com`
- Usuário: `alisson.siqueira`
- Perfil: `HMMCC - Laboratório - Biomédico`
- Setor: `HMMCC - Serv. Laboratório Análises Clínicas`

A **única** coisa que falta é a senha. Para configurar:
1. `pip install -r requirements.txt`
2. Crie o arquivo `.env` na pasta do repositório com uma linha: `ZION_PASSWORD=...` (o usuário fornece a senha; se o terminal for interativo, o CLI também pede a senha com `getpass`).
3. Teste: `python3 zion.py login`.

Nunca imprima a senha, nunca a coloque no chat, em commits ou logs; nunca leia `.session.json` para exibir tokens. O `.env` está no `.gitignore`.
- Use `python3` (pode não existir `python`).
- Comunique-se com o usuário em português do Brasil.

## Ver a fila (sem número de atendimento)
Quando perguntarem "quantos pacientes/exames pendentes", "o que tem na fila", etc., **não peça número de atendimento**. Use:
- `python3 zion.py fila --resumo`: contagem por etapa (10 Pendente coleta, 20 Material Coletado, 25 Em Análise, 26 Interfaceamento, 30 Digitação do Resultado).
- `python3 zion.py fila`: lista atendimentos (paciente, setor, leito) por etapa.
- `python3 zion.py fila --status 30 --exames`: amostras e exames de uma etapa (ex.: tudo que está esperando digitação).
Janela: pedidos dos últimos 4 dias.

## Fluxo padrão
1. `python3 zion.py listar AT` para ver o que existe.
2. `python3 zion.py digitacao AT` para levar os exames a Digitação (`--dry-run` antes se houver dúvida).
3. Leia os valores do papel/foto do analisador e monte o comando (`resultado`, `gaso` ou `hemo`).
4. **Sempre** rode com `--dry-run` primeiro e confira.
5. Salve (sem `--dry-run`).
6. **Sempre** confira a releitura que o CLI imprime (ou `ler AT`) e reporte ao usuário os valores gravados.

## Regras de digitação
- **Nunca liberar** resultado. O CLI só salva; não tente liberar por nenhum outro meio. Se aparecer confirmação de mudança para "Resultado Aprovado (Laudado)", cancele essa confirmação.
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
- Listas/texto (Tipagem `GP-TIP.abo`/`.rh`, Coombs `COOD`, EAS): use valores que existam na lista; se o CLI recusar, mostre as opções ao usuário.
- Em dúvida sobre unidade/fator (ex.: sedimento urinário "x1000"), **pergunte** antes de salvar.

## Nunca
- Liberar resultados.
- Clicar "Cancelar" na tela de resultado se estiver no navegador (descarta alterações não salvas).
- Versionar ou compartilhar `.session.json`, HAR, payloads (`--dump-payload`) ou qualquer dado de paciente.
