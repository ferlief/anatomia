# Contribuindo com anatomia

## Idioma dos commits

Mesma divisão que já vale para identificador e docstring (ver `CLAUDE.md`): **inglês para o que integra, português para o que explica.**

- Commit que muda **API pública, identificador, comportamento observável por quem consome a biblioteca**: mensagem em **inglês**.
  Exemplo real: `rename public API to English; keep design reasoning in Portuguese`.
- Commit sobre **raciocínio interno — `EXPERIMENTO.md`, cabeçalho de módulo, decisão de projeto**: mensagem em **português**.
  Exemplo real: `deteccao de conteudo sensivel por anatomia, nao por cor de pele`.

Não é regra nova, é a mesma regra de sempre estendida até o histórico do git. Na dúvida: se a mudança aparece pra quem só consome `anatomia` de fora, é inglês; se só aparece pra quem lê o design por dentro, é português.

## Formato

- Modo imperativo, foco no **porquê** da mudança — o diff já mostra o quê.
- Sem prefixo obrigatório (`feat:`, `fix:`); mensagem descritiva de uma linha é o padrão já estabelecido no histórico.
- Sem linha de atribuição a ferramenta de geração de código.

## Antes de abrir um PR

Este repositório está em **pre-measurement** (ver README) — a tese central ainda não foi medida. Mudança de código sem passar por `EXPERIMENTO.md` corre o risco de invalidar um critério de aceitação já registrado. Se a mudança afeta `gate.py`, `detector.py` ou `evaluator.py`, releia os 5 invariantes do `CLAUDE.md` antes.
