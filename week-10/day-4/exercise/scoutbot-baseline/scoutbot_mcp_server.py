"""Stdio entrypoint for ScoutBot's own MCP tool server (Week 10 Day 2).

The server itself lives in the package (`scoutbot.mcp_server`) so it can be imported and tested; this
thin file is just how it is *launched* as a standalone program over stdio - the way `run_mcp_server.py`
and real MCP hosts (Claude Desktop, IDEs) start it:

    python scoutbot_mcp_server.py

Or inspect it interactively:

    mcp dev scoutbot_mcp_server.py
"""
from scoutbot.mcp_server import mcp

if __name__ == "__main__":
    mcp.run()
