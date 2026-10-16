// Loaded by contraagent's pi backend (`-e`) for a launch whose plugin has a `.mcp.json`:
// pi reads MCP servers only from its own `mcp.json` files, so this registers the
// plugin's servers for the session. Each server's tools are declared to the model
// (`exposure: "direct"`, as Claude Code gives a plugin's tools) unless the entry says
// otherwise.
import { readFileSync } from "node:fs";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export default function (pi: ExtensionAPI): void {
  const file = process.env.CONTRAAGENT_PI_MCP_CONFIG;
  if (!file) return;
  const servers: Record<string, object> = JSON.parse(readFileSync(file, "utf8")).mcpServers ?? {};
  for (const [name, config] of Object.entries(servers)) {
    pi.registerMcpServer(name, { exposure: "direct", ...config } as Parameters<ExtensionAPI["registerMcpServer"]>[1]);
  }
}
