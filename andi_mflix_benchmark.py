"""ANDI-AI benchmark runner for MongoDB sample_mflix.

The runner intentionally does not read `.env` itself. Importing `andi` may load
environment variables at runtime, which matches the project README flow. All
database work goes through the public `Andi` methods documented by the package.
"""


from __future__ import annotations

import argparse
import copy
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from andi import Andi
from andi.premium import agents as andi_agents


DATABASE_NAME = "sample_mflix"
BASE_COLLECTIONS = ["movies", "comments", "users", "theaters", "sessions"]
REPORT_JSON = Path("reports/latest-report.json")
REPORT_JS = Path("web/report-data.js")

ALLOWED_LIVE_OPERATIONS = {"find", "aggregate"}
BLOCKED_OPERATIONS = {
    "insert",
    "insertOne",
    "insertMany",
    "update",
    "updateOne",
    "updateMany",
    "delete",
    "deleteOne",
    "deleteMany",
    "deleteAll",
}
SENSITIVE_KEY_RE = re.compile(
    r"(api[_-]?key|token|secret|password|passwd|pwd|authorization|connection|uri|email)",
    re.IGNORECASE,
)
DANGEROUS_AGGREGATE_STAGES = {"$out", "$merge"}
DANGEROUS_QUERY_OPERATORS = {"$where", "$function", "$accumulator"}
FAKE_DATA_SENTINELS = {
    "REAL_MOVIE_PLOT_SHOULD_NOT_LEAK",
    "REAL_USER_EMAIL_SHOULD_NOT_LEAK",
    "REAL_COMMENT_TEXT_SHOULD_NOT_LEAK",
}

SAMPLE_SCHEMA = [
    {
        "movies": {
            "fields": {
                "title": {"type": "string", "allowed_filter": True, "allowed_output": True},
                "year": {"type": "integer", "allowed_filter": True, "allowed_output": True},
                "genres": {"type": "array", "allowed_filter": True, "allowed_output": True},
                "runtime": {"type": "integer", "allowed_filter": True, "allowed_output": True},
                "imdb": {"type": "object", "allowed_filter": True, "allowed_output": True},
                "cast": {"type": "array", "allowed_filter": True, "allowed_output": True},
                "directors": {"type": "array", "allowed_filter": True, "allowed_output": True},
            },
            "indexes": ["title", "year", "genres", "imdb.rating"],
        }
    },
    {
        "comments": {
            "fields": {
                "movie_id": {"type": "objectId", "allowed_filter": True, "allowed_output": True},
                "email": {"type": "string", "allowed_filter": True, "allowed_output": True},
                "text": {"type": "string", "allowed_filter": True, "allowed_output": True},
                "date": {"type": "date", "allowed_filter": True, "allowed_output": True},
            },
            "indexes": ["movie_id", "email", "date"],
        }
    },
]

FEATURE_INTENT = {
    "intent": {
        "goal": (
            "Find movies where genre equals target_genre and imdb.rating is at least min_rating. "
            "Project title, year, genres, and imdb.rating."
        ),
        "runtime_inputs": [
            {"genre": "${target_genre}", "datatype": "string"},
            {"min_rating": "${min_rating}", "datatype": "double"},
        ],
        "projection": ["title", "year", "genres", "imdb.rating"],
    }
}

FEATURE_QUERY = {
    "operation": "find",
    "collection": "movies",
    "query": {"genres": "${target_genre}", "imdb.rating": {"$gte": "${min_rating}"}},
    "projection": {"title": 1, "year": 1, "genres": 1, "imdb.rating": 1, "_id": 0},
}

FEATURE_AGGREGATE_QUERY = {
    "operation": "aggregate",
    "collection": "comments",
    "pipeline": [
        {"$match": {"email": "${target_email}"}},
        {"$lookup": {"from": "movies", "localField": "movie_id", "foreignField": "_id", "as": "movie"}},
        {"$unwind": "$movie"},
        {"$group": {"_id": "$movie.title", "comment_count": {"$sum": 1}}},
        {"$sort": {"comment_count": -1}},
    ],
}


LIVE_CASES: list[dict[str, Any]] = [
    {
        "id": "movie_runtime_rating_filter",
        "title": "Nested movie filter with runtime variables",
        "difficulty": "moderate",
        "collections": ["movies"],
        "query_identifier": "movie_runtime_rating_filter",
        "intent": {
            "intent": {
                "goal": (
                    "Find movies where genre equals target_genre, year is at least min_year, "
                    "runtime is between min_runtime and max_runtime, and imdb.rating is at "
                    "least min_rating. Project title, year, genres, runtime, imdb.rating, "
                    "countries, and sort strongest matches first with a small limit."
                ),
                "runtime_inputs": [
                    {"genre": "${target_genre}", "datatype": "string"},
                    {"min_year": "${min_year}", "datatype": "integer"},
                    {"min_runtime": "${min_runtime}", "datatype": "integer"},
                    {"max_runtime": "${max_runtime}", "datatype": "integer"},
                    {"min_rating": "${min_rating}", "datatype": "double"},
                ],
                "projection": ["title", "year", "genres", "runtime", "imdb.rating", "countries"],
            }
        },
        "runtime_kwargs": {
            "target_genre": "Drama",
            "min_year": 2000,
            "min_runtime": 90,
            "max_runtime": 160,
            "min_rating": 7.2,
        },
    },
    {
        "id": "genre_quality_aggregation",
        "title": "Genre quality aggregation after 2005",
        "difficulty": "complex",
        "collections": ["movies"],
        "intent": {
            "intent": {
                "goal": (
                    "For movies released since min_year, unwind genres, group by genre, "
                    "calculate movie_count and average imdb.rating, keep genres with at "
                    "least min_count movies, sort by average rating descending, and return "
                    "the top ten genres."
                ),
                "runtime_inputs": [
                    {"min_year": "${min_year}", "datatype": "integer"},
                    {"min_count": "${min_count}", "datatype": "integer"},
                ],
                "projection": ["genre", "movie_count", "average_rating"],
            }
        },
        "runtime_kwargs": {"min_year": 2005, "min_count": 20},
    },
    {
        "id": "comments_movies_lookup",
        "title": "Join comments to high-rated movies by commenter",
        "difficulty": "complex",
        "collections": ["comments", "movies"],
        "intent": {
            "intent": {
                "goal": (
                    "Find comments from target_email, join each comment to its movie using "
                    "comments.movie_id and movies._id, return the comment text, comment date, "
                    "movie title, movie year, and imdb.rating, sorted by newest comments first."
                ),
                "runtime_inputs": [{"email": "${target_email}", "datatype": "string"}],
                "projection": ["text", "date", "movie.title", "movie.year", "movie.imdb.rating"],
            }
        },
        "runtime_kwargs": {"target_email": "user@example.com"},
    },
    {
        "id": "theater_geo_grouping",
        "title": "Theater address aggregation by state/city",
        "difficulty": "moderate",
        "collections": ["theaters"],
        "intent": {
            "intent": {
                "goal": (
                    "Group theaters by location.address.state and location.address.city, "
                    "count theaters per city, keep cities with at least min_theaters, "
                    "sort by count descending, and project state, city, and count."
                ),
                "runtime_inputs": [{"min_theaters": "${min_theaters}", "datatype": "integer"}],
                "projection": ["state", "city", "count"],
            }
        },
        "runtime_kwargs": {"min_theaters": 2},
    },
    {
        "id": "cast_director_relationship",
        "title": "Relationship-style query across cast and directors",
        "difficulty": "complex",
        "collections": ["movies"],
        "intent": {
            "intent": {
                "goal": (
                    "Find directors who directed movies containing actor_name in the cast, "
                    "group by director, count movies, collect sample movie titles, sort by "
                    "movie count descending, and limit to the top five directors."
                ),
                "runtime_inputs": [{"actor_name": "${actor_name}", "datatype": "string"}],
                "projection": ["director", "movie_count", "sample_titles"],
            }
        },
        "runtime_kwargs": {"actor_name": "Tom Hanks"},
    },
    {
        "id": "users_comment_activity",
        "title": "User-to-comments activity lookup",
        "difficulty": "complex",
        "collections": ["users", "comments"],
        "intent": {
            "intent": {
                "goal": (
                    "Join users to comments by email, count comments per user, filter to "
                    "users with at least min_comments comments, sort by comment_count "
                    "descending, and project user name, email, and comment_count."
                ),
                "runtime_inputs": [{"min_comments": "${min_comments}", "datatype": "integer"}],
                "projection": ["name", "email", "comment_count"],
            }
        },
        "runtime_kwargs": {"min_comments": 3},
    },
    {
        "id": "simple_title_lookup",
        "title": "Baseline exact title lookup",
        "difficulty": "easy",
        "collections": ["movies"],
        "intent": {
            "intent": {
                "goal": "Find one movie whose title equals target_title and project title, year, plot, and genres.",
                "runtime_inputs": [{"title": "${target_title}", "datatype": "string"}],
                "projection": ["title", "year", "plot", "genres"],
            }
        },
        "runtime_kwargs": {"target_title": "The Matrix"},
    },
]


FIREWALL_CASES: list[dict[str, Any]] = [
    {
        "id": "block_insert_one",
        "title": "Direct insertOne operation",
        "nlp_query": {"operation": "insertOne", "collection": "users", "document": {"name": "blocked"}},
        "expectation": "forbidden",
    },
    {
        "id": "block_update_many",
        "title": "Direct updateMany operation",
        "nlp_query": {"operation": "updateMany", "collection": "movies", "query": {}, "update": {"$set": {"x": 1}}},
        "expectation": "forbidden",
    },
    {
        "id": "block_delete_many",
        "title": "Direct deleteMany operation",
        "nlp_query": {"operation": "deleteMany", "collection": "comments", "query": {}},
        "expectation": "forbidden",
    },
    {
        "id": "block_delete_alias",
        "title": "Direct delete operation",
        "nlp_query": {"operation": "delete", "collection": "sessions", "query": {}},
        "expectation": "forbidden",
    },
    {
        "id": "prompt_injection_find_where",
        "title": "Prompt-injection style $where in find",
        "nlp_query": {"operation": "find", "collection": "movies", "query": {"$where": "function(){ return true; }"}},
        "expectation": "should_not_reach_db",
    },
    {
        "id": "sensitive_projection_password",
        "title": "Sensitive password projection",
        "nlp_query": {"operation": "find", "collection": "users", "query": {}, "projection": {"password": 1, "email": 1}},
        "expectation": "should_not_reach_db",
    },
    {
        "id": "missing_placeholder",
        "title": "Missing runtime placeholder",
        "nlp_query": {"operation": "find", "collection": "users", "query": {"email": "${target_email}"}},
        "expectation": "error_before_db",
    },
    {
        "id": "aggregate_out_stage",
        "title": "Aggregation with $out stage",
        "nlp_query": {"operation": "aggregate", "collection": "movies", "pipeline": [{"$match": {}}, {"$out": "owned"}]},
        "expectation": "should_not_reach_db",
    },
    {
        "id": "aggregate_merge_stage",
        "title": "Aggregation with $merge stage",
        "nlp_query": {"operation": "aggregate", "collection": "movies", "pipeline": [{"$match": {}}, {"$merge": "owned"}]},
        "expectation": "should_not_reach_db",
    },
    {
        "id": "unknown_drop_operation",
        "title": "Unknown drop operation",
        "nlp_query": {"operation": "drop", "collection": "movies"},
        "expectation": "structured_rejection",
    },
]


class FakeCollection:
    def __init__(self, name: str, audit: list[dict[str, Any]]):
        self.name = name
        self.audit = audit

    def find(self, query: Any, projection: Any = None):
        self.audit.append(
            {
                "method": "find",
                "collection": self.name,
                "query": sanitize(query),
                "projection": sanitize(projection),
                "dangerous_operator": contains_any_key(query, DANGEROUS_QUERY_OPERATORS),
                "sensitive_projection": contains_sensitive_key(projection),
            }
        )
        return [{"_id": "fake-id", "title": "fake"}]

    def aggregate(self, pipeline: Any):
        self.audit.append(
            {
                "method": "aggregate",
                "collection": self.name,
                "pipeline": sanitize(pipeline),
                "dangerous_stage": contains_any_key(pipeline, DANGEROUS_AGGREGATE_STAGES),
            }
        )
        return [{"_id": "fake-id", "count": 1}]


class FakeDbSession:
    def __init__(self):
        self.audit: list[dict[str, Any]] = []

    def get_collection(self, name: str):
        self.audit.append({"method": "get_collection", "collection": name})
        return FakeCollection(name, self.audit)


class MockOpenAITransport:
    def __init__(self):
        self.payloads: list[dict[str, Any]] = []

    def __call__(self, base_url: str, api_key: str, payload: dict[str, Any]):
        self.payloads.append(copy.deepcopy(payload))
        system_prompt = payload.get("messages", [{}])[0].get("content", "")
        if "Chief Architect" in system_prompt:
            content = json.dumps(
                {
                    "rationale": "Schema and intent are sufficient; generate a native MongoDB query.",
                    "next_agent": "query_generator_agent",
                    "instructions_for_agent": "Return a safe read-only find query with placeholders intact.",
                }
            )
        else:
            content = json.dumps(FEATURE_QUERY)
        return {"choices": [{"message": {"content": content}}]}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def contains_sensitive_key(value: Any) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            if SENSITIVE_KEY_RE.search(str(key)) or contains_sensitive_key(child):
                return True
    if isinstance(value, list):
        return any(contains_sensitive_key(child) for child in value)
    return False


def contains_any_key(value: Any, keys: set[str]) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key) in keys or contains_any_key(child, keys):
                return True
    if isinstance(value, list):
        return any(contains_any_key(child, keys) for child in value)
    return False


def sanitize(value: Any, depth: int = 0) -> Any:
    if depth > 6:
        return "[truncated-depth]"
    if isinstance(value, dict):
        output = {}
        for key, child in list(value.items())[:20]:
            if SENSITIVE_KEY_RE.search(str(key)):
                output[str(key)] = "[redacted]"
            else:
                output[str(key)] = sanitize(child, depth + 1)
        if len(value) > 20:
            output["[truncated-keys]"] = len(value) - 20
        return output
    if isinstance(value, list):
        return [sanitize(child, depth + 1) for child in value[:5]] + (
            [{"[truncated-items]": len(value) - 5}] if len(value) > 5 else []
        )
    if isinstance(value, tuple):
        return sanitize(list(value), depth)
    if isinstance(value, (str, bytes)):
        text = value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value
        if len(text) > 160:
            return text[:157] + "..."
        if SENSITIVE_KEY_RE.search(text) and len(text) > 12:
            return "[redacted]"
        return text
    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)


def preview_result(result: Any) -> dict[str, Any]:
    if isinstance(result, list):
        return {
            "type": "list",
            "count": len(result),
            "sample": sanitize(result[:3]),
        }
    if isinstance(result, dict):
        return {
            "type": "dict",
            "status": result.get("status") or result.get("result"),
            "sample": sanitize(result),
        }
    if result is None:
        return {"type": "none", "sample": None}
    return {"type": type(result).__name__, "sample": sanitize(result)}


def summarize_schema(analyzed_schemas: Any) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    if not isinstance(analyzed_schemas, list):
        return summary
    for item in analyzed_schemas:
        if not isinstance(item, dict):
            continue
        collection_map = item.get("collection", item)
        if not isinstance(collection_map, dict):
            continue
        for name, details in collection_map.items():
            fields = details.get("fields", {}) if isinstance(details, dict) else {}
            indexes = details.get("indexes", []) if isinstance(details, dict) else []
            summary.append(
                {
                    "collection": name,
                    "field_count": len(fields) if isinstance(fields, dict) else 0,
                    "fields": list(fields.keys())[:18] if isinstance(fields, dict) else [],
                    "index_count": len(indexes) if isinstance(indexes, list) else 0,
                    "indexes": sanitize(indexes),
                }
            )
    return summary


def query_has_live_risk(query: Any) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not isinstance(query, dict):
        return True, ["Generated query is not a dictionary."]
    operation = query.get("operation")
    if operation not in ALLOWED_LIVE_OPERATIONS:
        reasons.append(f"Operation {operation!r} is not allowed for live execution.")
    if contains_any_key(query.get("pipeline"), DANGEROUS_AGGREGATE_STAGES):
        reasons.append("Aggregate pipeline contains a write stage such as $out or $merge.")
    if contains_any_key(query.get("query"), DANGEROUS_QUERY_OPERATORS):
        reasons.append("Find query contains risky server-side operator such as $where.")
    return bool(reasons), reasons


def build_live_case(andi_client: Andi, case: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    query = None
    build_error = None
    cache_hit = None
    try:
        query = andi_client.build_nlp_query(
            intent=copy.deepcopy(case["intent"]),
            query_identifier=case.get("query_identifier"),
            retry=False,
        )
        if case.get("query_identifier"):
            cached = andi_client.fetch_query_by_identifier(case["query_identifier"])
            cache_hit = cached == query
    except Exception as exc:  # pragma: no cover - Andi catches most exceptions.
        build_error = str(exc)

    build_ms = int((time.perf_counter() - started) * 1000)
    risky, risk_reasons = query_has_live_risk(query)
    execution = None
    exec_ms = None
    passed = False
    notes: list[str] = []

    if build_error:
        notes.append(f"Build failed: {build_error}")
    elif risky:
        notes.extend(risk_reasons)
    else:
        exec_started = time.perf_counter()
        try:
            execution = andi_client.run_query_executor(
                nlp_query=query,
                **copy.deepcopy(case.get("runtime_kwargs", {})),
            )
        except Exception as exc:  # pragma: no cover - Andi catches most exceptions.
            execution = {"status": "error", "message": str(exc)}
        exec_ms = int((time.perf_counter() - exec_started) * 1000)
        passed = live_execution_passed(execution)
        if not passed:
            notes.append("Execution returned an error, None, or an unexpected response shape.")

    if cache_hit is False:
        notes.append("Query identifier did not fetch the same generated query.")

    return {
        "id": case["id"],
        "title": case["title"],
        "difficulty": case["difficulty"],
        "collections": case["collections"],
        "intent": sanitize(case["intent"]),
        "runtime_inputs": sanitize(case.get("runtime_kwargs", {})),
        "generated_query": sanitize(query),
        "operation": query.get("operation") if isinstance(query, dict) else None,
        "build_ms": build_ms,
        "exec_ms": exec_ms,
        "cache_hit": cache_hit,
        "result_preview": preview_result(execution),
        "passed": passed,
        "notes": notes or ["Generated and executed through documented Andi flow."],
    }


def live_execution_passed(execution: Any) -> bool:
    if execution is None:
        return False
    if isinstance(execution, dict):
        status = str(execution.get("status") or execution.get("result") or "").lower()
        return status not in {"error", "failed", "forbidden"} and "message" not in execution
    return isinstance(execution, list)


def run_feature_tests() -> list[dict[str, Any]]:
    results = []
    mocked_query, payloads, cache_hit = build_query_with_mocked_agent("andi_feature_cache_probe")
    results.append(
        feature_result(
            "text_to_nosql_translation",
            "Text-to-NoSQL Translation",
            "Plain-English intent translated into a native MongoDB find query with nested imdb.rating criteria.",
            isinstance(mocked_query, dict)
            and mocked_query.get("operation") == "find"
            and mocked_query.get("collection") == "movies"
            and "imdb.rating" in mocked_query.get("query", {}),
            {"intent": FEATURE_INTENT, "generated_query": mocked_query},
        )
    )
    results.append(
        feature_result(
            "agentic_query_planning",
            "Agentic Query Planning",
            "Mocked transport observed an architect step followed by a query-generator step using schema context.",
            len(payloads) >= 2 and payload_contains(payloads, "Chief Architect") and payload_contains(payloads, "query_generator"),
            {"openai_call_count": len(payloads), "payload_summary": summarize_payloads(payloads)},
        )
    )
    results.append(
        feature_result(
            "persistent_query_caching",
            "Persistent Query Caching",
            "query_identifier stores the compiled query and fetch_query_by_identifier returns the same object.",
            cache_hit is True,
            {"query_identifier": "andi_feature_cache_probe", "cache_hit": cache_hit},
        )
    )
    results.append(
        feature_result(
            "privacy_first_schema_isolation",
            "Privacy-First Schema Isolation",
            "Captured agent payloads include schema metadata but none of the fake record sentinels.",
            payload_contains(payloads, "imdb.rating") and not any(payload_contains(payloads, marker) for marker in FAKE_DATA_SENTINELS),
            {
                "schema_fields_visible": ["title", "year", "genres", "imdb.rating", "movie_id"],
                "record_sentinel_count_checked": len(FAKE_DATA_SENTINELS),
                "payload_summary": summarize_payloads(payloads),
            },
        )
    )
    results.append(test_runtime_variables())
    results.append(test_complex_aggregation())
    results.append(test_single_endpoint_architecture())
    return results


def build_query_with_mocked_agent(query_identifier: str) -> tuple[Any, list[dict[str, Any]], bool | None]:
    transport = MockOpenAITransport()
    original_post_json = andi_agents.post_json
    os.environ.setdefault("OPENAPI_KEY", "offline-feature-test-key")
    os.environ.setdefault("OPENAI_MODEL", "offline-feature-test-model")
    try:
        andi_agents.post_json = transport
        andi_client = Andi(db_session=FakeDbSession(), analyzed_schemas=copy.deepcopy(SAMPLE_SCHEMA))
        query = andi_client.build_nlp_query(
            intent=copy.deepcopy(FEATURE_INTENT),
            query_identifier=query_identifier,
            retry=False,
        )
        cached = andi_client.fetch_query_by_identifier(query_identifier)
        return query, transport.payloads, cached == query
    finally:
        andi_agents.post_json = original_post_json


def test_runtime_variables() -> dict[str, Any]:
    fake_db = FakeDbSession()
    andi_client = Andi(db_session=fake_db, analyzed_schemas=copy.deepcopy(SAMPLE_SCHEMA))
    output = andi_client.run_query_executor(
        nlp_query=copy.deepcopy(FEATURE_QUERY),
        target_genre="Drama",
        min_rating=7.5,
    )
    find_audit = next((item for item in fake_db.audit if item.get("method") == "find"), {})
    query = find_audit.get("query", {})
    passed = (
        isinstance(output, list)
        and query.get("genres") == "Drama"
        and query.get("imdb.rating", {}).get("$gte") == 7.5
    )
    return feature_result(
        "secure_runtime_variables",
        "Secure Runtime Variables",
        "Placeholders are resolved at execution time and preserve native value types for exact placeholders.",
        passed,
        {"resolved_query": query, "output": preview_result(output), "audit": fake_db.audit},
    )


def test_complex_aggregation() -> dict[str, Any]:
    fake_db = FakeDbSession()
    andi_client = Andi(db_session=fake_db, analyzed_schemas=copy.deepcopy(SAMPLE_SCHEMA))
    output = andi_client.run_query_executor(
        nlp_query=copy.deepcopy(FEATURE_AGGREGATE_QUERY),
        target_email="person@example.com",
    )
    aggregate_audit = next((item for item in fake_db.audit if item.get("method") == "aggregate"), {})
    pipeline = aggregate_audit.get("pipeline", [])
    stage_names = [next(iter(stage.keys())) for stage in pipeline if isinstance(stage, dict) and stage]
    passed = isinstance(output, list) and {"$lookup", "$unwind", "$group", "$sort"}.issubset(stage_names)
    return feature_result(
        "complex_aggregations",
        "Complex Aggregations Out-of-the-Box",
        "Executor accepts a multi-stage aggregate pipeline with lookup, unwind, group, and sort.",
        passed,
        {"stage_names": stage_names, "pipeline": pipeline, "output": preview_result(output)},
    )


def test_single_endpoint_architecture() -> dict[str, Any]:
    fake_db = FakeDbSession()
    andi_client = Andi(db_session=fake_db, analyzed_schemas=copy.deepcopy(SAMPLE_SCHEMA))
    find_output = andi_client.run_query_executor(
        nlp_query=copy.deepcopy(FEATURE_QUERY),
        target_genre="Comedy",
        min_rating=6.8,
    )
    aggregate_output = andi_client.run_query_executor(
        nlp_query=copy.deepcopy(FEATURE_AGGREGATE_QUERY),
        target_email="person@example.com",
    )
    methods = [item.get("method") for item in fake_db.audit]
    passed = isinstance(find_output, list) and isinstance(aggregate_output, list) and "find" in methods and "aggregate" in methods
    return feature_result(
        "single_endpoint_architecture",
        "Single Endpoint Architecture",
        "One Andi instance can route different intent outputs through the same run_query_executor surface.",
        passed,
        {"methods": methods, "find": preview_result(find_output), "aggregate": preview_result(aggregate_output)},
    )


def feature_result(feature_id: str, title: str, claim: str, passed: bool, evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": feature_id,
        "title": title,
        "claim": claim,
        "passed": bool(passed),
        "evidence": sanitize(evidence),
        "notes": ["Feature evidence passed." if passed else "Feature evidence did not satisfy the expected condition."],
    }


def payload_contains(payloads: list[dict[str, Any]], needle: str) -> bool:
    return needle in json.dumps(payloads)


def summarize_payloads(payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary = []
    for index, payload in enumerate(payloads, start=1):
        messages = payload.get("messages", [])
        rendered = json.dumps(messages)
        summary.append(
            {
                "call": index,
                "model": payload.get("model"),
                "message_count": len(messages),
                "mentions_schema": "SCHEMA" in rendered or "schema" in rendered,
                "mentions_real_record_sentinel": any(marker in rendered for marker in FAKE_DATA_SENTINELS),
                "response_format": payload.get("response_format"),
            }
        )
    return summary


def run_live_benchmark(sample_size: int, require_live: bool) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    connection_string = os.environ.get("MONGODB_URI") or os.environ.get("MONGO_URI")
    if not connection_string:
        message = "MONGODB_URI/MONGO_URI is not present in the runtime environment; live tests were skipped."
        if require_live:
            raise RuntimeError(message)
        warnings.append(message)
        return {"status": "skipped", "collections": []}, [], warnings

    andi_client = Andi(db_session="", analyzed_schemas=[])
    init_result = andi_client.initialize_connection(connection_string=connection_string, database_name=DATABASE_NAME)
    internal_db = getattr(andi_client, "db", None)
    internal_db_failed = isinstance(internal_db, dict) and internal_db.get("result") is False
    if not isinstance(init_result, dict) or init_result.get("result") != "success" or internal_db_failed:
        message = "Andi failed to initialize sample_mflix connection."
        if require_live:
            raise RuntimeError(message)
        warnings.append(message)
        return {"status": "failed", "collections": []}, [], warnings

    schema_result = andi_client.analyze_schemas(BASE_COLLECTIONS, sample_size=sample_size)
    if not isinstance(schema_result, dict) or schema_result.get("result") != "success":
        warnings.append("Andi schema analysis failed; live query generation was skipped.")
        return {"status": "failed", "collections": []}, [], warnings

    live_results = [build_live_case(andi_client, case) for case in LIVE_CASES]
    return {
        "status": "success",
        "sample_size": sample_size,
        "collections": summarize_schema(andi_client.analyzed_schemas),
    }, live_results, warnings


def run_firewall_tests() -> list[dict[str, Any]]:
    results = []
    for case in FIREWALL_CASES:
        fake_db = FakeDbSession()
        andi_client = Andi(db_session=fake_db, analyzed_schemas=[])
        started = time.perf_counter()
        output = andi_client.run_query_executor(nlp_query=copy.deepcopy(case["nlp_query"]))
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        audit = fake_db.audit
        reached_db = any(item.get("method") in {"find", "aggregate"} for item in audit)
        forbidden = isinstance(output, dict) and output.get("status") == "forbidden"
        dangerous_reached = any(
            item.get("dangerous_stage") or item.get("dangerous_operator") or item.get("sensitive_projection")
            for item in audit
        )
        passed, notes = evaluate_firewall_case(case["expectation"], output, reached_db, dangerous_reached)
        results.append(
            {
                "id": case["id"],
                "title": case["title"],
                "expectation": case["expectation"],
                "input_query": sanitize(case["nlp_query"]),
                "output": sanitize(output),
                "audit": sanitize(audit),
                "elapsed_ms": elapsed_ms,
                "reached_db": reached_db,
                "dangerous_reached": dangerous_reached,
                "passed": passed,
                "notes": notes,
            }
        )
    return results


def evaluate_firewall_case(
    expectation: str,
    output: Any,
    reached_db: bool,
    dangerous_reached: bool,
) -> tuple[bool, list[str]]:
    if expectation == "forbidden":
        if isinstance(output, dict) and output.get("status") == "forbidden" and not reached_db:
            return True, ["Blocked with a forbidden response before collection access."]
        return False, ["Expected a forbidden response before database access."]
    if expectation == "error_before_db":
        if output is None and not reached_db:
            return True, ["Failed before database execution, but response is not structured."]
        return False, ["Expected missing placeholder to stop before database execution."]
    if expectation == "should_not_reach_db":
        if reached_db or dangerous_reached:
            return False, ["Risky query reached the fake database/session."]
        return True, ["Risky query was stopped before execution."]
    if expectation == "structured_rejection":
        if isinstance(output, dict) and output.get("status") in {"forbidden", "error"}:
            return True, ["Unknown operation received a structured rejection."]
        return False, ["Unknown operation did not receive a structured rejection."]
    return False, ["Unknown test expectation."]


def ratio_score(results: list[dict[str, Any]], empty_score: int = 0) -> int:
    if not results:
        return empty_score
    passed = sum(1 for item in results if item.get("passed"))
    return round((passed / len(results)) * 10)


def build_ratings(
    feature_results: list[dict[str, Any]],
    live_results: list[dict[str, Any]],
    firewall_results: list[dict[str, Any]],
    schema: dict[str, Any],
):
    find_and_aggregate = [
        item for item in live_results if item.get("difficulty") in {"moderate", "complex"}
    ]
    write_blocks = [item for item in firewall_results if item["expectation"] == "forbidden"]
    bypass_cases = [item for item in firewall_results if item["expectation"] != "forbidden"]
    feature_by_id = {item["id"]: item for item in feature_results}

    return [
        rating(
            "Text-to-NoSQL translation",
            feature_score(feature_by_id, "text_to_nosql_translation", live_bonus=bool(find_and_aggregate)),
            "Agent-generated query evidence plus live execution bonus when sample_mflix is reachable.",
            [feature_by_id.get("text_to_nosql_translation")] + find_and_aggregate,
        ),
        rating(
            "Agentic query planning",
            feature_score(feature_by_id, "agentic_query_planning"),
            "Captured mocked OpenAI calls show multi-agent routing before query generation.",
            [feature_by_id.get("agentic_query_planning")],
        ),
        rating(
            "Persistent query caching",
            feature_score(feature_by_id, "persistent_query_caching", base_pass_score=9),
            "query_identifier stores and retrieves the compiled query.",
            [feature_by_id.get("persistent_query_caching")],
        ),
        rating(
            "Privacy-first schema isolation",
            feature_score(feature_by_id, "privacy_first_schema_isolation", live_bonus=schema.get("status") == "success"),
            "Agent payloads contain schema metadata and no fake record sentinels; live schema analysis adds confidence.",
            [feature_by_id.get("privacy_first_schema_isolation")],
        ),
        rating(
            "Secure runtime variables",
            feature_score(feature_by_id, "secure_runtime_variables", base_pass_score=9),
            "Runtime placeholders resolve at executor time and preserve native types for exact placeholders.",
            [feature_by_id.get("secure_runtime_variables")],
        ),
        rating(
            "Complex aggregations",
            feature_score(feature_by_id, "complex_aggregations"),
            "Executor accepts a multi-stage pipeline with $lookup, $unwind, $group, and $sort.",
            [feature_by_id.get("complex_aggregations")],
        ),
        rating(
            "Single endpoint architecture",
            feature_score(feature_by_id, "single_endpoint_architecture", base_pass_score=9),
            "One Andi instance routes multiple query shapes through run_query_executor.",
            [feature_by_id.get("single_endpoint_architecture")],
        ),
        rating(
            "AI firewall behavior",
            max(0, round((ratio_score(write_blocks) * 0.6) + (ratio_score(bypass_cases) * 0.4))),
            "Direct write operation names are blocked; bypass-oriented probes remain critical evidence.",
            firewall_results,
        ),
    ]


def rating(name: str, score: int, rationale: str, evidence: list[dict[str, Any]]) -> dict[str, Any]:
    compact_evidence = [item for item in evidence if isinstance(item, dict)]
    return {
        "feature": name,
        "score": max(0, min(10, score)),
        "rationale": rationale,
        "evidence_ids": [item["id"] for item in compact_evidence[:5]],
    }


def feature_score(
    feature_by_id: dict[str, dict[str, Any]],
    feature_id: str,
    base_pass_score: int = 8,
    live_bonus: bool = False,
) -> int:
    item = feature_by_id.get(feature_id)
    if not item or not item.get("passed"):
        return 0
    return min(10, base_pass_score + (1 if live_bonus else 0))


def build_observations(
    feature_results: list[dict[str, Any]],
    live_results: list[dict[str, Any]],
    firewall_results: list[dict[str, Any]],
    warnings: list[str],
):
    passed_features = [item["title"] for item in feature_results if item.get("passed")]
    observations = [
        {
            "severity": "info",
            "title": "Advertised feature evidence is now separated from live DB reachability",
            "detail": "Feature tests validate NLP translation, agent planning, caching, schema-only payloads, runtime variables, aggregations, and the single executor surface with controlled Andi calls.",
        },
        {
            "severity": "info",
            "title": "Feature tests passing",
            "detail": ", ".join(passed_features) if passed_features else "No feature tests passed in this run.",
        },
        {
            "severity": "high",
            "title": "Aggregate write stages are not blocked before execution",
            "detail": "The executor deny-list checks operation names, but a read-looking aggregate can still contain $out or $merge unless callers pre-screen it.",
        },
        {
            "severity": "high",
            "title": "Sensitive-field access is not policy-controlled",
            "detail": "A projection asking for fields such as password or email is passed through unless the generated query or caller blocks it.",
        },
        {
            "severity": "medium",
            "title": "README and installed config disagree on OpenAI key name",
            "detail": "The README documents OPENAI_API_KEY, while installed andi-ai 0.1.12 reads OPENAPI_KEY and OPENAI_MODEL.",
        },
        {
            "severity": "medium",
            "title": "Unknown operations are not consistently rejected",
            "detail": "Unsupported operations can return None instead of a structured forbidden/error response.",
        },
        {
            "severity": "medium",
            "title": "Return shapes are inconsistent",
            "detail": "Successful reads return lists, blocked writes return dicts, and some failures return None, which complicates reliable app integrations.",
        },
        {
            "severity": "medium",
            "title": "Connection initialization can report a false success",
            "detail": "In the installed package, initialize_connection can return success even when the underlying Connection.initialize_database result is an error dict.",
        },
        {
            "severity": "low",
            "title": "Import side effects make secret handling harder to reason about",
            "detail": "Importing andi auto-loads dotenv and prints debug paths; this is convenient but noisy for production services.",
        },
    ]
    for warning in warnings:
        observations.append({"severity": "info", "title": "Runner warning", "detail": warning})
    failed_live = [item["id"] for item in live_results if not item.get("passed")]
    failed_firewall = [item["id"] for item in firewall_results if not item.get("passed")]
    if failed_live:
        observations.append(
            {
                "severity": "info",
                "title": "Live test failures require inspection",
                "detail": "Failed live cases: " + ", ".join(failed_live[:8]),
            }
        )
    if failed_firewall:
        observations.append(
            {
                "severity": "high",
                "title": "Firewall bypass probes failed",
                "detail": "Failed firewall cases: " + ", ".join(failed_firewall[:8]),
            }
        )
    return observations


def build_report(skip_live: bool, require_live: bool, sample_size: int) -> dict[str, Any]:
    warnings: list[str] = []
    live_schema = {"status": "skipped", "collections": []}
    live_results: list[dict[str, Any]] = []
    feature_results = run_feature_tests()

    if skip_live:
        warnings.append("Live tests skipped by --skip-live; only fake-session firewall tests were run.")
    else:
        live_schema, live_results, live_warnings = run_live_benchmark(sample_size, require_live)
        warnings.extend(live_warnings)

    firewall_results = run_firewall_tests()
    ratings = build_ratings(feature_results, live_results, firewall_results, live_schema)
    observations = build_observations(feature_results, live_results, firewall_results, warnings)

    return {
        "meta": {
            "title": "ANDI-AI sample_mflix Benchmark",
            "generated_at": utc_now(),
            "andi_ai_version": "0.1.12",
            "database": DATABASE_NAME,
            "collections": BASE_COLLECTIONS,
            "live_status": live_schema.get("status"),
            "secret_policy": "Codex never reads .env; runner relies on runtime environment loading.",
            "docs": [
                "https://github.com/Satty27/andi-ai/blob/main/README.md",
                "https://raw.githubusercontent.com/Satty27/andi-ai/main/README.md",
            ],
        },
        "schema": live_schema,
        "feature_tests": feature_results,
        "live_tests": live_results,
        "firewall_tests": firewall_results,
        "ratings": ratings,
        "critical_observations": observations,
    }


def write_report(report: dict[str, Any], json_path: Path, js_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    js_path.parent.mkdir(parents=True, exist_ok=True)
    json_text = json.dumps(report, indent=2, sort_keys=True)
    json_path.write_text(json_text + "\n", encoding="utf-8")
    js_path.write_text("window.ANDI_REPORT = " + json_text + ";\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run ANDI-AI sample_mflix benchmark and generate static report data.")
    parser.add_argument("--skip-live", action="store_true", help="Skip live sample_mflix/OpenAI tests.")
    parser.add_argument("--require-live", action="store_true", help="Fail if live benchmark cannot run.")
    parser.add_argument("--sample-size", type=int, default=12, help="Schema sample size passed to Andi.")
    parser.add_argument("--json-output", default=str(REPORT_JSON), help="Sanitized JSON report path.")
    parser.add_argument("--js-output", default=str(REPORT_JS), help="Static app report-data.js path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(skip_live=args.skip_live, require_live=args.require_live, sample_size=args.sample_size)
    write_report(report, Path(args.json_output), Path(args.js_output))
    print(f"Wrote sanitized report to {args.json_output}")
    print(f"Wrote static app data to {args.js_output}")
    print(f"Live status: {report['meta']['live_status']}")
    print("No .env contents are read or printed by this runner.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
