"""Shared utilities for FastMCP servers in mcp_servers/.

Centralizes the HTTP-GET boilerplate that was duplicated across 6 servers
(alphafold, chembl, pubchem, pubmed, stringdb, uniprot) and provides a
standard error-dict shape + a NullHandler-default logger so debug output
does not pollute the MCP stdio transport.

Compat: return shapes match the previous per-server implementations
(parsed dict on success, ``{"error": ..., "detail": ...}`` on failure for
``http_get``; ``str``/``bytes`` or ``None`` for the text/bytes helpers).
"""

from __future__ import annotations

import json
import logging
import socket
import urllib.error
import urllib.request
from typing import Optional

DEFAULT_TIMEOUT = 30
DEFAULT_USER_AGENT = "AmberMD-Agent/1.0"


def get_logger(name: str) -> logging.Logger:
    """Return a logger with a NullHandler so MCP stdio is not corrupted by stray output."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.addHandler(logging.NullHandler())
    return logger


def error_response(code: str, detail: str, **ctx) -> dict:
    """Standard error shape used by all servers.

    Keeps the legacy ``"error"`` key so existing callers using
    ``result.get("error")`` continue to work, but the value is now a stable
    short code (``http_error``, ``timeout``, ``parse_error``, ...) and the
    free-text message moves to ``"detail"``.
    """
    out = {"error": code, "detail": detail}
    out.update(ctx)
    return out


def not_found_response(query: str, entity: str) -> dict:
    """Standard not-found shape for search-style tools."""
    return {"query": query, "entity": entity, "n_results": 0, "results": []}


def _classify_exception(exc: BaseException, url: str) -> dict:
    """Map a transport/parse exception to a stable error code."""
    if isinstance(exc, urllib.error.HTTPError):
        if exc.code == 404:
            return error_response("not_found", f"Not found (404): {url}", http_code=404)
        return error_response("http_error", f"HTTP {exc.code}: {exc.reason}", http_code=exc.code)
    if isinstance(exc, urllib.error.URLError):
        if isinstance(exc.reason, socket.timeout):
            return error_response("timeout", f"Request timed out: {url}")
        return error_response("url_error", str(exc.reason), url=url)
    if isinstance(exc, socket.timeout):
        return error_response("timeout", f"Request timed out: {url}")
    if isinstance(exc, json.JSONDecodeError):
        return error_response("parse_error", f"JSON decode failed: {exc.msg}")
    return error_response("unknown_error", f"{type(exc).__name__}: {exc}")


def _build_request(url: str, accept: Optional[str]) -> urllib.request.Request:
    headers = {"User-Agent": DEFAULT_USER_AGENT}
    if accept:
        headers["Accept"] = accept
    return urllib.request.Request(url, headers=headers)


def http_get(url: str,
             accept: str = "application/json",
             timeout: int = DEFAULT_TIMEOUT,
             retries: int = 0,
             return_text_on_parse_fail: bool = False) -> dict:
    """HTTP GET that always returns a dict.

    On success: parsed JSON (if ``accept`` is JSON) or ``{"raw_text": ...}``
    when ``return_text_on_parse_fail=True`` and the body is not valid JSON.

    On failure: ``error_response(...)`` dict. Retries only on
    timeout / URLError / 5xx — not on 4xx.
    """
    req = _build_request(url, accept)
    last_error: Optional[dict] = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode()
        except (urllib.error.HTTPError, urllib.error.URLError,
                socket.timeout) as exc:
            last_error = _classify_exception(exc, url)
            code = last_error.get("error")
            # Stop on 4xx (other than transient 408/429); retry on timeout / url_error / 5xx
            if code == "http_error" and last_error.get("http_code", 0) < 500:
                break
            if code == "not_found":
                break
            continue
        except Exception as exc:  # noqa: BLE001 — last-resort catch-all
            last_error = _classify_exception(exc, url)
            break

        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            if return_text_on_parse_fail:
                return {"raw_text": body}
            last_error = _classify_exception(exc, url)
            break
    return last_error or error_response("unknown_error", "No response and no exception")


def http_get_text(url: str,
                  timeout: int = DEFAULT_TIMEOUT,
                  retries: int = 0) -> Optional[str]:
    """HTTP GET returning the decoded body, or ``None`` on any failure.

    Matches the legacy ``_http_get_text``/``_http_get_raw`` behavior used by
    uniprot, alphafold, pubchem for SDF/PDB/text downloads.
    """
    req = _build_request(url, accept=None)
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode()
        except (urllib.error.HTTPError, urllib.error.URLError, socket.timeout):
            if attempt == retries:
                return None
            continue
        except Exception:  # noqa: BLE001
            return None
    return None


def http_get_bytes(url: str,
                   timeout: int = DEFAULT_TIMEOUT,
                   retries: int = 0) -> Optional[bytes]:
    """HTTP GET returning raw bytes, or ``None`` on failure."""
    req = _build_request(url, accept=None)
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except (urllib.error.HTTPError, urllib.error.URLError, socket.timeout):
            if attempt == retries:
                return None
            continue
        except Exception:  # noqa: BLE001
            return None
    return None
