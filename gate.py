r"""
anatomia.gate - the structural separation that protects children.

The one-line summaries below are in English, for anyone integrating this
library. The longer reasoning is in Portuguese, where it was written.

==========================================================================

O QUE E'

  Um VETO que roda ANTES do detector. Se o portao veta, nenhuma medida e'
  calculada - nao existe caminho no codigo em que o detector veja uma
  imagem vetada. A protecao nao e' um julgamento do detector; e' a ordem
  das operacoes.

FALHA FECHADA

  Toda duvida veta. Sinal ausente veta. Portao indisponivel veta TUDO - a
  categoria simplesmente nao produz candidatos naquele acervo.

  E' o oposto do padrao usual (na duvida, medir e deixar o limiar
  resolver). Aqui a duvida e' resolvida contra a medida, porque os dois
  erros nao custam a mesma coisa: nao marcar uma foto adulta e' um
  incomodo; medir a foto do banho da filha e' o dano que o projeto inteiro
  existe para evitar.

O PROBLEMA HONESTO DESTE PORTAO

  Ele se apoia em reconhecimento facial, e reconhecimento facial de bebe
  e' o sinal mais fraco do acervo - medido no projeto principal: uma foto
  de bebe casou com uma adulta sem parentesco a 0.46 de similaridade.

  Consequencias que o desenho assume em vez de esconder:

    1. O limiar de VETO e' mais BAIXO que o de identificacao (0.30 contra
       0.55). Aqui um falso positivo do reconhecimento nao custa quase
       nada - so' deixa de avaliar uma foto. Recall e' tudo; precisao nao
       importa.

    2. Crianca de costas, de longe, ou sem rosto visivel NAO e' pega por
       semelhanca. Por isso existe o modo STRICT, e por isso o experimento
       mede o RISCO RESIDUAL: quantas fotos de crianca o portao deixa
       passar.

    3. O portao nunca e' declarado "seguro" por argumento. Ele e' medido
       contra um conjunto de fotos de crianca rotulado a mao, e o numero
       que vale e' o RECALL DO PORTAO, nao a precisao do detector.

MODOS

  strict   : so' avalia imagem em que TODO rosto detectado casa com uma
             referencia adulta. Rosto desconhecido veta.
             Custo: num acervo com muita gente desconhecida, a categoria
             quase nao produz candidato. Beneficio: crianca desconhecida
             (visita, escola, praia) tambem fica protegida.

  standard : veta por semelhanca com pessoa protegida e por ausencia de
             sinal. Rosto adulto desconhecido passa.

  Qual usar nao se decide aqui: medem-se os dois no mesmo conjunto e
  olha-se a tabela. Ver EXPERIMENTO.md, experimento 0.
==========================================================================
"""

from __future__ import annotations

from dataclasses import dataclass


# Limiar de VETO. Deliberadamente abaixo de 'faces.protection_threshold'
# (0.40) do consumidor: aquele limiar decide "esta foto e' de alguem da
# familia", uma afirmacao. Este decide "pode ser", uma duvida - e duvida
# veta.
# NAO E' UM NUMERO MEDIDO. E' ponto de partida conservador; o experimento 0
# existe para substitui-lo por um numero medido.
DEFAULT_VETO_THRESHOLD = 0.30


@dataclass
class Gate:
    """Decides whether an image MAY be measured. Never measures anything."""

    veto_threshold: float = DEFAULT_VETO_THRESHOLD
    mode: str = "standard"             # 'standard' | 'strict'
    available: bool = False            # falha fechada ate' prova em contrario
    unavailable_reason: str = "gate_not_configured"

    # -- construction from the consumer's config --------------------
    @classmethod
    def from_config(cls, cfg, protected_refs_loaded: bool | None = None):
        """Read config and decide whether the gate may operate at all.

        Tres condicoes, todas necessarias:
          - faces.enabled        : ha' deteccao de rosto no indice
          - faces.identify       : ha' reconhecimento (senao
                                   protected_similarity e' sempre None e o
                                   veto nao funciona)
          - faces.never_evaluate : ha' pelo menos uma pessoa protegida
                                   declarada, com pasta de referencia

        Faltando qualquer uma, o portao fica indisponivel e a categoria
        inteira e' desligada. Nao existe modo degradado."""
        g = cls(veto_threshold=float(
                    cfg.get("policies.sensitive.veto_threshold",
                            DEFAULT_VETO_THRESHOLD)),
                mode=str(cfg.get("policies.sensitive.gate", "standard")))
        protected = list(cfg.get("faces.never_evaluate", []) or [])
        if not cfg.get("faces.enabled", True):
            g.unavailable_reason = "gate_no_face_detection"
        elif not cfg.get("faces.identify", False):
            g.unavailable_reason = "gate_no_recognition"
        elif not protected:
            g.unavailable_reason = "gate_no_protected_people"
        elif protected_refs_loaded is False:
            g.unavailable_reason = "gate_no_reference_vectors"
        else:
            g.available = True
            g.unavailable_reason = ""
        return g

    # -- decision ---------------------------------------------------
    def allows(self, rec: dict) -> tuple[bool, str]:
        """(may_evaluate, reason). 'rec' is one row of the index.

        So' le sinais JA' calculados - nao abre a imagem. Barato de
        proposito: o portao roda sobre o acervo inteiro, o detector so'
        sobre o que sobrar."""
        if not self.available:
            return False, self.unavailable_reason

        if rec.get("error"):
            return False, "read_error"

        # Sinal ausente = imagem nao indexada por completo. Falha fechada:
        # sem sinal de rosto nao ha' como saber quem esta' na foto.
        if rec.get("faces") is None:
            return False, "no_face_signal"
        if rec.get("protected_similarity") is None:
            return False, "no_recognition_signal"

        if float(rec["protected_similarity"]) >= self.veto_threshold:
            return False, "protected_person"

        if self.mode == "strict":
            # Exige que o rosto MENOS reconhecido da imagem ainda case com
            # alguma referencia adulta. Um unico rosto desconhecido veta.
            #
            # SINAL QUE AINDA NAO EXISTE no indice: hoje o nucleo guarda
            # so' o MAXIMO das semelhancas. O modo estrito precisa do
            # MINIMO por imagem - ver EXPERIMENTO.md, secao "mudancas
            # necessarias no nucleo". Enquanto nao existir, o modo estrito
            # veta tudo, que e' o lado certo de errar.
            worst = rec.get("min_known_similarity")
            if worst is None:
                return False, "strict_mode_missing_signal"
            if float(worst) < self.veto_threshold:
                return False, "unidentified_face"

        return True, "allowed"

    # -- propagation across duplicate groups ------------------------
    @staticmethod
    def propagate_veto(groups, vetoed: set[str]) -> set[str]:
        """If one member of a duplicate group is vetoed, all of them are.

        Sem isto o portao tem um furo: a mesma foto existe no acervo em
        duas copias - uma nitida, onde o rosto e' reconhecido, e uma
        pequena e borrada, onde nao e'. A copia borrada passa pelo portao,
        e a categoria recebe a mesma crianca que a copia nitida protegeu.

        'groups' e' a saida do agrupador de duplicatas, em caminhos."""
        out = set(vetoed)
        for members in groups:
            if any(p in out for p in members):
                out.update(members)
        return out
