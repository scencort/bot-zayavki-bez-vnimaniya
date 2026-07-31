from __future__ import annotations

import re
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen


DOC_ID_PATTERN = re.compile(r"/document/d/([a-zA-Z0-9_-]+)")


def build_export_url(google_docs_url: str) -> str:
    doc_id = extract_doc_id(google_docs_url)
    return f"https://docs.google.com/document/d/{doc_id}/export?format=txt"


def extract_doc_id(google_docs_url: str) -> str:
    match = DOC_ID_PATTERN.search(google_docs_url)
    if match:
        return match.group(1)

    parsed = urlparse(google_docs_url)
    query = parse_qs(parsed.query)
    if "id" in query and query["id"]:
        return query["id"][0]

    raise ValueError("Could not extract Google Docs document ID from the provided URL")


def fetch_document_text(google_docs_url: str, timeout_seconds: int = 30) -> str:
    export_url = build_export_url(google_docs_url)
    request = Request(
        export_url,
        headers={
            "User-Agent": "attention-free-leads-bot/0.1",
        },
    )

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset)
    except HTTPError as exc:
        raise RuntimeError(
            f"Google Docs returned HTTP {exc.code}. Ensure the document is shared for viewing."
        ) from exc
    except URLError as exc:
        raise RuntimeError("Could not reach Google Docs") from exc
