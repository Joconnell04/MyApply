# MyApply AgentKit Tools Service

MyApply Tools exposes JSON-only FastAPI endpoints that AgentKit can call to query candidate graphs and persist planner/generator bundles. All endpoints require bearer auth and the `X-MyApply-User` header so requests can be scoped to a single candidate.

## Environment

```
MYAPPLY_API_KEY=dev_key
DATABASE_URL=sqlite:///./myapply_tools.db
```

> Use `python -m dotenv.cli set` or a `.env` file to load variables locally. For production, point `DATABASE_URL` at a managed SQLite/Postgres instance.

## Run Locally

```
uvicorn myapply_tools.app:app --reload
```

The server auto-creates tables and seeds demo experiences for `demo-user`.

## Authentication

- `Authorization: Bearer <MYAPPLY_API_KEY>`
- `X-MyApply-User: <user-id>` (must match any `user_id` in the payload)

Missing or mismatched headers return `401`.

## Endpoints

| Method | Path | Description |
| --- | --- | --- |
| POST | `/tools/set_generation_bundle` | Upsert resume generation bundle. |
| POST | `/tools/get_generation_bundle` | Fetch resume bundle. |
| POST | `/tools/set_cl_bundle` | Upsert cover-letter bundle. |
| POST | `/tools/get_cl_bundle` | Fetch cover-letter bundle. |
| POST | `/tools/get_candidate_facets` | Aggregate candidate facets from experiences. |
| POST | `/tools/search_experiences` | Score and paginate experiences. |
| POST | `/tools/get_evidence` | Fetch evidence for a single experience. |
| POST | `/tools/get_evidence_batch` | Fetch evidence for many experiences. |
| POST | `/tools/get_company_insights` | Stub insights helper (returns canned strings). |
| GET | `/tools/toolspec` | JSON schema describing AgentKit tool definitions. |

All responses are JSON objects with an `ok` flag. 4xx codes carry `{ "detail": ... }`.

## Curl Cheatsheet

```
export API_BASE="http://127.0.0.1:8000"
export API_KEY="dev_key"
export USER="demo-user"
COMMON="-H \"Authorization: Bearer $API_KEY\" -H \"X-MyApply-User: $USER\" -H 'Content-Type: application/json'"

curl -s $API_BASE/tools/set_generation_bundle \
  $COMMON \
  -d '{
        "user_id":"'$USER'",
        "hash":"run-123",
        "plan":{"steps":["collect","draft"]},
        "resolved_jd":{"title":"Data Analyst"},
        "prefs":{"tone":"confident"},
        "ttl_seconds":604800
      }'

curl -s $API_BASE/tools/get_generation_bundle \
  $COMMON \
  -d '{"user_id":"'$USER'","hash":"run-123"}'

curl -s $API_BASE/tools/set_cl_bundle \
  $COMMON \
  -d '{
        "user_id":"'$USER'",
        "hash":"run-123",
        "jd":{"company":"Acme"},
        "story_plan":{"sections":3},
        "prefs":{"voice":"optimistic"}
      }'

curl -s $API_BASE/tools/get_cl_bundle \
  $COMMON \
  -d '{"user_id":"'$USER'","hash":"run-123"}'

curl -s $API_BASE/tools/get_candidate_facets \
  $COMMON \
  -d '{"user_id":"'$USER'","limit":5}'

curl -s $API_BASE/tools/search_experiences \
  $COMMON \
  -d '{
        "user_id":"'$USER'",
        "query":"dashboards",
        "page":1,
        "page_size":2
      }'

curl -s $API_BASE/tools/get_evidence \
  $COMMON \
  -d '{"experience_id":"exp-001","include_artifacts":false}'

curl -s $API_BASE/tools/get_evidence_batch \
  $COMMON \
  -d '{"experience_ids":["exp-001","exp-002"]}'

curl -s $API_BASE/tools/get_company_insights \
  $COMMON \
  -d '{"company_name":"Acme Labs","limit":3}'

curl -s $API_BASE/tools/toolspec
```

## Testing

```
pytest myapply_tools/tests -q
```

Tests reset the database per module, verify bundle TTL expiry, pagination, and evidence parity, and assert auth failures use HTTP 401.

## Tool Specification

`/tools/toolspec` returns the JSON required for AgentKit registration. The same payload is exported as `myapply_tools.schemas.AGENTKIT_TOOL_SPEC` for in-process clients.
