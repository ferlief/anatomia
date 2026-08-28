r"""
==========================================================================
 anatomia.avaliador - a composicao que nao da' para burlar, e a POLITICA
==========================================================================

PORQUE O PORTAO E O DETECTOR NAO SAO USADOS SOLTOS

  Se a biblioteca exportasse 'Detector.medir' como caminho normal, um dia
  alguem - eu, com pressa, num script de teste - chamaria o detector
  direto e a garantia estrutural sumiria sem barulho. Aqui a unica entrada
  publica e' Avaliador.avaliar, e ela chama o portao PRIMEIRO. Uma
  garantia que depende de disciplina nao e' uma garantia.

A POLITICA, E O JULGAMENTO QUE ELA CARREGA

  O detector devolve dezoito classes, entre elas BELLY_EXPOSED,
  FEET_EXPOSED, ARMPITS_EXPOSED, FEMALE_BREAST_EXPOSED e
  MALE_BREAST_EXPOSED. Escolher quais delas "contam" NAO e' engenharia:

    - barriga, pes e axilas a mostra sao praia, ginastica e verao. Entram
      na politica padrao? Nao. Entrariam num acervo de outra pessoa, com
      outro criterio? Talvez - e por isso a decisao mora em YAML.

    - torso masculino e feminino existem como classes SIMETRICAS no
      modelo. A assimetria - marcar um e nao o outro - nao vem do
      detector, vem de norma cultural. Se essa decisao ficasse escondida
      numa constante de codigo, viraria invisivel e ninguem discutiria.
      Escrita no YAML, ela pode ser lida, contestada e trocada.

    - FACE_FEMALE / FACE_MALE sao classificacao de genero por aparencia.
      NAO sao usadas por politica nenhuma aqui, e a lista padrao as ignora
      explicitamente em vez de simplesmente nao cita-las.

  A politica padrao e' ESTREITA de proposito: so' as classes anatomicas
  inequivocas. E' a leitura mais conservadora da assimetria de custo -
  marcar de menos e' chato; marcar foto de familia e' grave.

A SAIDA E' CANDIDATO, NUNCA CLASSIFICACAO

  Nenhum retorno desta biblioteca autoriza mover arquivo sozinho. O campo
  'revisar_sempre' e' True e nao ha' caminho que o desligue.
==========================================================================
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .detector import Detector
from .portao import Portao
from .tipos import Candidato, Medida


# --------------------------------------------------------------------
# POLITICA PADRAO
#
# Ponto de partida, nao verdade - e, ao contrario dos numeros do Acervo,
# estes AINDA NAO FORAM MEDIDOS neste acervo. Sao o que se leva para o
# experimento 1, nao o que se leva para producao.
#
# 'classes' mapeia rotulo cru -> confianca minima. Fora do mapa, a classe
# e' sinal registrado e nada mais.
# --------------------------------------------------------------------
POLITICA_PADRAO = {
    "classes": {
        "FEMALE_GENITALIA_EXPOSED": 0.50,
        "MALE_GENITALIA_EXPOSED": 0.50,
        "ANUS_EXPOSED": 0.50,
        "BUTTOCKS_EXPOSED": 0.60,
    },
    # DECISAO NORMATIVA, declarada: torso a mostra nao entra na politica
    # padrao, em nenhum dos dois generos. Quem quiser a categoria mais
    # ampla acrescenta a classe no YAML e assume a escolha por escrito.
    "classes_ignoradas": [
        "FEMALE_BREAST_EXPOSED", "MALE_BREAST_EXPOSED",
        "BELLY_EXPOSED", "FEET_EXPOSED", "ARMPITS_EXPOSED",
        "FACE_FEMALE", "FACE_MALE",          # genero por aparencia: nunca
    ],
    # Regiao minuscula costuma ser deteccao em textura de fundo. O numero
    # e' chute ate' o experimento 1 desenhar a curva area x precisao.
    "area_minima": 0.002,
    # Quantas classes distintas da lista precisam disparar. 1 e' o padrao;
    # 2 e' um ponto de operacao mais conservador que o experimento avalia.
    "classes_minimas": 1,
}


@dataclass
class Avaliador:
    """Portao + detector + politica. Unica entrada publica da biblioteca."""

    portao: Portao = field(default_factory=Portao)
    detector: Detector = field(default_factory=Detector)
    politica: dict = field(default_factory=lambda: dict(POLITICA_PADRAO))

    # -- medida (com portao na frente) ------------------------------
    def avaliar(self, reg: dict, fonte=None) -> Medida:
        """reg: linha do indice do Acervo. fonte: caminho/imagem, opcional.

        A ordem aqui E' a garantia. Nao inverta, nao adicione atalho, nao
        aceite parametro que pule o portao."""
        pode, motivo = self.portao.libera(reg)
        if not pode:
            return Medida(avaliado=False, motivo=motivo)
        dim = (reg.get("width"), reg.get("height"))
        return self.detector.medir(
            fonte if fonte is not None else reg["path"],
            dim if all(dim) else None)

    # -- politica ---------------------------------------------------
    def julgar(self, m: Medida) -> Candidato:
        """Medida -> Candidato. Funcao PURA da medida e da politica.

        Ser pura e' o que torna a varredura de limiar gratuita: com as
        regioes gravadas no indice, testar cem politicas custa cem
        consultas, nao cem passadas de GPU. 'Limiar nao se chuta' so' e'
        praticavel se recalcular for barato."""
        if not m.avaliado:
            return Candidato(False, m.motivo)

        limiares = self.politica.get("classes", {})
        ignoradas = set(self.politica.get("classes_ignoradas", []))
        area_min = float(self.politica.get("area_minima", 0.0))
        n_min = int(self.politica.get("classes_minimas", 1))

        disparadas, conf = {}, 0.0
        for r in m.regioes:
            if r.classe in ignoradas or r.classe not in limiares:
                continue
            if r.confianca < float(limiares[r.classe]):
                continue
            if r.area_rel and r.area_rel < area_min:
                continue
            disparadas[r.classe] = max(disparadas.get(r.classe, 0.0),
                                       r.confianca)
            conf = max(conf, r.confianca)

        if len(disparadas) < n_min:
            return Candidato(False, "abaixo_da_politica")
        return Candidato(True, "anatomia_exposta",
                         tuple(sorted(disparadas)), conf)

    # -- atalho -----------------------------------------------------
    def avaliar_e_julgar(self, reg: dict, fonte=None):
        m = self.avaliar(reg, fonte)
        return m, self.julgar(m)
