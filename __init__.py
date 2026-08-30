r"""
anatomia - sensitive-content detection by BODY STRUCTURE, not skin tone.

It does not classify pigment: it locates anatomy. It does not decide: it
measures. A gate runs before the detector and vetoes on any doubt, so
that photographs of children are not measured.

That protection is structural, not absolute. The gate leans on face
recognition, which does not catch a child seen from behind, at distance,
or with no visible face. Its recall is a number to be *measured*, not
assumed - see EXPERIMENTO.md, experiment 0. Until that number exists,
treat the guarantee as "the detector never sees what the gate vetoed",
which is enforced in code, and not as "no child is ever measured", which
is not something this library can promise.

    from anatomia import Evaluator, Gate, Detector

    ev = Evaluator(gate=Gate.from_config(cfg))
    measurement, candidate = ev.evaluate_and_judge(record)

'Detector' is exported for testing and for the experiment; in production
always use 'Evaluator', which puts the gate in front. See evaluator.py.

Documentation note: one-line summaries are in English. The longer design
reasoning, and EXPERIMENTO.md, are in Brazilian Portuguese - that is where
the thinking happened, and translating it would cost more than it buys.
"""

from .detector import Detector
from .evaluator import DEFAULT_POLICY, Evaluator
from .gate import (DEFAULT_IDENTIFICATION_THRESHOLD, DEFAULT_VETO_THRESHOLD,
                   Gate)
from .types import Candidate, Measurement, NOT_EVALUATED, Region

__all__ = ["Evaluator", "Gate", "Detector",
           "Measurement", "Region", "Candidate", "NOT_EVALUATED",
           "DEFAULT_POLICY", "DEFAULT_VETO_THRESHOLD",
           "DEFAULT_IDENTIFICATION_THRESHOLD"]
__version__ = "0.3.0-design"
