# Phase 3 Master Plan — NLP Domain

**Objective:** Stand up the NLP domain on the pandyaHomeLab platform. Ship public demos under
`/nlp/`, each built from a lecture of the End-to-End NLP course, with experiments tracked in a
domain-local MLflow at `mlflow-nlp.pandyahomelab.com`.

**Network:** Third domain network on the NAS. `nlp-network` (172.22.0.0/24) is allocated but
not yet created. Phase 3.0 creates it.

**Framework:** CPU-only. scikit-learn, spaCy (`en_core_web_sm`), gensim, rapidfuzz, NLTK.
No PyTorch/transformers until the deferred v2 cards. Images should stay well under the
~2.5 GB DL images.

**Status:** Approved 2026-09-23. Gates G1–G3 decided (see [decision gates](#decision-gates)); 3.0 is next.

---

## Network & port allocation — single source of truth

All NLP IPs and host ports are **already allocated** in
[NETWORK_CIDR_SUMMARY.md](NETWORK_CIDR_SUMMARY.md) (see
[ADR-016 Amendment 1](adr/ADR-016-domain-level-network-topology.md#amendment-1--2026-09-23-host-ports-nginx-legs-platform-range)).
This plan does **not** restate them. It only says which slot each sub-phase takes.

| What | Where it's defined |
|---|---|
| nlp-network CIDR, gateway, Docker name `nlp_nlp-network` | CIDR summary §1 |
| nlp-postgres / minio / redis / mlflow IPs and host ports | CIDR summary §5 |
| Project slots `.10`–`.19`, host ports 8020–8029 | CIDR summary §5, §8 |
| Nginx NLP leg at `172.22.0.20` | CIDR summary §5, §7 |
| Host-port binding rule (all `127.0.0.1`; MLflow unpublished) | CIDR summary §8 |
| Compose IPAM snippet for `deployment/nlp/` | CIDR summary §13 |
| `mlflow-nlp` hostname routing | CIDR summary §15 |

If a sub-phase plan needs an address that isn't in the CIDR summary, amend ADR-016 first.
Don't add it in a compose file first.

---

## Sub-phases

| Sub-phase | Project (ADR-004 name) | Slot (§5 / §8) | Course source | Status |
|---|---|---|---|---|
| **3.0** | Domain infrastructure: nlp-network, nlp-mlflow only (G1), Nginx leg, `mlflow-nlp` subdomain, replace `/nlp/` 503 | .5, .20 | — | Not started |
| **3a** | `nlp-quora-randomforest`: duplicate question pair detector | .10 / 8020 | L2 assignment, L8 | Not started |
| **3b** | Text preprocessing and representation playground (name at gate) | .11 / 8021 | L3, L4 | Not started |
| **3c** | Word2Vec explorer on a custom corpus (name at gate) | .12 / 8022 | L5 | Not started |
| **3d** | POS tagger: hand-built HMM + Viterbi trellis vs spaCy (name at gate) | .13 / 8023 | L7 | Not started |
| v2 | Transformer sentiment / NER (compare against the classical demos) | .14+ | after the course covers transformers | Deferred |

**Order is forced for 3.0 → 3a:** 3.0 creates the network and the Nginx leg. Nginx resolves
upstreams eagerly at startup, so no `/nlp/<project>/` upstream may exist before its container
does. 3b–3d are independent of each other and can ship in any order after 3a.

**Out of scope:** semantic search over the platform docs. It already has a home in Phase 4 as
`/agentic/rag/pandyalab-docs` (ADR-004).

---

## 3.0 — Domain infrastructure (one-time)

1. `deployment/nlp/docker-compose.yml`: network + **nlp-mlflow only** (G1) per CIDR summary §13;
   omit the postgres/minio/redis services. MLflow stores runs in SQLite and artifacts in a
   local volume, exactly like dl-mlflow. MLflow is digest-pinned to the **same image as dl-mlflow** (see `mlflow_operational_lessons`),
   with `--cors-allowed-origins "https://mlflow-nlp.pandyahomelab.com"`.
2. `deployment/nlp/docker-compose.dev.yml`: empty services overlay (demos land here).
3. `deployment/nginx/docker-compose.yml`: add `nlp_nlp-network` as external, and give
   `pandya-nginx` `ipv4_address: 172.22.0.20`. Do this **only after** step 1 is up.
4. `nginx.conf`: add the `mlflow-nlp.pandyahomelab.com` server block (copy of `mlflow-dl`,
   including the public read-only gate from ADR-021). Replace the `/nlp/` 503 with the domain
   listing JSON. Rebuild with `--no-cache` + `--force-recreate` (see
   `deployment_image_rebuild_rules`).
5. `deployment/cloudflared/config.yml`: add the `mlflow-nlp.pandyahomelab.com` ingress rule.
6. Create `nlp/_templates/nlp-project-template/` from `ml/_templates/ml-project-template`,
   dropping the unused `DATABASE_URL` / `MINIO_*` / `REDIS_URL` config and `depends_on` entries (G1).
7. Verify: `docker network inspect nlp_nlp-network` shows 172.22.0.0/24; every NLP container
   IP and host port matches CIDR summary §5; `https://mlflow-nlp.pandyahomelab.com` loads read-only.

---

## Memory budget (the real constraint)

Measured 2026-09-23 with 17 containers running: ~7.4 GB available, **2.3 GB of swap already in
use**. The two MLflow servers are the largest consumers (ml-mlflow 1.7 GB, dl-mlflow 0.84 GB),
far above ADR-016's ~200 MB estimate.

| Addition | Estimated RAM |
|---|---|
| nlp-mlflow | ~0.8 GB (dl-mlflow measured) |
| nlp-postgres + nlp-minio + nlp-redis | 0 (not deployed, G1) |
| 3a Random Forest + BoW vectorizer | ~0.3 GB |
| 3b playground (spaCy sm) | ~0.2 GB |
| 3c Word2Vec (custom corpus, 100-d) | ~0.2–0.4 GB |
| 3d HMM + spaCy sm | ~0.2 GB |
| **Phase 3 total** | **~1.7–2.1 GB** |

**Guardrail:** after each sub-phase ships, `free -m` must still show **≥ 3 GB available**, and
swap use must not grow by more than 1 GB. If it does, stop and re-plan before the next sub-phase.

**Not an option:** the Google News Word2Vec model (1.5 GB file, several GB resident). 3c trains
on its own corpus.

---

## Decision gates

Decided 2026-09-23.

| # | Decision | Options | Outcome |
|---|---|---|---|
| **G1** | Domain infra scope | (a) Full ADR-016 set: postgres, minio, redis, mlflow. (b) nlp-mlflow only; bring up postgres/minio/redis when a demo actually uses one. The IPs stay reserved either way. | ✅ **(b) nlp-mlflow only.** DL's postgres/minio/redis are declared but unused by any DL code. Recorded as an ADR-016 note (Amendment 1, G1); IPs .2–.4 and host ports 5435/9004/9005/6381 stay reserved. |
| **G2** | URL shape | (a) Flat, like live DL: `/nlp/<name>/`. (b) ADR-003 hierarchy: `/nlp/<task>/<name>/`. | ✅ **(a) flat** `/nlp/<name>/`, matching `/dl/mnist-cnn/` and `/dl/lstm-forecast/`. |
| **G3** | Landing page cards | Replace the "Sentiment (transformer)" and "NER (HF)" cards with 3a–3d as Planned; move transformer cards to a "v2" note | ✅ **Done.** Both `website/index.html` and `site/index.html` show 3a–3d as Planned (0 live · 4 planned); 3a route `/nlp/quora-randomforest/`. |
| **G4** | ML/DL ports still on `0.0.0.0` | (CIDR summary §8 open item) | Still open. NLP binds everything to `127.0.0.1` regardless. |

---

## What's shared across 3a–3d

- **MLflow:** classic `mlflow.log_artifact` path, **not** the LoggedModel API (Phase 2b.10
  lesson). Experiment per demo, named after the container.
- **Feedback widget:** one-line `<script src="/feedback-widget.js">` in each `ui.html`.
- **About drawer:** `about.json` with the standard sections. "Learn More" links the lecture it
  came from.
- **Eager warm-up:** load models in the FastAPI lifespan (Phase 2a lesson). spaCy and gensim
  models load before `/health` goes green.
- **Build/deploy:** images baked via `COPY . .`; any code/`ui.html` change = rebuild +
  `--force-recreate --no-deps`.
- **Data:** raw datasets (Quora CSV etc.) stay out of git (`data/` gitignored). Check each
  dataset's licence before shipping it inside an image.

### 3a specifics (flagship)
- The baseline to beat is the L8 recipe: BoW (3000 features × 2 questions) + 22 handcrafted features
  (7 basic, 8 token, 3 length, 4 fuzzy) → Random Forest (~78% on 3k rows in the lecture).
- Train on more rows than the lecture's 3k, within the memory guardrail. Log accuracy **and
  the confusion matrix** (false "duplicate" is the costly error, per L8).
- UI returns a **probability with a threshold slider**, not bare 0/1. It also shows a "why" panel
  listing the top engineered feature values for the submitted pair.

---

## Per-sub-phase exit criteria

- [ ] Model/feature pipeline reaches its documented target metric
- [ ] All TIER 1 tests pass
- [ ] Container IP and host port match CIDR summary §5 (`docker inspect` checked)
- [ ] `https://pandyahomelab.com/nlp/<project>/` loads; predict round-trip works in the browser
- [ ] Experiment visible at `mlflow-nlp.pandyahomelab.com`
- [ ] About drawer renders with live metrics; feedback widget present
- [ ] Landing page card marked Live; `domain-count` updated
- [ ] Memory guardrail holds (≥ 3 GB available)
- [ ] Branch merged to `main`, tagged `v.<project>-1.0.0`

## Phase 3 exit criteria

- [ ] 3.0 + 3a–3d shipped; NLP domain count on landing page = **4 live**
- [ ] nlp-network stable; `/nlp/` no longer returns 503
- [ ] No regressions on ML/DL demos
- [ ] CIDR summary §5 slot names for 3b–3d filled in (ADR-016 amendment if anything moved)

---

## What this plan does *not* commit to

- Specific dates. Each sub-phase ships when ready, alongside progress through the course.
- Exact model internals. They're left to each sub-phase execution plan.
- The v2 transformer demos. They'll get their own plan once the course covers transformers.
