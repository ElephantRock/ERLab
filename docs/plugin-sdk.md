# Plugin SDK Documentation

> **Version:** 1.0.0  
> **AIV Framework:** v5.1  
> **Last Updated:** 2026-05-03

The Elephant Rock Plugin SDK lets external developers extend the research platform with custom tools, hook handlers, and pipeline integrations — without modifying core code.

---

## 1. Architecture Overview

The plugin system has three main components:

```
┌─────────────────────────────────────────────────────────┐
│                   Plugin Lifecycle                       │
│                                                         │
│  ┌──────────┐   ┌──────────────┐   ┌────────────────┐  │
│  │ Discover  │──▶│   Verify     │──▶│     Load       │  │
│  │ (scan dir)│   │ (hash check) │   │ (import module)│  │
│  └──────────┘   └──────────────┘   └───────┬────────┘  │
│                                            │            │
│                              ┌─────────────▼──────────┐ │
│                              │  Register Tools/Hooks  │ │
│                              │  (via ToolRegistry &    │ │
│                              │   HookDispatcher)       │ │
│                              └────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### Plugin Loader (`backend/pipeline/plugins/loader.py`)

The `PluginLoader` discovers Python packages in the `backend/pipeline/plugins/` directory. Each plugin is a subdirectory containing an `__init__.py` that optionally exposes:

- `register_tools(registry: ToolRegistry) -> None` — Register custom tools
- `register_agents(registry) -> None` — Register custom agents

**Discovery rules:**
- Plugin directories must contain `__init__.py`
- Directories starting with `_` are ignored
- Plugins are loaded in alphabetical order

**Verification (optional):**
When `plugin_verification_enabled=True` in settings, the loader computes a SHA-256 hash of all `.py` files in the plugin directory and validates it against an allowlist (`data/plugins/allowlist.json`). Plugins not in the allowlist are rejected.

### Tool Registry (`backend/pipeline/tools/registry.py`)

The `ToolRegistry` is the central registry for callable tools. Plugins register tools via:

```python
registry.register(
    name="my_tool",
    handler=my_async_function,
    description="What this tool does",
    trust_level="untrusted",  # or "trusted"
)
```

Tools are exposed to agents via the OpenAI function-calling schema format. The registry enforces per-tool timeouts, output size limits, and trust-based resource constraints.

### Hook Dispatcher (`backend/pipeline/autonomy/hooks.py`)

The `HookDispatcher` manages event handlers for pipeline lifecycle events. Plugins register handlers to react to pipeline state changes:

```python
hooks.register("pipeline.completed", my_completion_handler)
```

---

## 2. Plugin Manifest Schema

Each plugin should include a `plugin.json` manifest at its root. This file declares metadata, required permissions, and subscribed hooks.

### Full Schema

```json
{
  "name": "string (required)",
  "version": "semver string (required)",
  "description": "string (required)",
  "author": "string (optional)",
  "homepage": "url string (optional)",
  "license": "string (optional)",

  "hooks": ["string (optional, array of event names)"],
  "permissions": ["string (optional, array of permission strings)"],

  "config_schema": {
    "type": "object (optional)",
    "properties": { }
  },

  "trust_level": "trusted | untrusted (default: untrusted)",
  "min_platform_version": "semver string (optional)"
}
```

### Field Reference

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | ✅ | Unique plugin identifier. Lowercase, hyphens allowed. |
| `version` | string | ✅ | Semantic version (e.g., `"1.0.0"`). |
| `description` | string | ✅ | Human-readable summary. |
| `author` | string | ❌ | Plugin author or organization. |
| `homepage` | string | ❌ | URL to plugin documentation or repository. |
| `license` | string | ❌ | SPDX license identifier (e.g., `"MIT"`). |
| `hooks` | string[] | ❌ | Event names this plugin subscribes to. |
| `permissions` | string[] | ❌ | Permissions required (see Security Model). |
| `config_schema` | object | ❌ | JSON Schema for plugin configuration. |
| `trust_level` | string | ❌ | `"trusted"` or `"untrusted"`. Default: `"untrusted"`. |
| `min_platform_version` | string | ❌ | Minimum Elephant Rock version required. |

### Minimal Example

```json
{
  "name": "hello-plugin",
  "version": "1.0.0",
  "description": "A minimal example plugin for Elephant Rock",
  "author": "Example",
  "hooks": ["pipeline.completed"],
  "permissions": ["read:pipeline"]
}
```

---

## 3. Hook System

### Available Events

| Event | Payload | Trigger |
|-------|---------|---------|
| `pipeline.start` | `{run_id, domain, params}` | Pipeline begins execution |
| `pipeline.stage.complete` | `{stage, elapsed, run_id}` | After each stage finishes |
| `pipeline.complete` | `{run_id, ideas_count, gaps_count, proposals_count}` | Pipeline finishes successfully |
| `pipeline.failed` | `{run_id, stage, error}` | Pipeline encounters an unrecoverable error |
| `gap.found` | `{title, confidence, gap_type}` | A new research gap is identified |
| `idea.generated` | `{title, score}` | A new research idea is generated |
| `idea.scored` | `{title, novelty_score}` | An idea's novelty is evaluated |
| `session.start` | `{session_id}` | A research session begins |
| `session.end` | `{session_id}` | A research session ends |
| `impasse.detected` | `{round, reason}` | Ideation loop detects an impasse |
| `impasse.resolved` | `{round, strategy}` | Impasse is resolved |
| `state.transition` | `{from, to, trigger}` | Autonomous state machine transitions |

### Registering Handlers

Handlers are async functions that accept a `dict` payload:

```python
from backend.pipeline.autonomy.hooks import HookDispatcher

hooks = HookDispatcher()

async def on_pipeline_complete(payload: dict) -> None:
    run_id = payload["run_id"]
    print(f"Pipeline {run_id} completed with {payload['ideas_count']} ideas")

hooks.register("pipeline.complete", on_pipeline_complete)
```

### Handler Guarantees

- Handlers are called **sequentially** in registration order.
- If a handler raises an exception, it is logged but **does not** prevent other handlers from running.
- `dispatch_sync_safe` ensures dispatch never raises — errors are caught and logged.
- Handlers must be `async` functions. Sync functions will cause a `TypeError`.

---

## 4. API Reference

### `ToolRegistry`

#### `register(name, handler, *, description="", parameters=None, trust_level="trusted", timeout=30.0, max_output_bytes=1_000_000)`

Register a new tool. If `parameters` is not provided, they are extracted from the handler's function signature.

```python
from backend.pipeline.tools.registry import get_tool_registry

registry = get_tool_registry()

async def search_papers(query: str, max_results: int = 10) -> list[dict]:
    """Search academic databases for papers."""
    # ... implementation
    return results

registry.register(
    name="academic_search",
    handler=search_papers,
    description="Search academic databases for papers",
    trust_level="untrusted",
)
```

#### `@tool` Decorator

Shorthand for registering a function as a tool:

```python
from backend.pipeline.tools.registry import tool

@tool(description="Compute citation statistics for a paper")
async def citation_stats(paper_id: str) -> dict:
    # ... implementation
    return {"citations": 42}
```

#### `unregister(name) -> bool`

Remove a tool. Returns `True` if the tool existed.

#### `get(name) -> ToolDefinition | None`

Look up a registered tool.

#### `list_tools(enabled_only=True) -> list[ToolDefinition]`

List all (or only enabled) tools.

#### `async call(name, **kwargs) -> Any`

Invoke a tool by name. Enforces timeout, guardrails, and output limits.

### `PluginLoader`

#### `__init__(plugin_dir=None, verification_enabled=False, allowlist_path="./data/plugins/allowlist.json")`

Create a loader. Defaults to `backend/pipeline/plugins/`.

#### `discover_plugins() -> list[str]`

Return names of all discoverable plugin packages.

#### `load_plugin(name, tool_registry=None) -> bool`

Load a single plugin. Returns `True` on success.

#### `load_all(tool_registry=None) -> list[str]`

Discover and load all plugins. Returns list of successfully loaded names.

#### `loaded_plugins -> list[str]`

Read-only list of currently loaded plugin names.

### `PluginVerifier`

#### `is_allowed(plugin_name, plugin_dir) -> bool`

Check if a plugin's hash matches the allowlist. If no allowlist exists, all plugins are allowed.

#### `add_to_allowlist(plugin_name, plugin_dir) -> None`

Add a plugin's current hash to the allowlist file.

### `HookDispatcher`

#### `register(event, handler)`

Register an async handler for a named event.

#### `unregister(event, handler)`

Remove a specific handler for an event.

#### `async dispatch(event, payload=None)`

Fire all handlers for an event. Exceptions in handlers are logged but don't stop dispatch.

#### `registered_events -> list[str]`

List all events that have registered handlers.

### `PluginRegistry` (API Layer)

The API-level plugin registry (`backend/plugins/registry.py`) manages plugin metadata independently from the loader:

#### `list_plugins() -> list[dict]`

Return all registered plugins with name, version, description, and enabled status.

#### `install(name, version, description) -> dict`

Register a new plugin or update an existing one.

#### `uninstall(name) -> bool`

Remove a plugin from the registry.

---

## 5. Tutorial: Build Your First Plugin

This tutorial walks through creating `hello-plugin`, a minimal plugin that logs a message when a pipeline run completes.

### Step 1: Create the Plugin Directory

```
backend/pipeline/plugins/hello_plugin/
├── __init__.py
└── plugin.json
```

> **Note:** Plugin directory names use underscores (Python package naming) while the `name` field in `plugin.json` uses hyphens.

### Step 2: Write the Manifest

Create `plugin.json`:

```json
{
  "name": "hello-plugin",
  "version": "1.0.0",
  "description": "A minimal example plugin for Elephant Rock",
  "author": "Example",
  "hooks": ["pipeline.completed"],
  "permissions": ["read:pipeline"]
}
```

### Step 3: Implement the Plugin

Create `__init__.py`:

```python
"""hello-plugin — logs a greeting when the pipeline completes."""

import logging
from backend.pipeline.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


def register_tools(registry: ToolRegistry) -> None:
    """Register the hello_world tool."""

    async def hello_world(run_id: str = "unknown") -> str:
        """Return a greeting for the given run."""
        return f"Hello from hello-plugin! Run: {run_id}"

    registry.register(
        name="hello_world",
        handler=hello_world,
        description="Greet the pipeline runner",
        trust_level="untrusted",
    )
    logger.info("hello-plugin registered hello_world tool")
```

### Step 4: Verify Loading

```python
from backend.pipeline.plugins.loader import PluginLoader
from backend.pipeline.tools.registry import ToolRegistry

registry = ToolRegistry()
loader = PluginLoader()
loaded = loader.load_all(registry)

assert "hello_plugin" in loaded
assert registry.get("hello_world") is not None
```

### Step 5: Test the Tool

```python
import asyncio

result = asyncio.run(registry.call("hello_world", run_id="test_001"))
assert result == "Hello from hello-plugin! Run: test_001"
```

### Step 6: Add to Allowlist (Production)

For production deployments with verification enabled:

```python
from backend.pipeline.plugins.loader import PluginVerifier

verifier = PluginVerifier()
verifier.add_to_allowlist("hello_plugin", Path("backend/pipeline/plugins/hello_plugin"))
```

---

## 6. Security Model

### Trust Levels

| Level | Timeout | Max Output | Retries | Description |
|-------|---------|------------|---------|-------------|
| `trusted` | 120s | 1 MB | 2 | Core platform tools and verified plugins |
| `untrusted` | 10s | 100 KB | 0 | Third-party plugins (default) |

### Permission Strings

Plugins declare required permissions in `plugin.json`:

| Permission | Scope |
|------------|-------|
| `read:pipeline` | Read pipeline state, results, and metadata |
| `write:pipeline` | Modify pipeline configuration and parameters |
| `read:papers` | Access ingested paper data |
| `write:papers` | Add or modify papers in the knowledge base |
| `read:gaps` | Access research gap data |
| `write:gaps` | Create or modify research gaps |
| `read:ideas` | Access generated research ideas |
| `write:ideas` | Create or modify ideas |
| `execute:tools` | Call other registered tools |
| `admin:plugins` | Install, uninstall, or modify plugins |

### Plugin Verification

When `EROCK_PLUGIN_VERIFICATION_ENABLED=true`:

1. The `PluginVerifier` computes a SHA-256 hash of all `.py` files in the plugin directory.
2. The hash is compared against `data/plugins/allowlist.json`.
3. Plugins not in the allowlist or with mismatched hashes are **rejected**.

**Allowlist format** (`data/plugins/allowlist.json`):

```json
{
  "hello_plugin": "a1b2c3d4e5f6...",
  "my_other_plugin": "f6e5d4c3b2a1..."
}
```

### Sandboxing

Plugins run in the same Python process as the platform. Resource isolation is enforced through:

- **Tool timeouts**: Async execution with `asyncio.wait_for()`
- **Output truncation**: Untrusted tool output is capped at 100KB
- **Guardrails**: Optional content validation before tool execution
- **Audit logging**: All tool executions are recorded with status, duration, and errors

### Resource Limits Configuration

```python
from backend.pipeline.tools.tool_limits import UNTRUSTED_CONFIG, TRUSTED_CONFIG

# Untrusted tools (default for plugins)
UNTRUSTED_CONFIG = ToolLimitsConfig(
    timeout_seconds=10.0,
    max_output_bytes=100_000,  # 100KB
    max_retries=0,
    trust_level="untrusted",
)

# Trusted tools (core platform)
TRUSTED_CONFIG = ToolLimitsConfig(
    timeout_seconds=120.0,
    max_output_bytes=1_000_000,  # 1MB
    max_retries=2,
    trust_level="trusted",
)
```

### Audit Trail

Every tool execution is recorded in the `ToolAuditLog`:

```python
@dataclass
class ToolExecutionEvent:
    tool_name: str
    status: str         # "success", "timeout", "error", "blocked"
    duration_ms: float
    input_hash: str
    output_hash: str
    run_id: str | None
    timestamp: str
    error: str | None
```

Enable persistent audit logging:

```python
from backend.pipeline.tools.tool_limits import ToolAuditLog

audit = ToolAuditLog(persist_path="./data/audit/tool_events.jsonl")
registry = ToolRegistry(audit_log=audit)
```

---

## Appendix: Plugin API Endpoints

The platform exposes REST API endpoints for plugin management:

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/plugins/` | List all registered plugins |
| `POST` | `/plugins/install` | Install or update a plugin |

**Install request body:**

```json
{
  "name": "my-plugin",
  "version": "1.0.0",
  "description": "My custom plugin"
}
```
