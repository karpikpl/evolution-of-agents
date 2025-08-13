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

DEFAULT_CSV_PATH = os.environ.get("BOOKS_CSV_PATH", "docs/book1-100k.csv")


@lru_cache(maxsize=1)
def _load_df(csv_path: str = DEFAULT_CSV_PATH) -> pd.DataFrame:
    if not os.path.exists(csv_path):
        raise FileNotFoundError(
            f"Books CSV not found at '{csv_path}'. Set BOOKS_CSV_PATH env var or pass path explicitly."
        )
    df = pd.read_csv(csv_path)
    df.columns = [c.strip() for c in df.columns]
    return df


def _serialize_rows(df: pd.DataFrame, limit: int = 5) -> List[dict]:
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
    name="search_books",
    description="Search books by a query string contained in title (case-insensitive) and return concise JSON rows.",
)
def search_books(query: str, limit: int = 5, csv_path: Optional[str] = None) -> str:
    import json

    limit = max(1, min(int(limit), 20))
    df = _load_df(csv_path or DEFAULT_CSV_PATH)
    if not query:
        return json.dumps({"error": "Empty query"})
    mask = df["Name"].str.contains(query, case=False, na=False)
    result = df.loc[mask].copy()
    result = result.sort_values(
        by=["Rating", "CountsOfReview"], ascending=[False, False]
    )
    payload = _serialize_rows(result, limit)
    return json.dumps({"count": len(payload), "items": payload})


@kernel_function(
    name="get_book_by_id",
    description="Lookup a single book record by numeric Id and return a concise JSON object.",
)
def get_book_by_id(book_id: int, csv_path: Optional[str] = None) -> str:
    import json

    df = _load_df(csv_path or DEFAULT_CSV_PATH)
    try:
        book_id = int(book_id)
    except Exception:
        return json.dumps({"error": "book_id must be an integer"})
    row = df.loc[df["Id"] == book_id]
    if row.empty:
        return json.dumps({"error": f"No book with Id {book_id}"})
    payload = _serialize_rows(row, 1)[0]
    return json.dumps(payload)


@kernel_function(
    name="author_top",
    description="List top rated books for an author name (substring match) ordered by rating then reviews.",
)
def author_top(
    author_query: str, limit: int = 5, csv_path: Optional[str] = None
) -> str:
    import json

    limit = max(1, min(int(limit), 20))
    if not author_query:
        return json.dumps({"error": "Empty author_query"})
    df = _load_df(csv_path or DEFAULT_CSV_PATH)
    mask = df["Authors"].str.contains(author_query, case=False, na=False)
    subset = df.loc[mask].copy()
    if subset.empty:
        return json.dumps({"count": 0, "items": []})
    subset = subset.sort_values(
        by=["Rating", "CountsOfReview"], ascending=[False, False]
    )
    payload = _serialize_rows(subset, limit)
    return json.dumps({"count": len(payload), "items": payload})


def load_books_plugin(kernel) -> None:
    """Register this module's functions with an existing Semantic Kernel instance."""
    kernel.add_functions(
        [search_books, get_book_by_id, author_top], plugin_name="books"
    )


__all__ = [
    "search_books",
    "get_book_by_id",
    "author_top",
    "load_books_plugin",
]
