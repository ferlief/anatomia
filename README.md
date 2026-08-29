# anatomia

Sensitive-content detection by **body structure**, not by skin colour.

Classic nudity detectors measure skin fraction in a colour space. That fails in a predictable direction: the darker the skin, the more area gets classified as "skin", and the more false positives the system produces. The bias is not an accident of implementation — it is the metric.

This library changes the metric: it reports **detected anatomical regions**, each with a box, a label and a confidence.

## Two rules that define the API

**1. It returns measurement, never a verdict.** The library says *"a region labelled `BUTTOCKS_EXPOSED`, confidence 0.71, covering 4% of the image"*. It does not say *"this image is sensitive"*. That is policy — it lives in the consumer's YAML, and can be read, argued with and changed without touching code.

**2. The gate runs before the detector.** If the gate vetoes an image, no measurement is computed — there is no code path in which the detector sees a vetoed image. The protection is the order of operations, not a judgement made by the model. Every doubt vetoes; a missing signal vetoes; an unavailable gate vetoes everything.

```python
from anatomia import Evaluator, Gate

ev = Evaluator(gate=Gate.from_config(cfg))
measurement, candidate = ev.evaluate_and_judge(record)
```

`Measurement.evaluated` distinguishes *"the detector looked and found nothing"* from *"the detector never looked"*. Collapsing those two would make a gate-protected photo indistinguishable from a clean one, and the log would stop proving that the protection happened.

## Status

**Pre-measurement.** Nothing here has been validated yet. See `EXPERIMENTO.md`, which defines the numbers that decide whether training is necessary at all — with the acceptance criteria written *before* the experiment runs, deliberately.

The project's thesis, that anatomy is fairer than colour, is a **measurable claim, not a theorem**. Geometry being invariant to pigment does not make the *model* invariant: NudeNet is a YOLO trained on web-collected images, and such detectors have documented uneven performance across skin tones. Experiment 2 measures exactly that, on content-matched pairs.

## Language

Code, API and one-line docstrings are in English. The longer design reasoning — the module headers and `EXPERIMENTO.md` — is in Brazilian Portuguese, where it was written and where it reads best.

What you need in order to *integrate* is in English; what explains *why* is in Portuguese.

## License

AGPLv3. Any trained weights, if they ever exist, only from material without identifiable people.
