"""Load Logfire traces into DuckDB with dlt."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import duckdb
import dlt
from dotenv import load_dotenv
from dlt.sources.helpers import requests


LOGFIRE_QUERY_URL = "https://logfire-us.pydantic.dev/v1/query"
DEFAULT_QUERY = """
SELECT * FROM records
WHERE otel_scope_name = 'pydantic-ai'
ORDER BY start_timestamp DESC
LIMIT 1000
"""


def _query_logfire(read_token: str, query: str) -> list[dict[str, Any]]:
    """Query the Logfire read API and return rows as dictionaries."""
    headers = {"Authorization": f"Bearer {read_token}"}
    response = requests.get(
        LOGFIRE_QUERY_URL,
        headers=headers,
        params={"sql": query},
        timeout=60,
    )
    if not response.ok:
        raise RuntimeError(f"Failed to query Logfire API: {response.status_code}: {response.text}")
    return _normalize_payload(response.json())


def _normalize_payload(payload: Any) -> list[dict[str, Any]]:
    """Normalize common Logfire API payload shapes into a list of dict rows."""
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]

    if not isinstance(payload, dict):
        raise TypeError(f"Unsupported Logfire payload type: {type(payload)!r}")

    cols = payload.get("columns")
    if isinstance(cols, list) and cols and isinstance(cols[0], dict) and "values" in cols[0]:
        names = [c["name"] for c in cols]
        values = [c["values"] for c in cols]
        return [dict(zip(names, row)) for row in zip(*values)]

    if "rows" in payload and "columns" in payload:
        columns = payload["columns"]
        rows = payload["rows"]
        return [dict(zip(columns, row)) for row in rows]

    for key in ("data", "rows", "results", "records", "items"):
        value = payload.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
        if isinstance(value, dict):
            return _normalize_payload(value)

    if "result" in payload:
        return _normalize_payload(payload["result"])

    raise ValueError(f"Unsupported Logfire payload shape: {payload}")


@dlt.resource(name="spans", write_disposition="replace")
def logfire_spans() -> Any:
    """Yield Logfire record rows as dlt resources."""
    load_dotenv()

    read_token = os.environ["LOGFIRE_READ_TOKEN"]
    query = os.getenv("LOGFIRE_QUERY", DEFAULT_QUERY)

    rows = _query_logfire(read_token, query)
    for row in rows:
        yield row


def load_logfire_traces() -> None:
    """Load Logfire spans into a local DuckDB database."""
    pipeline = dlt.pipeline(
        pipeline_name="logfire_traces",
        destination="duckdb",
        dataset_name="agent_traces",
    )

    load_info = pipeline.run(logfire_spans(), table_name="spans")
    print(load_info)

    show_table_names()


def _find_duckdb_path() -> Path:
    """Locate the DuckDB file created by the dlt pipeline."""
    path = Path("logfire_traces.duckdb")
    if path.exists():
        return path
    candidates = sorted(Path(".").rglob("*.duckdb"))
    if not candidates:
        raise FileNotFoundError("Could not find a DuckDB database file for the pipeline.")
    return candidates[-1]


def show_table_names() -> None:
    """Print the table names in the agent_traces schema."""
    db_path = _find_duckdb_path()
    with duckdb.connect(str(db_path)) as conn:
        rows = conn.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'agent_traces'
            ORDER BY table_name
            """
        ).fetchall()

    print("Tables in agent_traces schema:")
    for row in rows:
        print(row[0])


if __name__ == "__main__":
    load_logfire_traces()