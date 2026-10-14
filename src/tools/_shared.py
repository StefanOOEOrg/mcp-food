"""Shared parameter types, the error type and the tool decorator for the food tools."""
import functools
from typing import Annotated, Callable

from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BeforeValidator, Field, WithJsonSchema

from server_instance import server


class FoodError(Exception):
    """A refusal with a message for the agent (unknown id, missing amount, ...)."""


def doc(text: str):
    """Field with a description for the tool schema (keeps the signatures readable)."""
    return Field(description=text)


def _number(value):
    """'1', '1,5' or ' 70 ' → a number. Some models send the numbers inside list items as text,
    and Hermes only converts top-level arguments before it validates them."""
    if isinstance(value, str):
        text = value.strip().replace(",", ".")
        try:
            return float(text) if "." in text else int(text)
        except ValueError as exc:
            raise ValueError(f"'{value}' is not a number") from exc
    return value


# A number that may also arrive as text (schema: number or numeric string).
AS_NUMBER = BeforeValidator(_number)
NUMBER_SCHEMA = WithJsonSchema({"anyOf": [{"type": "number"}, {"type": "string"}]})
OPTIONAL_NUMBER_SCHEMA = WithJsonSchema(
    {"anyOf": [{"type": "number"}, {"type": "string"}, {"type": "null"}]})

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
