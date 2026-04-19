"""Tool registry — tools decorate with @tool, get schema-introspected, dispatched by name."""
from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, get_type_hints

from rbac import TOOL_MINIMUM_ROLE


@dataclass
class Tool:
    name: str
    fn: Callable[..., Awaitable[Any]]
    description: str
    input_schema: dict = field(default_factory=dict)


_REGISTRY: dict[str, Tool] = {}


def _py_type_to_json(t: Any) -> dict:
    """Best-effort map Python annotations to JSON Schema."""
    origin = getattr(t, "__origin__", None)
    args = getattr(t, "__args__", ())

    # Optional[X] / X | None
    if origin in (None,):
        if t is str:
            return {"type": "string"}
        if t is int:
            return {"type": "integer"}
        if t is float:
            return {"type": "number"}
        if t is bool:
            return {"type": "boolean"}
        if t is list:
            return {"type": "array"}
        if t is dict:
            return {"type": "object"}
    if origin is list:
        inner = _py_type_to_json(args[0]) if args else {"type": "string"}
        return {"type": "array", "items": inner}
    if origin is dict:
        return {"type": "object"}
    # Handle Union / Optional by picking the first non-None type
    if origin is not None and args:
        non_none = [a for a in args if a is not type(None)]
        if non_none:
            return _py_type_to_json(non_none[0])
    return {"type": "string"}


def tool(name: str | None = None):
    """Register an async function as a callable tool."""

    def decorator(fn: Callable[..., Awaitable[Any]]):
        tool_name = name or fn.__name__
        sig = inspect.signature(fn)
        hints = get_type_hints(fn)

        properties: dict[str, Any] = {}
        required: list[str] = []
        for pname, param in sig.parameters.items():
            if pname in ("_ctx", "role"):
                continue
            ann = hints.get(pname, str)
            schema = _py_type_to_json(ann)
            properties[pname] = schema
            if param.default is inspect._empty:
                required.append(pname)

        input_schema = {
            "type": "object",
            "properties": properties,
        }
        if required:
            input_schema["required"] = required

        doc = (fn.__doc__ or "").strip().split("\n\n")[0]
        _REGISTRY[tool_name] = Tool(
            name=tool_name, fn=fn, description=doc, input_schema=input_schema
        )
        return fn

    return decorator


def list_tools() -> list[dict]:
    return [
        {
            "name": t.name,
            "description": t.description,
            "input_schema": t.input_schema,
            "min_role": TOOL_MINIMUM_ROLE.get(t.name, "viewer"),
            "server_name": "ollychat-grafana",
        }
        for t in _REGISTRY.values()
    ]


def get_tool(name: str) -> Tool | None:
    return _REGISTRY.get(name)


def tool_count() -> int:
    return len(_REGISTRY)
