# Ignition Doc MCP

**Ground your AI answers in live Inductive Automation Ignition documentation.**

![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![MCP](https://img.shields.io/badge/MCP-compatible-green)
![License: MIT](https://img.shields.io/badge/license-MIT-lightgrey)

---

## What it does

Ignition Doc MCP is a [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server that gives AI assistants like Claude direct access to the official Inductive Automation Ignition documentation. Instead of relying on training data that may be outdated or incorrect, the AI fetches real answers from live docs — eliminating hallucination on Ignition-specific topics.

Covers both the **Ignition User Manual** (always the latest version) and the **Ignition SDK Programmer's Guide**.

---

## How it works

The server queries the Typesense search backends that power [`docs.inductiveautomation.com`](https://docs.inductiveautomation.com) and [`sdk-docs.inductiveautomation.com`](https://www.sdk-docs.inductiveautomation.com) in real time. No API key required, no local doc files, no indexing step — every search goes directly to Inductive Automation's search backend and returns content that is always up to date.

The User Manual search is pinned to the `docs-default-current` tag, which automatically resolves to the latest published version — no manual version bumps needed when Ignition releases a new version.

---

## Prerequisites

- **Python 3.11 or later** — [python.org/downloads](https://www.python.org/downloads/)
- **uv** — fast Python package manager

  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

- **Claude Code** CLI — [installation guide](https://docs.anthropic.com/en/docs/claude-code/getting-started)

---

## Installation

**1. Clone the repository**

```bash
git clone https://github.com/nurnaufal321/inductiveautomation-doc-mcp.git
cd inductiveautomation-doc-mcp
```

**2. Install dependencies**

```bash
uv sync
```

**3. Register with Claude Code**

```bash
claude mcp add ignition-docs --scope user -- uv run --directory /path/to/inductiveautomation-doc-mcp python server.py
```

Replace `/path/to/inductiveautomation-doc-mcp` with the absolute path to the cloned folder.

**4. Restart Claude Code** to pick up the new MCP server. You should see `ignition-docs` listed when you run:

```bash
claude mcp list
```

---

## Available Tools

Once registered, Claude has access to three tools:

| Tool | Description |
|---|---|
| `search_ignition_docs` | Search the Ignition User Manual (latest version) by keyword. Optional: `n_results` (default 5, max 20). |
| `search_ignition_sdk` | Search the Ignition SDK Programmer's Guide by keyword. Optional: `n_results` (default 5, max 20). |
| `get_page` | Fetch the full text of a documentation page by URL. Optional: `max_chars` (default 4000, max 12000). |

---

## Usage Examples

Ask Claude questions like:

- *"How do I configure an OPC-UA connection in Ignition?"*
- *"What Vision window types are available?"*
- *"How does tag history deadband work?"*
- *"How do I create a GatewayModuleHook for my Ignition module?"*
- *"What are the core modules included in Ignition?"*

Claude will search the live docs and cite the exact page it used.

---

## Scope

### Ignition User Manual
Covers the full Ignition platform including:

- Tags, Tag Historian, and Tag Diagnostics
- Perspective and Vision modules
- Scripting and Python in Ignition
- Alarm Notification and Event Streams
- OPC-UA, SQL Bridge, Reporting
- Gateway, Designer, and Client configuration
- Transaction Groups and Database connections

### Ignition SDK Programmer's Guide
Covers module development including:

- `GatewayModuleHook`, `DesignerModuleHook`, `ClientModuleHook`
- Tag providers, drivers, and OPC server development
- Gateway network communication
- Component and style development

---

## References

- [Ignition User Manual](https://docs.inductiveautomation.com)
- [Ignition SDK Programmer's Guide](https://www.sdk-docs.inductiveautomation.com)
- [Model Context Protocol](https://modelcontextprotocol.io)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [uv — Python package manager](https://docs.astral.sh/uv/)
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code)

---

## Disclaimer

This project is not affiliated with, endorsed by, or supported by Inductive Automation. It queries Inductive Automation's publicly accessible documentation search backend for personal and developer use. Users are responsible for complying with [Inductive Automation's terms of use](https://inductiveautomation.com/legal).

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
