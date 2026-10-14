"""Composition root: wires up the MCP server and registers all tools."""
import logging
from server_instance import server
import config
import tools

logging.basicConfig(
    level=config.LOG_LEVEL, format="%(asctime)s - %(levelname)s - %(message)s", force=True
)
log = logging.getLogger(__name__)
log.info("MCP server '%s' ready, loaded tool modules: %s", server.name, tools.__all__)
