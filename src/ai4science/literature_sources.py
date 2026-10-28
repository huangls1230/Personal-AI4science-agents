"""Bounded, read-only scholarly source clients. All returned metadata is untrusted.

Only fixed public endpoints are contacted; source-returned links are never fetched.
Search itself and DOI lookup are source assertions, not independent verification.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import threading
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener
import xml.etree.ElementTree as ET

MAX_BODY = 2_000_000
MAX_LIMIT = 50
CACHE_SECONDS = 86_400
_ARXIV_LOCK = threading.Lock()
_ARXIV_LAST = None


def _now():
    return datetime.now(timezone.utc).isoformat()


def _text(value, limit=30000):
    if not isinstance(value, str):
        return None
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]*>", " ", value))).strip()[:limit] or None


def _url(value):
    # These are references only, never request targets. Discard non-web schemes.
    if not isinstance(value, str) or len(value) > 2048:
        return None
    from urllib.parse import urlsplit
    try:
        parts = urlsplit(value)
        if parts.scheme.lower() not in ("http", "https") or not parts.hostname or parts.username or parts.password:
            return None
    except ValueError:
        return None
    return value


def _type(value):
    return {"journal-article": "journal_article",
            "proceedings-article": "conference_paper", "proceedings_article": "conference_paper",
            "conference": "conference_paper", "preprint": "preprint", "posted-content": "preprint",
            "book": "book", "book-chapter": "book"}.get(value, "unknown" if not value else "other")


def _crossref(item):
    title = item.get("title") or []
    venue = item.get("container-title") or []
    date = item.get("published") or item.get("issued") or {}
    parts = date.get("date-parts") or [[]]
    year = parts[0][0] if parts[0] and isinstance(parts[0][0], int) else None
    authors = [" ".join(filter(None, [_text(a.get("given")), _text(a.get("family"))])) for a in item.get("author", []) if isinstance(a, dict)]
    return {"title": _text(title[0]) if title else None, "authors": [a for a in authors if a],
            "year": year, "venue": _text(venue[0]) if venue else None, "doi": _text(item.get("DOI"), 500),
            "source_url": _url(item.get("URL")), "abstract": _text(item.get("abstract")),
            "fulltext_url": None, "publication_type": _type(item.get("type")), "source": "crossref"}


def _openalex(item):
    inverse = item.get("abstract_inverted_index") or {}
    # Inverted index comes from a remote service and can contain invalid positions.
    words = sorted((p, word) for word, positions in inverse.items() if isinstance(word, str) and isinstance(positions, list)
                   for p in positions if isinstance(p, int) and 0 <= p < 10000)[:10000] if isinstance(inverse, dict) else []
    location = item.get("primary_location") or {}
    source = location.get("source") or {}
    oa = item.get("best_oa_location") or {}
    doi = item.get("doi")
    if isinstance(doi, str):
        doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi, flags=re.I)
    return {"title": _text(item.get("display_name")),
            "authors": [n for a in item.get("authorships", []) if isinstance(a, dict) for n in [_text((a.get("author") or {}).get("display_name"))] if n],
            "year": item.get("publication_year") if isinstance(item.get("publication_year"), int) else None,
            "venue": _text(source.get("display_name")), "doi": _text(doi, 500), "source_url": _url(item.get("id")),
            "abstract": _text(" ".join(w for _, w in words)), "fulltext_url": _url(oa.get("pdf_url")),
            "publication_type": _type(item.get("type")), "source": "openalex"}


def _semantic(item):
    ids = item.get("externalIds") or {}
    types = item.get("publicationTypes") or []
    typ = "preprint" if "Preprint" in types else "journal_article" if "JournalArticle" in types else "conference_paper" if "Conference" in types else "unknown"
    pdf = item.get("openAccessPdf") or {}
    return {"title": _text(item.get("title")), "authors": [n for a in item.get("authors", []) if isinstance(a, dict) for n in [_text(a.get("name"))] if n],
            "year": item.get("year") if isinstance(item.get("year"), int) else None, "venue": _text(item.get("venue")),
            "doi": _text(ids.get("DOI"), 500), "source_url": _url(item.get("url")), "abstract": _text(item.get("abstract")),
            "fulltext_url": _url(pdf.get("url")), "publication_type": typ, "source": "semantic_scholar"}


def _arxiv(data):
    if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise ValueError("XML declarations are not allowed")
    root = ET.fromstring(data)
    if root.tag != "{http://www.w3.org/2005/Atom}feed":
        raise ValueError("response is not an Atom feed")
    ns = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
    items = []
    for entry in root.findall("a:entry", ns):
        get = lambda name: entry.findtext(name, default=None, namespaces=ns)
        entry_id = get("a:id") or ""
        if re.match(r"^https?://arxiv\.org/api/errors(?:#|/|$)", entry_id, flags=re.I):
            raise ValueError("arXiv API returned an error feed")
        published = get("a:published") or ""
        pdf = next((x.get("href") for x in entry.findall("a:link", ns) if x.get("title") == "pdf"), None)
        items.append({"title": _text(get("a:title")), "authors": [n for a in entry.findall("a:author", ns) for n in [_text(a.findtext("a:name", namespaces=ns))] if n],
                      "year": int(published[:4]) if published[:4].isdigit() else None, "venue": "arXiv",
                      "doi": _text(get("arxiv:doi"), 500), "source_url": _url(get("a:id")), "abstract": _text(get("a:summary")),
                      "fulltext_url": _url(pdf), "publication_type": "preprint", "source": "arxiv"})
    total_text = root.findtext("{http://a9.com/-/spec/opensearch/1.1/}totalResults")
    total = int(total_text) if total_text and total_text.isdigit() else None
    return items, total


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _fetch(url, timeout, headers=None):
    # The URL is assembled exclusively from constant HTTPS API endpoints.
    request = Request(url, headers={"User-Agent": "PersonalAI4Science/0.1 (research metadata client)", **(headers or {})})
    with build_opener(_NoRedirect()).open(request, timeout=timeout) as response:
        body = response.read(MAX_BODY + 1)
    if len(body) > MAX_BODY:
        raise ValueError("response exceeds byte limit")
    return body


def _cache_file(cache_dir, identity):
    if cache_dir is None:
        return None
    # Cache data can include abstracts; it belongs in the project workspace only.
    root = (Path(__file__).resolve().parents[2] / "workspace").resolve(strict=True)
    path = Path(cache_dir).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError("cache directory must be inside project workspace") from exc
    path.mkdir(parents=True, exist_ok=True)
    file = path / (hashlib.sha256(identity.encode()).hexdigest() + ".json")
    try:
        file.resolve().relative_to(root)
    except ValueError as exc:
        raise ValueError("cache file escapes project workspace") from exc
    return file


def _cached(path):
    if path is None:
        return None
    try:
        if path.stat().st_size > MAX_BODY or time.time() - path.stat().st_mtime > CACHE_SECONDS:
            return None
        with path.open(encoding="utf-8") as f:
            entry = json.load(f)
        return entry if isinstance(entry, dict) and isinstance(entry.get("items"), list) and isinstance(entry.get("retrieved_at"), str) else None
    except (OSError, ValueError):
        return None


def _save(path, entry):
    if path is not None:
        # Atomic replacement; no API key, URL, or raw response is written.
        import os
        import tempfile
        temp_name = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as f:
                temp_name = f.name
                json.dump(entry, f, ensure_ascii=False)
            os.replace(temp_name, path)
        finally:
            if temp_name and os.path.exists(temp_name):
                os.unlink(temp_name)


def _wait_arxiv():
    """Space arXiv requests by three seconds within this Python process."""
    global _ARXIV_LAST
    with _ARXIV_LOCK:
        now = time.monotonic()
        if _ARXIV_LAST is not None:
            delay = 3.0 - (now - _ARXIV_LAST)
            if delay > 0:
                time.sleep(delay)
        _ARXIV_LAST = time.monotonic()


def _request(source, query, limit, page, api_key, timeout):
    headers = {}
    if source == "crossref":
        url = "https://api.crossref.org/works?" + urlencode({"query.bibliographic": query, "rows": limit, "offset": (page - 1) * limit})
    elif source == "openalex":
        if not api_key:
            raise ValueError("OpenAlex API key is required")
        url = "https://api.openalex.org/works?" + urlencode({"search": query, "per-page": limit, "page": page, "api_key": api_key})
    elif source == "semantic_scholar":
        url = "https://api.semanticscholar.org/graph/v1/paper/search?" + urlencode({"query": query, "limit": limit, "offset": (page - 1) * limit, "fields": "title,authors,year,venue,externalIds,url,abstract,openAccessPdf,publicationTypes"})
        if api_key:
            headers["x-api-key"] = api_key
    elif source == "arxiv":
        url = "https://export.arxiv.org/api/query?" + urlencode({"search_query": query, "start": (page - 1) * limit, "max_results": limit})
    else:
        raise ValueError("unsupported source")
    if source == "arxiv":
        _wait_arxiv()
    body = _fetch(url, timeout, headers)
    if source == "arxiv":
        items, total = _arxiv(body)
        return items, len(items) == limit and (total is None or page * limit < total)
    payload = json.loads(body)
    if source == "crossref":
        message = payload["message"]
        items = [_crossref(i) for i in message["items"]]
        total = message.get("total-results")
        has_more = len(items) == limit and (not isinstance(total, int) or page * limit < total)
    elif source == "openalex":
        items = [_openalex(i) for i in payload["results"]]
        total = payload.get("meta", {}).get("count")
        has_more = len(items) == limit and (not isinstance(total, int) or page * limit < total)
    else:
        items = [_semantic(i) for i in payload["data"]]
        has_more = payload.get("next") is not None
    return items, has_more


def search_source(source: str, query: str, *, limit: int = 10, page: int = 1, cache_dir: Path | None = None, timeout: float = 10.0, api_key: str | None = None) -> dict:
    """Retrieve one bounded page. Errors are distinct from a successful empty page.

    The caller must authorize query disclosure and enforce its own router and budget.
    Cache is restricted to the project workspace and may contain copyrighted abstracts.
    """
    if source not in ("crossref", "openalex", "semantic_scholar", "arxiv"):
        raise ValueError("unsupported source")
    if not isinstance(query, str) or not query.strip() or len(query) > 2000:
        raise ValueError("query must contain 1–2000 characters")
    if type(limit) is not int or not 1 <= limit <= MAX_LIMIT or type(page) is not int or not 1 <= page <= 100:
        raise ValueError("limit must be 1–50 and page must be 1–100")
    if source == "semantic_scholar" and page * limit > 1000:
        raise ValueError("Semantic Scholar relevance search is limited to 1000 results")
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or not 0 < timeout <= 30:
        raise ValueError("timeout must be greater than 0 and at most 30 seconds")
    result = {"source": source, "query": query, "retrieved_at": _now(), "items": [], "status": "error", "error": None, "page": page, "limit": limit, "has_more": False, "cached": False}
    # Hash only public request parameters; credentials never persist in cache.
    path = _cache_file(cache_dir, json.dumps(["v1", source, query, limit, page], ensure_ascii=False))
    cached = _cached(path)
    if cached is not None:
        result.update(cached, status="ok", cached=True)
        return result
    try:
        items, more = _request(source, query, limit, page, api_key, timeout)
        if len(items) > limit:
            raise ValueError("source exceeded requested page size")
        entry = {"retrieved_at": _now(), "items": items, "has_more": more}
        _save(path, entry)
        result.update(entry, status="ok")
    except HTTPError as exc:
        # Never expose URL or exception strings that may contain API keys.
        result["error"] = f"HTTP {exc.code}"
    except (URLError, TimeoutError, OSError):
        result["error"] = "network or timeout error"
    except (ValueError, KeyError, TypeError, IndexError, AttributeError, ET.ParseError):
        result["error"] = "invalid source response or missing required credentials"
    return result


def verify_crossref_doi(doi: str, *, cache_dir: Path | None = None, timeout: float = 10.0) -> dict:
    """Look up a DOI in Crossref; caller must compare title and other metadata."""
    if not isinstance(doi, str):
        raise ValueError("invalid DOI")
    doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi.strip(), flags=re.I)
    if not re.fullmatch(r"10\.\d{4,9}/[^\s?#]{1,300}", doi, flags=re.I):
        raise ValueError("invalid DOI")
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or not 0 < timeout <= 30:
        raise ValueError("timeout must be greater than 0 and at most 30 seconds")
    result = {"source": "crossref", "status": "error", "item": None, "retrieved_at": _now(), "error": None, "cached": False}
    path = _cache_file(cache_dir, "doi-v1:" + doi.lower())
    cached = _cached(path)
    if cached is not None and len(cached["items"]) == 1 and isinstance(cached["items"][0], dict):
        result.update(status="ok", item=cached["items"][0], retrieved_at=cached["retrieved_at"], cached=True)
        return result
    try:
        payload = json.loads(_fetch("https://api.crossref.org/works/" + quote(doi, safe=""), timeout))
        item = _crossref(payload["message"])
        entry = {"retrieved_at": _now(), "items": [item]}
        _save(path, entry)
        result.update(status="ok", item=item, retrieved_at=entry["retrieved_at"])
    except HTTPError as exc:
        result["error"] = f"HTTP {exc.code}"
    except (URLError, TimeoutError, OSError):
        result["error"] = "network or timeout error"
    except (ValueError, KeyError, TypeError, IndexError, AttributeError):
        result["error"] = "invalid source response"
    return result
