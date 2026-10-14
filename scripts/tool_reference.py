"""Regenerate the tool reference in README.md from the server's tool schemas.

Run from the repo root: venv/bin/python scripts/tool_reference.py
The section between the markers <!-- tool-reference:start --> and <!-- tool-reference:end -->
is replaced; tools are grouped by their module in src/tools/.
"""
import asyncio
import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from mcp import Client  # noqa: E402  pylint: disable=wrong-import-position

import mcp_server  # noqa: E402  pylint: disable=wrong-import-position
from tools import __all__ as MODULES  # noqa: E402  pylint: disable=wrong-import-position

START, END = "<!-- tool-reference:start -->", "<!-- tool-reference:end -->"
TYPES = {"string": "text", "integer": "number", "number": "number", "boolean": "yes/no",
         "array": "list", "object": "object"}


def _type(prop: dict) -> str:
    for option in prop.get("anyOf", [prop]):
        if "enum" in option:
            return " / ".join(f"`{v}`" for v in option["enum"])
        if option.get("type") != "null":
            return TYPES[option["type"]]
    return "?"


def _tool_section(tool) -> list[str]:
    lines = [f"#### `{tool.name}`", "", " ".join(inspect.cleandoc(tool.description).split()), ""]
    props = tool.input_schema.get("properties", {})
    if props:
        required = set(tool.input_schema.get("required", []))
        lines += ["| Parameter | Type | Required | Description |", "|---|---|---|---|"]
        for name, prop in props.items():
            default = repr(prop.get("default")).replace("None", "none")
            needed = "yes" if name in required else f"no (default `{default}`)"
            lines.append(f"| `{name}` | {_type(prop)} | {needed} | {prop.get('description', '')} |")
        lines.append("")
    return lines


async def reference() -> str:
    """Markdown for all tools, grouped by tool module in reading order of tools.__all__."""
    async with Client(mcp_server.server) as client:
        tools = {t.name: t for t in (await client.list_tools()).tools}
    lines = []
    for module in MODULES:
        names = [n for n, f in vars(sys.modules[f"tools.{module}"]).items()
                 if n in tools and callable(f)]
        lines += [f"### {module.capitalize()}", ""]
        for name in names:
            lines += _tool_section(tools.pop(name))
    assert not tools, f"tools without module: {sorted(tools)}"
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    """Replace the marked section of README.md."""
    readme = ROOT / "README.md"
    text = readme.read_text(encoding="utf-8")
    head, rest = text.split(START, 1)
    _, tail = rest.split(END, 1)
    readme.write_text(f"{head}{START}\n\n{asyncio.run(reference())}\n{END}{tail}", encoding="utf-8")


if __name__ == "__main__":
    main()
