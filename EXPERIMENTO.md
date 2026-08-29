# Experimento de medição — anatomia sobre o acervo

Nada aqui treina nada. O objetivo é produzir os números que decidem se
treinar é necessário.

---

## 0. A ordem, e por que ela é essa

O portão vem antes do detector **também na avaliação**. Não é escrúpulo
decorativo: se a avaliação rodasse o detector sobre todas as fotos de
criança para "medir a taxa de falso positivo em criança", ela faria
exatamente o que o sistema promete nunca fazer, e o número medido seria de
um pipeline que não é o de produção.

A pergunta certa não é *"o detector marca foto de criança?"* e sim:

> **Quantas fotos de criança o portão deixa passar, e o que o detector faz
> com essas?**

Isso é *risco residual*, e mede-se rodando o detector **só sobre as fotos
que o portão liberou** — ou seja, só sobre o que produção já veria. A
avaliação não faz nada que produção não faça.

Consequência prática: o experimento 0 (portão) bloqueia o experimento 1
(detector). Não dá para inverter.

---

## 1. Quadro amostral

Antes de amostrar, resolver uma inconsistência: os índices no diretório
não batem com 294.530 imagens.

| índice | linhas |
|---|---|
| `acervo.sqlite3` (`arquivos`) | 540 |
| `dedup_index_fase5.sqlite3` | 194.290 |
| `dedup_index.sqlite3` | 91.542 |

O quadro precisa ser **um** índice, com caminho + `sha256` + `phash` +
`width/height` + sinais de rosto, e é dele que sai toda amostra. Se os
294.530 são a união de fases, a união precisa ser materializada numa
tabela antes de qualquer sorteio — senão as probabilidades de inclusão
ficam desconhecidas e nenhuma estimativa de recall é válida.

**Deduplicação do quadro**: sortear sobre arquivos, não sobre imagens,
enviesa a amostra na direção do que foi copiado mais vezes. Sortear sobre
grupos de `phash` (um representante por grupo) e depois propagar o rótulo
para o grupo.

---

## 2. Experimento 0 — o portão (bloqueia todo o resto)

### O que existe hoje

`faces.identify: false`, `never_evaluate: []`, sem `referencias.pkl`.
Pelo código de `Gate.from_config`, isso deixa o portão **indisponível**, e
portanto a categoria inteira desligada. Este experimento é o que a liga.

### Passos

1. Montar pastas de referência para as pessoas protegidas (filha,
   enteada) e para os adultos da família. **Referência de criança precisa
   cobrir a variação de idade**: um vetor de bebê de 3 meses não protege a
   foto da mesma criança aos 4 anos. Pastas por pessoa **e por faixa de
   idade**.
2. Ligar `faces.identify` e reindexar para popular `protected_similarity`.
3. Rotular à mão um conjunto de **crianças** — alvo: 400 imagens, incluindo
   de propósito os casos difíceis: de costas, de longe, rosto parcial,
   foto escaneada, foto de foto, grupo grande, baixa luz.
4. Rodar **só o portão** sobre esse conjunto, nos dois modos.

### Números que saem

- **Recall do portão** = fração das fotos de criança que o portão veta.
  Este é o número de segurança do projeto inteiro.
- **Custo do portão** = fração do acervo adulto que o portão veta
  desnecessariamente (mede se a categoria ainda serve para alguma coisa).
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

```sql
CREATE TABLE anatomia (
  path TEXT PRIMARY KEY,
  avaliado INTEGER NOT NULL,
  motivo TEXT NOT NULL,          -- 'medido' ou o veto do portão
  versao_modelo TEXT,
  regioes TEXT,                  -- JSON: [{classe, confianca, caixa, area_rel}]
  conf_max REAL,                 -- desnormalizado, só para estratificar
  medido_em REAL
);
```

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

A costura que já existe (`policies.sensitive: {ativa: false, via: modelo}`)
ganha os campos do portão e da política de classes:

```yaml
politicas:
  sensivel:
    ativa: false            # segue desligada ate' o experimento 1 fechar
    via: modelo             # nunca 'cor'; a heuristica YCrCb foi descartada
    model: anatomia        # biblioteca satelite, deteccao por estrutura

    # ---- portao: protecao estrutural de crianca -------------------
    # Exige faces.identify=true e faces.never_evaluate preenchido.
    # Faltando qualquer um, a categoria inteira fica desligada.
    gate: standard         # standard | strict
    veto_threshold: 0.30       # ABAIXO de faces.protection_threshold, de proposito

    # ---- politica de classes: DECISAO NORMATIVA, declarada --------
    # Torso a mostra nao entra, em nenhum dos dois generos. Barriga, pes e
    # axilas sao praia e verao. Classe de genero por aparencia nunca entra.
    classes:
      FEMALE_GENITALIA_EXPOSED: 0.50
      MALE_GENITALIA_EXPOSED: 0.50
      ANUS_EXPOSED: 0.50
      BUTTOCKS_EXPOSED: 0.60
    min_area_ratio: 0.002
    min_labels: 1

    # A saida e' sempre CANDIDATA a validacao humana.
    caixa: sensivel
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
