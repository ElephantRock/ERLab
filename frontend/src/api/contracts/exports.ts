/**
 * F1.7a — Plugin install endpoint contract.
 *
 * Migrates the one remaining apiFetchUnchecked caller in src/api/exports.ts
 * (installPlugin) to JsonContract + a runtime decoder. The list endpoint
 * (listPlugins) was already migrated in F1.3a. The install decoder validates
 * the same material fields as the list plugin decoder (name, version,
 * description, enabled) so a single Plugin shape flows through both paths.
 *
 * Backend source (backend/api/routes/plugins.py):
 *   POST /plugins/install → Plugin (from registry.install → asdict(Plugin))
 *
 * The Plugin dataclass also carries an enabled flag (default True) and a
 * metadata dict — both material for the plugin UI.
 */

import type { Plugin } from "@/api/exports";
import {
  decodeBoolean,
  decodeObject,
  decodeString,
  type JsonContract,
} from "./common";

// Plugin — all four declared-typed fields validated. metadata is
// Record<string, unknown>; decodeObject's forward-compat spread preserves it
// without per-key validation (opaque to this layer).
const pluginDecoder = decodeObject<Plugin>({
  required: {
    name: decodeString,
    version: decodeString,
    description: decodeString,
    enabled: decodeBoolean,
  },
});

export const installPluginContract: JsonContract<Plugin> = {
  id: "plugins.installPlugin",
  method: "POST",
  pathPattern: "/plugins/install",
  responseKind: "json",
  decoder: pluginDecoder,
};
