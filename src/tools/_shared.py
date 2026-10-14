"""Shared parameter types, the error type and the tool decorator for the food tools."""
import functools
from typing import Annotated, Callable

from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from server_instance import server


class FoodError(Exception):
    """A refusal with a message for the agent (unknown id, missing amount, ...)."""


def doc(text: str):
    """Field with a description for the tool schema (keeps the signatures readable)."""
    return Field(description=text)


RecipeName = Annotated[str, doc("Name of a saved recipe as recipe_list shows it, e.g. "
                                "'Overnight Oats'. Case does not matter; a unique part of the "
                                "name is enough.")]


def food_tool(func: Callable) -> Callable:
    """Register func as an MCP tool; FoodError reaches the agent as ToolError."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except FoodError as exc:
            raise ToolError(str(exc)) from exc
    server.tool()(wrapper)
    return wrapper
