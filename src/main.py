"""This module serves as the entry point for the food MCP server."""
import db
from mcp_server import server

if __name__ == "__main__":
    db.init_schema()
    server.run()
