# anatomia

Detecção de conteúdo sensível em imagens **por estrutura corporal**, não por cor de pele.

Detectores clássicos de nudez usam fração de pele em espaço de cor. Isso falha de um jeito previsível: quanto mais escura a pele, mais área é classificada como "pele", e mais falso positivo o sistema produz. O viés não é acidental — é a métrica.

Esta biblioteca troca a métrica: mede **regiões anatômicas detectadas**, com caixa, classe e confiança.

## Duas regras que definem a API

**1. Devolve medida, nunca veredito.** A biblioteca diz "região `BUTTOCKS_EXPOSED`, confiança 0.71, 4% da imagem". Ela não diz "esta imagem é sensível". Isso é política, mora em YAML no consumidor, e pode ser lida e trocada sem tocar em código.

**2. O portão vem antes do detector.** Se o portão veta uma imagem, nenhuma medida é calculada — não existe caminho no código em que o detector veja uma imagem vetada. A proteção é a ordem das operações, não um julgamento do modelo. Toda dúvida veta; sinal ausente veta; portão indisponível veta tudo.

## Estado

Pré-medição. Nada aqui foi validado ainda — ver `EXPERIMENTO.md`, que define os números que decidem se treinar é necessário. O critério de aceitação está escrito **antes** de rodar, de propósito.

## Licença

AGPLv3. Pesos treinados, se houver, só com material sem pessoas identificáveis.
