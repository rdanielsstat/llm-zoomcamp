# Agent Traces Pipeline

A mini-project: instrument a Pydantic AI FAQ agent with Logfire, pull the trace data into DuckDB with dlt, and query it.

## Setup

```bash
uv init
uv add openai minsearch requests python-dotenv pydantic-ai logfire
uv add "dlt[duckdb]"
```

`.env` holds both tokens:

```
OPENAI_API_KEY=sk-...
LOGFIRE_TOKEN=...
LOGFIRE_READ_TOKEN=...
```

## 1. Spans per agent run

Added to `main.py`, above the agent code:

```python
import logfire
from dotenv import load_dotenv

load_dotenv()
logfire.configure()
logfire.instrument_pydantic_ai()
```

Running the query "How do I run Ollama locally?" printed this trace:

```
faq_agent run
  chat gpt-5.4-mini
  running tool: search
  chat gpt-5.4-mini
```

Four spans: the agent run, an LLM call, the search tool call, and a second LLM call that turns the search results into an answer. The count moves with how many searches the model decides to run.

**Result: 4**

## 2. Loading traces into DuckDB

`dlt init logfire duckdb` falls back to the intro template, since there's no verified Logfire source. I gutted the template and wrote `logfire_pipeline.py` against the Logfire query API.

Three things tripped this up:

The query endpoint is a GET, not a POST. SQL goes in a `sql` query parameter, the read token in an `Authorization: Bearer` header:

```python
response = requests.get(
    "https://logfire-us.pydantic.dev/v1/query",
    headers={"Authorization": f"Bearer {read_token}"},
    params={"sql": query},
    timeout=60,
)
```

The response comes back column-oriented, with values nested inside each column object rather than as a separate `rows` key:

```python
cols = payload["columns"]
names = [c["name"] for c in cols]
values = [c["values"] for c in cols]
rows = [dict(zip(names, row)) for row in zip(*values)]
```

Naming the pipeline and the dataset both `agent_traces` breaks the load step. DuckDB can't tell whether `agent_traces` means the catalog or the schema and raises a binder error. Renaming the pipeline to `logfire_traces` while keeping the dataset as `agent_traces` fixes it:

```python
pipeline = dlt.pipeline(
    pipeline_name="logfire_traces",
    destination="duckdb",
    dataset_name="agent_traces",
)
```

Counting what landed:

```sql
SELECT COUNT(*) 
  FROM information_schema.tables
 WHERE table_schema = 'agent_traces';
```

dlt unpacked the nested span attributes into a `spans` table plus child tables for input messages, output messages, tool definitions, tool call results, token usage details, and the request parameters, several of those nested two levels deep. Three dlt bookkeeping tables (`_dlt_loads`, `_dlt_pipeline_state`, `_dlt_version`) sit in the same schema and count toward the total.

**Result: 24**

## 3. Input token usage

The token counts flatten into columns on the `spans` table. Note the single underscores in the normalized name:

```sql
SELECT column_name 
  FROM information_schema.columns
 WHERE table_schema = 'agent_traces'
   AND table_name = 'spans'
   AND column_name LIKE '%token%';
```

Summing per trace:

```sql
SELECT trace_id,
       SUM(attributes__gen_ai_usage_input_tokens) AS input_tokens,
       COUNT(*) AS spans
  FROM agent_traces.spans
 GROUP BY trace_id
 ORDER BY input_tokens DESC;
```

```
019f80cf327c47c8a27924d4dae255c1  1488  4
019f80ceb640f2bb0cf79bab8bdfb639  1095  4
019f80cd6645f30b61eaeb41d2e1c7df  1030  4
```

The `message` column on the agent-run span is generic, so identifying which trace is which means joining down to the input message parts:

```sql
SELECT s.trace_id, substr(p.content, 1, 80) AS content
  FROM agent_traces.spans s
  JOIN agent_traces.spans__attributes__gen_ai_input_messages m
    ON m._dlt_parent_id = s._dlt_id
  JOIN agent_traces.spans__attributes__gen_ai_input_messages__parts p
    ON p._dlt_parent_id = m._dlt_id
 WHERE p.content IS NOT NULL
 ORDER BY s.trace_id, s.start_timestamp;
```

That points at `019f80cf...` as the Ollama run, totalling 1488 input tokens across two LLM calls: 204 for the first, which sees only the system prompt and question, and 1284 for the second, which also carries the search results. The `attributes__gen_ai_aggregated_usage_input_tokens` value on the agent-run span agrees at 1488.

## Gotchas

Running `duckdb.connect()` on a path that doesn't exist creates an empty database rather than erroring, which makes a misplaced file look like a failed load. `find . -name "*.duckdb"` settles it.

dlt writes the database to the working directory of the script, named after the pipeline. Here that's `logfire_traces.duckdb`.

A failed load leaves the package pending and dlt retries it on the next run, ignoring any new data. Clear it with `dlt pipeline agent_traces drop-pending-packages`.

The "columns did not receive any data" warnings during normalization are noise. They list optional span attributes that these runs never populated, like exception fields and HTTP metadata.
