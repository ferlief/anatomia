# Contribuindo com anatomia

## Mensagens de commit

**Inglês, sempre — [Conventional Commits](https://www.conventionalcommits.org/), modo imperativo.** Não é sobre quem lê este repositório; é o padrão de quem programa de forma séria hoje, com ou sem audiência externa. Vale a partir de agora — histórico anterior (que misturava inglês e português) fica como está.

```
<type>(<scope>): short imperative summary, ≤50 chars

Body explaining WHY this change exists, not what changed — the diff
already shows what. Wrap at ~72 columns.
```

Tipos comuns: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `perf`, `build`, `ci`. Escopo é opcional — use quando desambiguar (`fix(gate): ...`).

Referências: [conventionalcommits.org](https://www.conventionalcommits.org/) para o formato, as 7 regras de Chris Beams ("How to Write a Git Commit Message") para a prosa. Sem linha de atribuição a ferramenta de geração de código.

## Antes de abrir um PR

Este repositório está em **pre-measurement** (ver README) — a tese central ainda não foi medida. Mudança de código sem passar por `EXPERIMENTO.md` corre o risco de invalidar um critério de aceitação já registrado. Se a mudança afeta `gate.py`, `detector.py` ou `evaluator.py`, releia os 5 invariantes do `CLAUDE.md` antes.
