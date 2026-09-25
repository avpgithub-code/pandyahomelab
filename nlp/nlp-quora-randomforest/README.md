# nlp-quora-randomforest

Phase 3a (flagship): are two Quora questions asking the same thing?

Built from lectures L2 (assignment) and L8 of the End-to-End NLP course. The
baseline to beat is the L8 recipe: bag-of-words (3000 features × 2 questions) +
22 handcrafted features (7 basic, 8 token, 3 length, 4 fuzzy) → Random Forest,
about 78% accuracy on 3k rows. See `docs/PHASE_3_MASTER_PLAN.md` → "3a specifics".

| | |
|---|---|
| Container | `nlp-quora-randomforest` · 172.22.0.10:8000 · `127.0.0.1:8020` |
| Route | `/nlp/quora-randomforest/` |
| MLflow | experiment `nlp-quora-randomforest` on `mlflow-nlp.pandyahomelab.com` |

## Status

Scaffolded from `nlp/_templates/nlp-project-template`. It still runs the template's
placeholder classifier and sample corpus. Still to build:

- [ ] Quora Question Pairs loader (dataset stays out of git; licence check before baking)
- [ ] 22 engineered features + BoW → Random Forest; train on more than 3k rows within the memory guardrail
- [ ] Probability + threshold slider; "why" panel with the top feature values for the pair
- [ ] About sections `features` and `threshold`; confusion matrix Not duplicate / Duplicate
- [ ] Deploy (compose overlay, then Nginx route), exit criteria in the plan

## Develop

```sh
make test-unit
make docker-build
```
