# Guia para agentes de IA — zion-tasy-cli

Você vai operar o laboratório no Zion/Tasy via `zion.py`. Siga estas regras sem exceção.

## Pré-requisitos
- `ZION_URL`, `ZION_USER`, `ZION_PASSWORD`, `ZION_PROFILE` definidos no ambiente. **Nunca** imprima, registre ou peça a senha em texto no chat; nunca leia `.session.json` para exibir tokens.
- Use `python3` (pode não existir `python`).
- Comunique-se com o usuário em português do Brasil.

## Fluxo padrão
1. `python3 zion.py listar AT` para ver o que existe.
2. `python3 zion.py digitacao AT` para levar os exames a Digitação (`--dry-run` antes se houver dúvida).
3. Leia os valores do papel/foto do analisador e monte o comando (`resultado`, `gaso` ou `hemo`).
4. **Sempre** rode com `--dry-run` primeiro e confira.
5. Salve (sem `--dry-run`).
6. **Sempre** confira a releitura que o CLI imprime (ou `ler AT`) e reporte ao usuário os valores gravados.

## Regras de digitação
- **Nunca liberar** resultado. O CLI só salva; não tente liberar por nenhum outro meio. Se aparecer confirmação de mudança para "Resultado Aprovado (Laudado)", cancele essa confirmação.
- **Ureia:** só a parte inteira, truncada (30,56 → 30; 11,72 → 11).
- **Bilirrubina indireta:** aceite o valor recalculado pelo sistema (total − direta), mesmo que difira do aparelho por arredondamento.
- **Hemograma:** valores como no impresso; plaquetas em 10⁹/L (`--plt 174`); WBC em 10³/µL (`--wbc 14.06`); percentuais arredondados fechando 100 (o CLI faz).
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
