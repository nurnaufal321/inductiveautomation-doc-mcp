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

mcp = MCPServer("ignition-doc-mcp")
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

        lines.append(f"{count + 1}. {title}")
        lines.append(f"   {page_url}")
        if snippet:
            lines.append(f"   {snippet}")
        count += 1

    return "\n".join(lines)


# ── Tools ──────────────────────────────────────────────────────────────────────

@mcp.tool()
async def search_ignition_docs(
    query: Annotated[str, "Search terms, e.g. 'configure OPC-UA connection' or 'tag historian deadband'"],
    n_results: Annotated[int, "Number of unique pages to return (default 5, max 20)"] = 5,
) -> str:
    """Search the Ignition User Manual (always the latest version).

    Use this for questions about Ignition configuration, tags, scripting,
    modules, gateways, designers, and general product usage.
    """
    n = min(n_results, 20)
    hits = await _typesense_search(
        _DOCS_HOST, _DOCS_KEY, _DOCS_COLLECTION,
        query, n,
        filter_by=f"docusaurus_tag:={_DOCS_TAG}",
    )
    result = _format_hits(hits, n)
    if not result:
        return f"No results found for: {query}"
    return f"Ignition User Manual — latest (8.3)\n\n{result}"


@mcp.tool()
async def search_ignition_sdk(
    query: Annotated[str, "Search terms, e.g. 'GatewayModuleHook startup' or 'tag provider SDK'"],
    n_results: Annotated[int, "Number of unique pages to return (default 5, max 20)"] = 5,
) -> str:
    """Search the Ignition SDK Programmer's Guide.

    Use this for questions about building Ignition modules: GatewayModuleHook,
    DesignerModuleHook, ClientModuleHook, AbstractGatewayModuleHook, and the
    Ignition module API.
    """
    n = min(n_results, 20)
    hits = await _typesense_search(
        _SDK_HOST, _SDK_KEY, _SDK_COLLECTION,
        query, n,
    )
    result = _format_hits(hits, n)
    if not result:
        return f"No results found for: {query}"
    return f"Ignition SDK Programmer's Guide\n\n{result}"


@mcp.tool()
async def get_page(
    url: Annotated[str, "Full page URL from search results"],
    max_chars: Annotated[int, "Max characters to return (default 4000, max 12000)"] = 4000,
) -> str:
    """Fetch the text content of an Ignition documentation page by URL.

    Use URLs returned by search_ignition_docs or search_ignition_sdk.
    """
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
