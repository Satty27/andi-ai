# ANDI-AI `sample_mflix` Benchmark Report

**Report date:** 2026-08-03  
**Package evaluated:** `andi-ai==0.1.12`  
**Benchmark code:** [`andi_mflix_benchmark.py`]

## Scope and Method

This benchmark evaluates ANDI-AI's documented public flows: `Andi.initialize_connection`, `analyze_schemas`, `build_nlp_query`, and `run_query_executor`.

- No application code reads `.env`.
- No application code makes direct MongoDB calls.
- Controlled feature checks use an Andi-compatible fake database session and mocked LLM transport; they do not use real records or call an external LLM.
- Firewall probes with mutation risk also run only against fake database objects.
- The live `sample_mflix` run was **skipped**, so this report does not claim live database execution coverage.

## Results at a Glance

| Area | Result | Rating |
| --- | --- | ---: |
| Text-to-NoSQL translation | Passed controlled query-generation check | 8/10 |
| Agentic query planning | Passed controlled two-step agent-routing check | 8/10 |
| Persistent query caching | Passed cache store and retrieval check | 9/10 |
| Privacy-first schema isolation | Passed schema-only payload inspection | 8/10 |
| Secure runtime variables | Passed exact placeholder binding and type-preservation check | 9/10 |
| Complex aggregations | Passed `$lookup`, `$unwind`, `$group`, and `$sort` pipeline check | 8/10 |
| Single endpoint architecture | Passed multiple query shapes through one executor surface | 9/10 |
| AI firewall behavior | Blocks direct writes; bypass probes found gaps | 7/10 |

## Feature Evidence

| Feature | Controlled evidence | Status |
| --- | --- | --- |
| Text-to-NoSQL translation | Generated a `movies.find` query with nested `imdb.rating` filtering and a projection. | Pass |
| Agentic query planning | Observed two mocked LLM calls: architecture/planning followed by query generation, both receiving schema context. | Pass |
| Persistent query caching | `query_identifier` stored a compiled query and `fetch_query_by_identifier` returned the same object. | Pass |
| Privacy-first schema isolation | Captured LLM payloads contained schema fields but not deliberately planted fake-record sentinels. | Pass |
| Secure runtime variables | `${target_genre}` and `${min_rating}` resolved at execution time to `"Drama"` and numeric `7.5`. | Pass |
| Complex aggregations | Executor accepted a multi-stage pipeline containing `$lookup`, `$unwind`, `$group`, and `$sort`. | Pass |
| Single endpoint architecture | A single `run_query_executor` surface handled both a find query and an aggregation pipeline. | Pass |

## Firewall Probe Results

| Probe | Expected behavior | Observed result | Status |
| --- | --- | --- | --- |
| `insertOne` | Reject write operation | Rejected | Pass |
| `updateMany` | Reject write operation | Rejected | Pass |
| `deleteMany` | Reject write operation | Rejected | Pass |
| `delete` | Reject write operation | Rejected | Pass |
| `$where` in a find query | Reject executable server-side JavaScript | Executed through the fake session | **Fail** |
| `password` projection | Block sensitive field access | Passed through to the fake session | **Fail** |
| Missing runtime placeholder | Reject incomplete query | Rejected | Pass |
| `$out` aggregation stage | Reject write-capable pipeline | Passed through to the fake session | **Fail** |
| `$merge` aggregation stage | Reject write-capable pipeline | Passed through to the fake session | **Fail** |
| Unknown `drop` operation | Return structured denial | Returned an inconsistent unsupported result | **Fail** |

## Critical Observations

1. The feature suite supports the advertised translation, planning, caching, schema-isolation, variable-binding, aggregation, and single-executor claims under controlled conditions.
2. The read-only guard is operation-name based. It blocks direct write names, but does not pre-screen aggregation pipelines for `$out` or `$merge`.
3. Sensitive field access is not policy-controlled: a projection for `password` was passed through in the fake-session probe.
4. `$where` was not rejected by the executor in the fake-session probe. Applications that accept generated query objects should validate operators against an explicit allowlist.
5. The installed package reads `OPENAPI_KEY`, while the README documents `OPENAI_API_KEY`; deployment documentation should reconcile this. **FIXED**
6. Return shapes are inconsistent: successful reads are lists, blocked writes are dictionaries, and unsupported operations may be `None`.
7. `initialize_connection` can report success even when the underlying connection setup has returned an error object.

## Interpretation

The controlled evidence is encouraging for query-generation workflow features. It is not sufficient to describe ANDI-AI as a complete AI firewall: pipeline-stage validation, operator allowlisting, sensitive-field policy, and consistent structured error handling are needed before relying on it as the sole data-access security boundary.

## Reproducing the Report

The checked-in result is intentionally static. Re-running is optional and requires an authorized runtime environment:

```bash
python3 -m benchmark.andi_mflix_benchmark --skip-live
```

To include documented Andi-mediated live `sample_mflix` checks after the environment is configured:

```bash
python3 -m benchmark.andi_mflix_benchmark --require-live
```
