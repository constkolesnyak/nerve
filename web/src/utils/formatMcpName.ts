/**
 * Format MCP server name for display.
 *
 * Claude Code plugin servers use names like "plugin_Notion_notion" or
 * "plugin_slack_slack".  This extracts the plugin name portion and
 * capitalises it for a cleaner UI display.
 *
 * Examples:
 *   "plugin_Notion_notion" → "Notion"
 *   "plugin_slack_slack"   → "Slack"
 *   "grafana"              → "grafana"
 *   "nerve"                → "nerve"
 */
export function formatMcpName(raw: string): string {
  if (!raw.startsWith('plugin_')) return raw;

  const rest = raw.slice('plugin_'.length); // "Notion_notion" or "slack_slack"
  const lastUnderscore = rest.lastIndexOf('_');
  const name = lastUnderscore > 0 ? rest.slice(0, lastUnderscore) : rest;
  // Capitalise first letter if all-lowercase
  return name.charAt(0).toUpperCase() + name.slice(1);
}
