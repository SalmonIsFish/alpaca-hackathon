# Alpaca CLI over MCP for execution transport

The agent must trade unattended every 60 minutes 09:30–16:00 ET via systemd. Alpaca's MCP is documented as interactive/session-bound for Claude Code, while the Alpaca CLI (`alpaca doctor`, `data option chain`, `order submit`) is explicitly recommended for cron/automation in `github.com/alpacahq/alpaca-skills`. We chose CLI (Go binary locally, Python wrapper `alpaca_cli.py` on VPS) over MCP — per the official FAQ, "You can use Alpaca's MCP or CLI" and CLI satisfies the `MCP server or CLI` requirement, with minimal `urllib`+`subprocess` surface.
