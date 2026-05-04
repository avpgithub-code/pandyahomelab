# ADR-004: Level 4 demos named with dataset-algorithm convention

**Status:** Accepted
**Date:** April 2026
**Stage:** 1 (Conceptual Design)

## Context

ADR-003 establishes a four-level URL hierarchy. Level 3 holds technique families (classification, regression, clustering). Level 4 holds individual interactive demos. The question this ADR resolves: **what is a demo named?**

Two intuitions competed:
- **Algorithm-based:** name demos after the algorithm they showcase (`iris-knn` → just `knn`)
- **Dataset-based:** name demos after the dataset (`iris-knn` → just `iris`)
- **Combined:** name demos with both (`iris-knn`, `housing-linear`)

The decision affects every URL on the platform, every container name in `docker-compose.yml`, and every directory in the project repository.

## Decision

**Level 4 demos are named `dataset-algorithm`. The dataset comes first.**

Examples:
- `/ml/classification/iris-knn` — Iris dataset, K-Nearest Neighbors
- `/ml/classification/titanic-randomforest` — Titanic dataset, Random Forest
- `/ml/regression/housing-linear` — California housing, Linear Regression
- `/ml/regression/housing-xgboost` — same dataset, different algorithm
- `/ml/clustering/customers-kmeans` — Customer segments, K-Means
- `/dl/image-classification/mnist-cnn` — MNIST, Convolutional Neural Network
- `/nlp/ner/news-spacy` — News articles, spaCy NER
- `/agentic/rag/pandyalab-docs` — pandyaHomeLab documentation, RAG

The same algorithm applied to different datasets becomes two demos with distinct names. The same dataset run through different algorithms also becomes two demos — useful for direct algorithm comparison.

## Alternatives considered

**Algorithm only (rejected).** Names like `/ml/classification/knn` are technically descriptive but emotionally flat. A visitor remembering the site three days later is more likely to remember "the one with the flowers" or "the housing prices one" than "the KNN demo." Lead with what is memorable.

**Dataset only (rejected).** Names like `/ml/classification/iris` cannot accommodate the case of running multiple algorithms on the same dataset, which is a natural pedagogical pattern (compare KNN vs SVM vs Random Forest on Iris).

**Algorithm-dataset, reversed (rejected).** `/ml/classification/knn-iris` works but reads awkwardly. The dataset is the noun (what the demo is *about*); the algorithm is the verb (how the demo *works*). Noun-then-verb is more natural.

**Free-form descriptive names (rejected).** Names like `/ml/classification/flower-predictor` are friendlier but lose technical precision. A portfolio platform should signal that the operator thinks in terms of dataset + algorithm — that is the working data scientist's vocabulary.

## Consequences

**Positive:**

- Every new demo has an unambiguous name before it is built. No naming debates.
- The same dataset across multiple algorithms becomes a comparison cluster (`housing-linear`, `housing-xgboost`, `housing-randomforest`). Educationally valuable.
- Container names follow URLs: `ml-iris-knn` (with `ml-` prefix for the domain). Greppable across logs, `docker ps`, Nginx config, and source repository.
- Repository folder structure can mirror URL structure exactly: `/services/ml/classification/iris-knn/`. One naming decision propagates everywhere.

**Negative:**

- Some datasets are obscure or have boring names (`uci-adult`, `kdd99`). The dataset-first principle does not always produce the most evocative URL.
- When showcasing a sophisticated algorithm, the dataset name dominates the URL even though the algorithm is the point. This is acceptable for L4 but means L3 or written content must do the work of highlighting algorithmic interest.
- Datasets with multi-word names (`fashion-mnist`, `boston-housing`) make demo names longer (`fashion-mnist-vit`). Mitigation: either shorten the dataset name (`fmnist`) or accept the length.

**Forecloses:**

- Demos that have no specific dataset (e.g., a pure visualization of how attention works) need a different naming pattern. Such cases are exceptions, not the rule, and will be ADR'd individually if they arise.
