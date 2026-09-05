"""Ignition Documentation MCP Server.

Searches and retrieves Inductive Automation Ignition documentation via the
Typesense backends powering docs.inductiveautomation.com and
sdk-docs.inductiveautomation.com. Always uses the latest published version.
"""

import re
from typing import Annotated

import httpx
from bs4 import BeautifulSoup
from mcp.server.mcpserver.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

# ── Typesense endpoints ────────────────────────────────────────────────────────

_DOCS_HOST = "https://search-docs.inductiveautomation.com"
_DOCS_KEY = "1e3c83e4-5ffe-4874-81a9-52e3b9c4e770"
_DOCS_COLLECTION = "ia_um"
# "current" tag always resolves to the latest published version (8.3 as of 2025)
_DOCS_TAG = "docs-default-current"

_SDK_HOST = "https://search.sdk-docs.inductiveautomation.com"
_SDK_KEY = "l2pfBZvAqpsJ76aYI2uo91Sy9efBIYdV"
_SDK_COLLECTION = "ia_um"

_QUERY_BY = "hierarchy.lvl1,hierarchy.lvl2,hierarchy.lvl3,hierarchy.lvl5,content"
_SORT_BY = "item_priority:desc,_text_match:desc"

# ── App ────────────────────────────────────────────────────────────────────────

# Every tool here reads public documentation over the network: no side effects,
# and results depend on what Inductive Automation currently publishes.
READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=True)

mcp = MCPServer(
    "ignition-doc-mcp",
    instructions=(
        "Answers questions about Inductive Automation Ignition from the official "
        "documentation, always the latest published version. Use "
        "search_ignition_docs for using and configuring Ignition, and "
        "search_ignition_sdk for writing Java modules against the SDK, then "
        "get_page to read any promising result in full — search returns excerpts "
        "that usually omit the actual steps. Results are tagged with the doc "
        "version from their URL and can span 7.9 through 8.3, so check it before "
        "relying on a page. Prefer these tools over recalled knowledge: Ignition "
        "changes between versions and details drift. All tools are read-only and "
        "need no credentials."
    ),
)
_client: httpx.AsyncClient | None = None


def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
    return _client


# ── Helpers ────────────────────────────────────────────────────────────────────

def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
        tag.decompose()
    for tag in soup.select(
        ".theme-doc-sidebar-container, .navbar, .footer, "
        ".pagination-nav, .breadcrumbs, .table-of-contents"
    ):
        tag.decompose()
    text = soup.get_text(separator=" ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


async def _typesense_search(
    host: str,
    api_key: str,
    collection: str,
    query: str,
    n: int,
    filter_by: str = "",
) -> list[dict]:
    params: dict = {
        "q": query,
        "query_by": _QUERY_BY,
        "sort_by": _SORT_BY,
        "per_page": min(n * 4, 100),  # over-fetch for page-level dedup
    }
    if filter_by:
        params["filter_by"] = filter_by

    resp = await get_client().get(
        f"{host}/collections/{collection}/documents/search",
        params=params,
        headers={"X-TYPESENSE-API-KEY": api_key},
    )
    resp.raise_for_status()
    return resp.json().get("hits", [])


_VERSION_IN_URL = re.compile(r"/docs/(\d+\.\d+)/")


def _version_of(url: str) -> str:
    """Ignition puts the doc version in the URL path, e.g. /docs/8.1/..."""
    m = _VERSION_IN_URL.search(url)
    return m.group(1) if m else "?"


def _format_hits(hits: list[dict], n: int) -> str:
    lines: list[str] = []
    seen: set[str] = set()
    count = 0
    for item in hits:
        if count >= n:
            break
        doc = item["document"]
        page_url = doc.get("url_without_anchor", "")
        if page_url in seen:
            continue
        seen.add(page_url)

        h = doc.get("hierarchy", {})
        parts = [h.get(f"lvl{i}") for i in range(4) if h.get(f"lvl{i}")]
        title = " > ".join(parts) if parts else page_url
        snippet = doc.get("content", "")[:200].strip()

        lines.append(f"{count + 1}. {title}  [v{_version_of(page_url)}]")
        lines.append(f"   {page_url}")
        if snippet:
            lines.append(f"   {snippet}")
        count += 1

    return "\n".join(lines)


# ── Tools ──────────────────────────────────────────────────────────────────────

@mcp.tool(
    description=(
        "Search the Ignition User Manual and return page titles, URLs and "
        "matching excerpts.\n\n"
        "Use this for how Ignition is used and configured: tags and the tag "
        "historian, OPC-UA connections, Perspective and Vision, gateway and "
        "designer settings, Jython scripting, alarms, security, and installation. "
        "Use search_ignition_sdk instead when the question is about writing a Java "
        "module against Ignition's API. Reach for this before answering from "
        "memory — Ignition's behaviour and UI shift between versions.\n\n"
        "Read-only; no side effects; no credentials needed. Results carry a "
        "[v8.1]-style version tag read from the page URL: the upstream index "
        "labels some older pages as current, so results can mix 7.9, 8.1 and 8.3 "
        "and you should check the version before relying on one. Excerpts are "
        "short and often omit the steps themselves — follow up with get_page on "
        "the URL that looks right."
    ),
    annotations=READ_ONLY,
)
async def search_ignition_docs(
    query: Annotated[str, Field(description=(
        "Search terms describing the task or setting, e.g. 'configure OPC-UA "
        "connection' or 'tag historian deadband'. Plain keywords work better "
        "than a full question."
    ))],
    n_results: Annotated[int, Field(
        default=5, ge=1, le=20,
        description="Number of unique pages to return, 1-20.",
    )] = 5,
) -> str:
    n = min(n_results, 20)
    hits = await _typesense_search(
        _DOCS_HOST, _DOCS_KEY, _DOCS_COLLECTION,
        query, n,
        filter_by=f"docusaurus_tag:={_DOCS_TAG}",
    )
    result = _format_hits(hits, n)
    if not result:
        return f"No results found for: {query}"
    return (
        "Ignition User Manual. Each result is tagged with the doc version taken "
        "from its URL; Inductive Automation's index labels some older pages as "
        "current, so check the version before relying on a result.\n\n"
        f"{result}"
    )


@mcp.tool(
    description=(
        "Search the Ignition SDK Programmer's Guide and return page titles, URLs "
        "and matching excerpts.\n\n"
        "Use this when writing or debugging an Ignition module in Java: the hook "
        "classes (GatewayModuleHook, DesignerModuleHook, ClientModuleHook, "
        "AbstractGatewayModuleHook), module lifecycle and .modl packaging, custom "
        "tag providers, RPC between scopes, and Perspective or Vision component "
        "development. Use search_ignition_docs instead for configuring or "
        "operating Ignition itself; that is the far more common need, so prefer it "
        "unless the question is clearly about module code.\n\n"
        "Read-only; no side effects; no credentials needed. Covers only the SDK "
        "guide, not the user manual or Javadoc. Follow up with get_page to read a "
        "result in full."
    ),
    annotations=READ_ONLY,
)
async def search_ignition_sdk(
    query: Annotated[str, Field(description=(
        "Search terms, ideally naming an SDK class or concept, e.g. "
        "'GatewayModuleHook startup' or 'tag provider SDK'."
    ))],
    n_results: Annotated[int, Field(
        default=5, ge=1, le=20,
        description="Number of unique pages to return, 1-20.",
    )] = 5,
) -> str:
    n = min(n_results, 20)
    hits = await _typesense_search(
        _SDK_HOST, _SDK_KEY, _SDK_COLLECTION,
        query, n,
    )
    result = _format_hits(hits, n)
    if not result:
        return f"No results found for: {query}"
    return f"Ignition SDK Programmer's Guide\n\n{result}"


@mcp.tool(
    description=(
        "Fetch one Ignition documentation page and return its text.\n\n"
        "Use this after either search tool, on any result whose excerpt looks "
        "relevant — excerpts are a couple of lines and routinely omit the actual "
        "configuration steps or code, so do not answer from a search result alone. "
        "Also accepts any docs.inductiveautomation.com or "
        "sdk-docs.inductiveautomation.com URL the user pastes.\n\n"
        "Read-only; no side effects; no credentials needed. Any anchor is stripped "
        "so the whole page is returned, not just one section. Output is the URL "
        "followed by the page text, truncated at max_chars with a marker when cut."
    ),
    annotations=READ_ONLY,
)
async def get_page(
    url: Annotated[str, Field(description=(
        "Full page URL, normally copied from a search result, e.g. "
        "'https://docs.inductiveautomation.com/docs/8.3/platform/tags/tag-historian'. "
        "Any '#section' anchor is ignored."
    ))],
    max_chars: Annotated[int, Field(
        default=4000, ge=500, le=12000,
        description=(
            "Maximum characters of page text to return, 500-12000. Raise it if "
            "the output ends in a truncation marker."
        ),
    )] = 4000,
) -> str:
    url = url.split("#")[0]  # strip anchor — fetch the full page
    max_chars = min(max_chars, 12000)

    resp = await get_client().get(url, headers={"Accept": "text/html"})
    resp.raise_for_status()

    content = html_to_text(resp.text)
    truncated = len(content) > max_chars
    content = content[:max_chars]
    suffix = "\n\n[truncated — increase max_chars for more]" if truncated else ""
    return f"{url}\n\n{content}{suffix}"


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
