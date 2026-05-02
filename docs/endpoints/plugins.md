# Plugins

List and install plugins for the extensible plugin architecture.

**Base path:** `/api/v1/plugins`

---

## List Available Plugins

`GET /api/v1/plugins/`

Return all registered plugins with name, version, description, and enabled status.

### Example Request

```bash
curl -H "X-API-Key: your-key" http://localhost:8000/api/v1/plugins/
```

### Example Response

```json
{
  "plugins": [
    {
      "name": "literature-enricher",
      "version": "1.0.0",
      "description": "Enriches ideas with additional literature references",
      "enabled": true
    },
    {
      "name": "slack-notifier",
      "version": "0.5.0",
      "description": "Sends pipeline notifications to Slack",
      "enabled": false
    }
  ],
  "total": 2
}
```

---

## Install a Plugin

`POST /api/v1/plugins/install`

Register a new plugin or update an existing one.

### Request Body

| Field | Type | Description |
|:------|:-----|:------------|
| `name` | string | Plugin name (unique identifier) |
| `version` | string | Semantic version string |
| `description` | string | Plugin description |

### Example Request

```bash
curl -X POST http://localhost:8000/api/v1/plugins/install \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"name": "custom-scorer", "version": "1.0.0", "description": "Custom scoring algorithm for domain-specific evaluation"}'
```

### Example Response

```json
{
  "name": "custom-scorer",
  "version": "1.0.0",
  "description": "Custom scoring algorithm for domain-specific evaluation",
  "enabled": true
}
```
