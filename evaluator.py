r"""
anatomia.evaluator - the composition you cannot bypass, and the POLICY.

The one-line summaries below are in English, for anyone integrating this
library. The longer reasoning is in Portuguese, where it was written.

==========================================================================

PORQUE O PORTAO E O DETECTOR NAO SAO USADOS SOLTOS

  Se a biblioteca exportasse 'Detector.measure' como caminho normal, um
  dia alguem - eu, com pressa, num script de teste - chamaria o detector
  direto e a garantia estrutural sumiria sem barulho. Aqui a unica entrada
  publica e' Evaluator.evaluate, e ela chama o portao PRIMEIRO. Uma
  garantia que depende de disciplina nao e' uma garantia.

A POLITICA, E O JULGAMENTO QUE ELA CARREGA

  O detector devolve dezoito rotulos, entre eles BELLY_EXPOSED,
  FEET_EXPOSED, ARMPITS_EXPOSED, FEMALE_BREAST_EXPOSED e
  MALE_BREAST_EXPOSED. Escolher quais deles "contam" NAO e' engenharia:

    - barriga, pes e axilas a mostra sao praia, ginastica e verao. Entram
      na politica padrao? Nao. Entrariam num acervo de outra pessoa, com
      outro criterio? Talvez - e por isso a decisao mora em YAML.

    - torso masculino e feminino existem como rotulos SIMETRICOS no
      modelo. A assimetria - marcar um e nao o outro - nao vem do
      detector, vem de norma cultural. Se essa decisao ficasse escondida
      numa constante de codigo, viraria invisivel e ninguem discutiria.
      Escrita no YAML, ela pode ser lida, contestada e trocada.

    - FACE_FEMALE / FACE_MALE sao classificacao de genero por aparencia.
      NAO sao usadas por politica nenhuma aqui, e a lista padrao as ignora
      explicitamente em vez de simplesmente nao cita-las.

  A politica padrao e' ESTREITA de proposito: so' os rotulos anatomicos
  inequivocos. E' a leitura mais conservadora da assimetria de custo -
  marcar de menos e' chato; marcar foto de familia e' grave.

A SAIDA E' CANDIDATO, NUNCA CLASSIFICACAO

  Nenhum retorno desta biblioteca autoriza mover arquivo sozinho. O campo
  'always_review' e' True e nao ha' caminho que o desligue.
==========================================================================
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .detector import Detector
from .gate import Gate
from .types import Candidate, Measurement


# --------------------------------------------------------------------
# DEFAULT POLICY
#
# Ponto de partida, nao verdade - e, ao contrario dos numeros do projeto
# principal, estes AINDA NAO FORAM MEDIDOS neste acervo. Sao o que se
# leva para o experimento 1, nao o que se leva para producao.
#
# 'labels' mapeia rotulo cru -> confianca minima. Fora do mapa, o rotulo
# e' sinal registrado e nada mais.
# --------------------------------------------------------------------
DEFAULT_POLICY = {
    "labels": {
        "FEMALE_GENITALIA_EXPOSED": 0.50,
        "MALE_GENITALIA_EXPOSED": 0.50,
        "ANUS_EXPOSED": 0.50,
        "BUTTOCKS_EXPOSED": 0.60,
    },
    # DECISAO NORMATIVA, declarada: torso a mostra nao entra na politica
    # padrao, em nenhum dos dois generos. Quem quiser a categoria mais
    # ampla acrescenta o rotulo no YAML e assume a escolha por escrito.
    "ignored_labels": [
        "FEMALE_BREAST_EXPOSED", "MALE_BREAST_EXPOSED",
        "BELLY_EXPOSED", "FEET_EXPOSED", "ARMPITS_EXPOSED",
        "FACE_FEMALE", "FACE_MALE",          # genero por aparencia: nunca
    ],
    # Regiao minuscula costuma ser deteccao em textura de fundo. O numero
    # e' chute ate' o experimento 1 desenhar a curva area x precisao.
    "min_area_ratio": 0.002,
    # Quantos rotulos distintos da lista precisam disparar. 1 e' o padrao;
    # 2 e' um ponto de operacao mais conservador que o experimento avalia.
    "min_labels": 1,
}


@dataclass
class Evaluator:
    """Gate + detector + policy. The library's only public entry point."""

    gate: Gate = field(default_factory=Gate)
    detector: Detector = field(default_factory=Detector)
    policy: dict = field(default_factory=lambda: dict(DEFAULT_POLICY))

    # -- measurement, with the gate in front -------------------------
    def evaluate(self, rec: dict, source=None) -> Measurement:
        """rec: one index row. source: path or image, optional.

        A ordem aqui E' a garantia. Nao inverta, nao adicione atalho, nao
        aceite parametro que pule o portao."""
        allowed, reason = self.gate.allows(rec)
        if not allowed:
            return Measurement(evaluated=False, reason=reason)
        dim = (rec.get("width"), rec.get("height"))
        return self.detector.measure(
            source if source is not None else rec["path"],
            dim if all(dim) else None)

    # -- policy ------------------------------------------------------
    def judge(self, m: Measurement) -> Candidate:
        """Measurement -> Candidate. A PURE function of measurement+policy.

        Ser pura e' o que torna a varredura de limiar gratuita: com as
        regioes gravadas no indice, testar cem politicas custa cem
        consultas, nao cem passadas de GPU. 'Limiar nao se chuta' so' e'
        praticavel se recalcular for barato."""
        if not m.evaluated:
            return Candidate(False, m.reason)

        thresholds = self.policy.get("labels", {})
        ignored = set(self.policy.get("ignored_labels", []))
        min_area = float(self.policy.get("min_area_ratio", 0.0))
        min_labels = int(self.policy.get("min_labels", 1))

        triggered, conf = {}, 0.0
        for r in m.regions:
            if r.label in ignored or r.label not in thresholds:
                continue
            if r.confidence < float(thresholds[r.label]):
                continue
            if r.area_ratio and r.area_ratio < min_area:
                continue
            triggered[r.label] = max(triggered.get(r.label, 0.0), r.confidence)
            conf = max(conf, r.confidence)

        if len(triggered) < min_labels:
            return Candidate(False, "below_policy")
        return Candidate(True, "anatomy_exposed", tuple(sorted(triggered)),
                         conf)

    # -- shortcut ----------------------------------------------------
    def evaluate_and_judge(self, rec: dict, source=None):
        m = self.evaluate(rec, source)
        return m, self.judge(m)
