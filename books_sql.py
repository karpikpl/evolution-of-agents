"""Books dataset tool / plugin for LLM function-calling.

Provides lightweight semantic-kernel compatible functions to explore the
`docs/book1-100k.csv` dataset (or another CSV passed via env var or parameter).

Functions exposed:
 - search_books: fuzzy / substring search over Name column
 - get_book_by_id: fetch a single record by Id
 - author_top: list top rated books for an author

Design goals:
 - Fast load: lazily load the dataframe on first use (singleton pattern)
 - Safe output: limit rows & truncate long text to keep LLM context small
 - Deterministic: sorting and stable field ordering
"""

from __future__ import annotations
import os
from functools import lru_cache
from typing import List, Optional
import pandas as pd
from semantic_kernel.functions import kernel_function
import duckdb
import json

DEFAULT_CSV_PATH = os.environ.get("BOOKS_CSV_PATH", "docs/book1-100k.csv")


class BooksSql:
    """Encapsulates access & lightweight query helpers for the books CSV dataset.

    Use register(kernel) to expose the decorated methods to Semantic Kernel.
    """

    @staticmethod
    @lru_cache(maxsize=1)
    def _load_df(csv_path: str = DEFAULT_CSV_PATH) -> pd.DataFrame:
        if not os.path.exists(csv_path):
            raise FileNotFoundError(
                f"Books CSV not found at '{csv_path}'. Set BOOKS_CSV_PATH env var or pass path explicitly."  # noqa: E501
            )
        df = pd.read_csv(csv_path)
        df.columns = [c.strip() for c in df.columns]
        return df

    def _serialize_rows(self, df: pd.DataFrame, limit: int = 5) -> List[dict]:
        rows = []
        for _, r in df.head(limit).iterrows():
            rows.append(
                {
                    "Id": int(r.get("Id")) if not pd.isna(r.get("Id")) else None,
                    "Name": str(r.get("Name"))[:200],
                    "Authors": str(r.get("Authors"))[:120],
                    "Rating": (
                        float(r.get("Rating")) if not pd.isna(r.get("Rating")) else None
                    ),
                    "Pages": (
                        int(r.get("pagesNumber"))
                        if not pd.isna(r.get("pagesNumber"))
                        else None
                    ),
                    "Year": (
                        int(r.get("PublishYear"))
                        if not pd.isna(r.get("PublishYear"))
                        else None
                    ),
                    "Reviews": (
                        int(r.get("CountsOfReview"))
                        if not pd.isna(r.get("CountsOfReview"))
                        else None
                    ),
                }
            )
        return rows

    @kernel_function(
        name="sql_books",
        description=(
            "Run a read-only SQL SELECT over the books dataframe as table 'books'. "
            "Columns: Id (int), Name (text), Authors (text), Rating (float), CountsOfReview (int), pagesNumber (int), PublishYear (int). "
            "Supports SELECT / WITH, WHERE, ORDER BY, expressions; result limited to 20 rows."
        ),
    )
    def sql_books(
        self, sql: str, limit: int = 5, csv_path: Optional[str] = None
    ) -> str:
        """Execute a limited, read-only SQL query against the books CSV using DuckDB.

        Simplified limit logic (consistent with other functions):
        - Clamp limit parameter to 1..20
        - Ignore any LIMIT inside user SQL; we wrap as subquery and enforce our own
        - Allow SELECT or WITH queries; single statement only
        """
        if not sql or not isinstance(sql, str):
            return json.dumps({"error": "Empty sql"})

        user_sql = sql.strip().rstrip(";")
        # Disallow multiple statements rudimentarily
        if user_sql.count(";") > 0:
            return json.dumps({"error": "Multiple statements not allowed"})

        # Clamp limit like other helper methods (1..20)
        limit = max(1, min(int(limit), 20))

        lowered = user_sql.lower()
        # Require starts with select or with (still basic guard)
        if not (lowered.startswith("select") or lowered.startswith("with")):
            return json.dumps({"error": "Query must start with SELECT or WITH"})

        df = self._load_df(csv_path or DEFAULT_CSV_PATH)
        try:
            con = duckdb.connect(database=":memory:")
            con.register("books", df)
            wrapped = f"SELECT * FROM ({user_sql}) t LIMIT {limit}"
            query_df = con.execute(wrapped).fetch_df()
        except Exception as e:
            return json.dumps({"error": f"SQL error: {e}"})
        finally:
            try:
                con.close()
            except Exception:
                pass

        payload = self._serialize_rows(query_df, limit)
        return json.dumps({"count": len(payload), "items": payload})

    @kernel_function(
        name="books_schema",
        description="Return JSON describing the 'books' table schema (columns, types, brief descriptions) to help form SQL queries.",
    )
    def books_schema(self, csv_path: Optional[str] = None) -> str:
        df = self._load_df(csv_path or DEFAULT_CSV_PATH)
        # Column descriptions
        descriptions = {
            "Id": "Unique numeric identifier",
            "Name": "Book title",
            "Authors": "Author name(s), possibly multiple separated by commas",
            "Rating": "Average reader rating (float)",
            "CountsOfReview": "Number of reviews",
            "pagesNumber": "Number of pages",
            "PublishYear": "Publication year",
        }
        cols = []
        for c in [
            "Id",
            "Name",
            "Authors",
            "Rating",
            "CountsOfReview",
            "pagesNumber",
            "PublishYear",
        ]:
            if c in df.columns:
                series = df[c]
                sample = next((str(v) for v in series.head(50) if pd.notna(v)), None)
                cols.append(
                    {
                        "name": c,
                        "dtype": str(series.dtype),
                        "description": descriptions.get(c, ""),
                        "sample": sample[:60] if sample else None,
                    }
                )
        out = {
            "table": "books",
            "row_count": int(len(df)),
            "columns": cols,
            "guidance": "Use table name 'books'. Limit result rows; heavy aggregations are fine. Primary key: Id.",
        }
        return json.dumps(out)


__all__ = ["BooksSql"]
