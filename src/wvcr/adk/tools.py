import os
from pathlib import Path

from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters


VAULT_MCP_SERVER = Path(os.getenv("VAULT_MCP_SERVER_PATH")).expanduser()
memory_toolset = McpToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command="python",
                    args=[str(VAULT_MCP_SERVER)],
                )
            ),
        )