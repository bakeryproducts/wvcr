import os
from pathlib import Path

from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

from loguru import logger


vault_path = os.getenv("VAULT_MCP_SERVER_PATH")
if not vault_path:
    raise ValueError(
        "VAULT_MCP_SERVER_PATH environment variable is not set. "
        "Please set it to the path of your MCP server script."
    )

VAULT_MCP_SERVER = Path(vault_path).expanduser()
if not VAULT_MCP_SERVER.exists():
    raise FileNotFoundError(
        f"MCP server not found at {VAULT_MCP_SERVER}. "
        "Please check VAULT_MCP_SERVER_PATH is correct."
    )

logger.warning(f"VAULT MCP {VAULT_MCP_SERVER}")

memory_toolset = McpToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command="python",
                    args=[str(VAULT_MCP_SERVER)],
                )
            ),
        )
