# Measurement experiment — anatomia on data

Nothing here trains anything. The goal is to produce the numbers that decide whether training is necessary.

---

## 0. The order, and why

The gate comes before the detector **also in the evaluation**. It is not a decorative scruple: if the evaluation ran the detector on all children's photos to "measure the false positive rate on children," it would do exactly what the system promises never to do, and the measured number would be from a pipeline that isn't the production one.

The right question isn't *"does the detector flag children's photos?"* but rather:

>**How many children's photos does the gate let through, and what does the detector do with >them?**

*This is residual risk*, and it is measured by running the detector **only on the photos the gate let through** — that is, only on what production would already see. The evaluation does nothing that production doesn't do.

Practical consequence: experiment 0 (gate) blocks experiment 1 (detector). You cannot invert them.

---

## 1. Sampling Frame

Before sampling, resolve an inconsistency: the directory indices don't match 294,530 images.


| índice | linhas |
|---|---|
| `acervo.sqlite3` (`arquivos`) | 540 |
| `dedup_index_fase5.sqlite3` | 194.290 |
| `dedup_index.sqlite3` | 91.542 |

The frame needs to be **one** index, with path + `sha256` + `phash` + face signals, and every sample must come from it. If the 294,530 are the union of phases, the union needs to be materialized in a table before any drawing — otherwise the inclusion probabilities remain unknown and no recall estimate is valid.

**Frame deduplication**: drawing over files, not images, biases the 
sample toward what was copied the most. Draw over `phash` groups 
(one representative per group) and then propagate the label to the group.

---

## 2. Experiment 0 — the gate (blocks everything else)

### What exists today

`faces.identify: false`, `never_evaluate: []`, without `referencias.pkl`.
By the `Gate.from_config`, code, this makes the gate **unavailable**, 
and therefore the entire category turned off. This experiment is what 
turns it on.

### Steps

1. Set up reference folders for protected people (daughter, stepdaughter)
and for the adults in the family. **Child references need to cover age 
variation**: a 3-month-old baby vector does not protect the photo of the
same child at 4 years old. Folders per person 
**and by age group**.
2. Turn on `faces.identify` and reindex to populate `protected_similarity`.
3. Hand-label a set of **children** — target: 400 images, intentionally 
including hard cases: from the back, from a distance, partial face, 
scanned photo, photo of a photo, large group, low light.
4. Run **only the gate** on this set, in both modes.

### Resulting metrics

- **Gate recall** = fraction of children's photos that the gate vetoes. 
  This is the safety number for the entire project.
- **Gate cost** = fraction of the adult archive that the gate vetoes 
  unnecessarily (measures if the category is still useful for anything).
- Tabela `standard` x `strict` nas duas colunas acima — a escolha do modo
  sai daí, não de argumento.

### Quanto vale 400

Zero falhas em 400 dá, pela regra de três, um limite superior de ~0,75% a
95% de confiança. Ou seja: mesmo com resultado perfeito, o máximo que se
pode afirmar é *"o portão deixa passar menos de 1% das fotos de criança"*.
Para afirmar menos de 0,1% seriam ~3.000 imagens rotuladas. Vale escrever
o limite junto do resultado, sempre — é a diferença entre publicar
metodologia e publicar propaganda.

### Mudança necessária no núcleo (para o modo estrito)

Hoje `indexar()` guarda só o **máximo** das similaridades (`sim_in`,
`sim_ex`, `protected_similarity`). O modo estrito precisa do **mínimo por
imagem**: "o rosto menos reconhecido desta foto ainda casa com alguém
conhecido?".

Sinal novo, em `CAMPOS`: `min_known_similarity` — para cada rosto, a melhor
similaridade contra o conjunto de referências conhecidas; da imagem, o
**menor** desses valores. `NULL` quando não há rosto. Sem esse campo, o
modo estrito veta tudo (falha fechada, por desenho).

---

## 3. Experimento 1 — o que o NudeNet pronto faz

### Passada completa, atrás do portão

Rodar `Evaluator.evaluate` sobre o quadro inteiro. Gravar **as regiões
cruas**, sem filtro de confiança, em tabela lateral:

As colunas seguem os nomes que `Measurement.as_dict()` emite — se
divergirem, o `INSERT` não casa com nenhuma chave do dicionário:

```sql
CREATE TABLE anatomia (
  path TEXT PRIMARY KEY,
  evaluated INTEGER NOT NULL,
  reason TEXT NOT NULL,          -- 'measured' ou o motivo do veto
  model_version TEXT,
  regions TEXT,                  -- JSON: [{label, confidence, box, area_ratio}]
  ms REAL,                       -- tempo de inferência, para orçamento
  max_confidence REAL,           -- desnormalizado, só para estratificar
  medido_em REAL
);
```

`max_confidence` não vem do `as_dict()` — é a propriedade de mesmo nome,
calculada na hora da escrita. Todas as outras são cópia direta.

Gravar cru é o que torna "limiar não se chuta" praticável: varrer cem
políticas depois vira cem `SELECT`, não cem passadas de GPU. O custo é
uma passada só — em 320n com onnxruntime o gargalo é decodificar JPEG, não
inferir; dá para rodar numa noite.

### Amostra estratificada

Prevalência esperada de conteúdo adulto num acervo pessoal: baixa,
provavelmente < 1%. Amostra aleatória simples de 1.000 imagens traria ~5
positivos — inútil para estimar recall. Então: estratos com probabilidade
de inclusão **conhecida**, e reponderação de Horvitz-Thompson na hora de
somar.

| estrato | definição | n |
|---|---|---|
| A | aleatório do quadro liberado pelo portão | 600 |
| B | `conf_max ≥ limiar` (os candidatos) | 300 |
| C | banda cinzenta, `0.2 ≤ conf_max < limiar` | 200 |
| D | CLIP marca / NudeNet não marca | 200 |
| E | crianças que o portão liberou (risco residual) | tudo |
| F | negativos difíceis conhecidos | 250 |

**Estrato F** é a lista de erros que você já viu: praia e piscina,
academia, amamentação, diagrama de anatomia muscular (o que o CLIP marcou),
arte e pintura, pele em close, esporte, fantasia de carnaval, ultrassom.
Não é amostra aleatória e não entra na estimativa populacional — entra na
tabela de erros por tipo, que é o que orienta decisão de treino.

**Estrato D** é a sonda de recall. Com dois detectores quase independentes
(NudeNet e o CLIP de `semantico.py`), captura-recaptura estima o total de
positivos: `N̂ = n₁·n₂/n₁₂`. A independência é falsa — os dois erram nas
mesmas imagens difíceis — então `N̂` é subestimado e o recall calculado a
partir dele é **otimista**. Publicar as duas estimativas (HT pelos
estratos e captura-recaptura) e a distância entre elas vale mais que
publicar uma só com cara de exata.

### Métricas

1. **Precisão** no ponto de operação, com intervalo de Wilson.
2. **Recall**, pelos dois métodos, com a diferença explícita.
3. **Crianças entre os candidatos** — antes e depois do portão. O "antes"
   é contrafactual, calculado sobre o estrato E: quantas seriam marcadas
   se o portão não existisse. É a medida do valor do portão.
4. **Erros por classe**: qual classe do detector produz o falso positivo.
   Se 80% vier de `BUTTOCKS_EXPOSED` em foto de praia, a correção é
   política (tirar a classe), não treino.
5. **Curva de custo**: varrendo confiança e área, plotar *candidatos
   perdidos* × *fotos de criança marcadas*. O ponto de operação sai daqui,
   depois de olhar. Não antes.

---

## 4. Experimento 2 — a tese, medida

Três abordagens, **mesmo conjunto rotulado, mesmos rótulos**:

| abordagem | estado |
|---|---|
| fração de pele YCrCb | já implementada; `pele_frac` ainda está em `acervo.sqlite3` |
| CLIP zero-shot | já implementado em `acervo/semantico.py` |
| NudeNet (anatomia) | este experimento |

Isso produz a tabela que é o argumento publicável do projeto — precisão,
recall e taxa de falso positivo em criança, lado a lado, no mesmo acervo.

### E a parte que falta para a tese fechar

"Anatomia é invariante a cor" vale para a *geometria*, não para o *modelo*:
o NudeNet é YOLO treinado em imagens da web, e detectores assim têm
desempenho desigual documentado entre tons de pele e condições de luz — não
por medirem cor, mas pelo desbalanço do treino.

Então a tese precisa de um número, e ele vem do mesmo desenho pareado que
você já planejou para o eixo cultural: **pares casados por conteúdo**
(mesma cena, mesmo enquadramento, mesma roupa) variando tom de pele e
iluminação, medindo Δ na taxa de marcação. Sem esse Δ, "mais justo" é
hipótese; com ele, é resultado.

Onde arrumar pares casados sem usar pessoas identificáveis do acervo:
conjuntos abertos com anotação de tom (FACET, MIAP/Open Images) para o
eixo de pele, e material sintético pareado para o resto. Cai direto na sua
regra: avaliar com o acervo, medir viés com dados abertos.

---

## 5. Protocolo de rotulagem

Rótulos, não binário:

- `nada` — sem pessoa, ou pessoa vestida
- `nudez_adulto` — anatomia exposta, adulto
- `sugestivo_vestido` — a categoria fuzzy; **rotular separado e decidir
  depois se conta**, nunca misturar com nudez na hora de rotular
- `crianca_presente` — bandeira ortogonal, marcada junto com qualquer outra
- `arte_diagrama_medico` — pintura, escultura, ilustração, diagrama
- `ambiguo` — e o motivo, em texto livre

Regras do protocolo:

1. **Rotular às cegas.** Sem ver a saída do modelo. Ver o score antes
   ancora o rótulo e a precisão medida vira ficção.
2. **Mosaico primeiro.** A grade de miniaturas de `app.py` já serve; vira
   um modo de rotulagem. Foi olhando que você descobriu que os rótulos
   estavam errados, não o modelo.
3. **Reteste de concordância.** 10% do conjunto, rotulado de novo em outro
   dia, sem ver o rótulo anterior. Publicar a concordância consigo mesma.
   Se ela for 0,85, nenhuma diferença de 3 pontos entre abordagens
   significa coisa alguma — e é bom saber disso antes de escrever a
   conclusão.
4. Rótulo é versionado e guardado por `sha256`, não por caminho: o
   Acervo move arquivos.

---

## 6. Critérios de aceitação, escritos antes de rodar

Pré-registrar o que é "bom o bastante" não é a mesma coisa que chutar
limiar. O limiar sai da curva, depois de olhar; o critério é o nível de
qualidade aceitável, e defini-lo depois de ver o resultado é como se
escolhe o número que confirma o que se queria.

**NudeNet pronto basta se, e só se:**

- crianças entre os candidatos: **0** em ≥ 300 candidatos revisados
  (limite superior ~1%), e
- precisão ≥ 60% no ponto de operação, e
- recall estimado ≥ 50% pelo método mais pessimista dos dois, e
- nenhuma classe isolada responder por > 50% dos falsos positivos sem que
  removê-la resolva.

**Falhando o primeiro critério**, a resposta não é treinar: é apertar o
portão. Treino não conserta ordem de operações.

**Falhando só precisão ou recall**, tentar nesta ordem, medindo a cada
passo: (a) mudar a lista de classes, (b) mudar limiar por classe e área,
(c) exigir 2 classes, (d) combinar com a margem do CLIP, (e) só então
cogitar treino — e, se chegar lá, treino só com material sem pessoas
identificáveis, conforme a regra do projeto.

---

## 7. Como pluga no Acervo

As chaves abaixo são **exatamente** as que `Gate.from_config` e
`Evaluator.judge` leem. Copiar este bloco trocando um nome produz um
portão indisponível sem mensagem de erro:

```yaml
policies:
  sensitive:
    enabled: false          # segue desligada ate' o experimento 1 fechar
    via: model              # nunca 'cor'; a heuristica YCrCb foi descartada
    model: anatomia         # biblioteca satelite, deteccao por estrutura

    # ---- portao: protecao estrutural de crianca -------------------
    # Exige faces.identify=true e faces.never_evaluate preenchido.
    # Faltando qualquer um, a categoria inteira fica desligada.
    gate: standard          # standard | strict
    veto_threshold: 0.30    # ABAIXO de faces.protection_threshold, de proposito
    identification_threshold: 0.55   # so' o modo strict usa; ACIMA do veto

    # ---- politica de rotulos: DECISAO NORMATIVA, declarada --------
    # Torso a mostra nao entra, em nenhum dos dois generos. Barriga, pes e
    # axilas sao praia e verao. Rotulo de genero por aparencia nunca entra.
    labels:
      FEMALE_GENITALIA_EXPOSED: 0.50
      MALE_GENITALIA_EXPOSED: 0.50
      ANUS_EXPOSED: 0.50
      BUTTOCKS_EXPOSED: 0.60

    # A lista abaixo e' onde a decisao normativa fica VISIVEL. Sem ela,
    # o julgamento existe so' no codigo e ninguem o discute.
    ignored_labels:
      - FEMALE_BREAST_EXPOSED
      - MALE_BREAST_EXPOSED
      - BELLY_EXPOSED
      - FEET_EXPOSED
      - ARMPITS_EXPOSED
      - FACE_FEMALE          # genero por aparencia: nunca
      - FACE_MALE

    min_area_ratio: 0.002
    min_labels: 1

    # A saida e' sempre CANDIDATA a validacao humana.
    box: sensitive
```

### Onde entra no motor

Em `montar_plano`, depois de `classifica_conteudo` e `classifica_pessoa` —
`sensivel` é a única categoria de conteúdo que se aplica a foto **com**
rosto, então não pode ficar atrás da guarda `rosto_detectado` de
[nucleo.py:397](acervo/nucleo.py:397).

```python
if caixa is None:
    caixa, motivo = self.classifica_sensivel(r)   # le a tabela 'anatomia'
```

`classifica_sensivel` lê só sinais já persistidos e aplica
`Evaluator.judge` — função pura. O plano continua sendo função pura do
índice, e trocar a política no YAML não obriga a recalcular nada.

### O que precisa mudar no núcleo

1. `CAMPOS` + `min_known_similarity` (modo estrito) — seção 2.
2. Tabela lateral `anatomia` — seção 3.
3. Propagação de veto por grupo: `Gate.propagate_veto` aplicado sobre a
   saída de `agrupar()` antes de julgar. Sem isso a cópia borrada da mesma
   foto passa pelo portão que a cópia nítida vetou.
4. `descreve_vies()` ganha a linha da categoria sensível: detector de
   anatomia tem desempenho desigual documentado entre tons de pele e tipos
   de corpo; a saída é candidata a revisão, nunca exclusão automática.

---

## 8. Ordem de execução

1. Referências de pessoa protegida, por faixa de idade → `identificar: true`
   → reindexar.
2. Rotular o conjunto de crianças (400).
3. **Experimento 0.** Se o recall do portão não fechar, para aqui.
4. `min_known_similarity` no núcleo, se o modo estrito for o escolhido.
5. `pip install nudenet` → passada completa atrás do portão → tabela `anatomia`.
6. Sortear os estratos, rotular às cegas, reteste de 10%.
7. **Experimento 1.** Curvas, tabela de erros por classe, ponto de operação.
8. **Experimento 2.** Três abordagens lado a lado + Δ por tom de pele.
9. Só então: a conversa sobre treinar.
