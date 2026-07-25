"""허용 목록 기반 tool 호출 계약과 안전한 기본 executor."""

from __future__ import annotations

import ast
import datetime as dt
import json
from dataclasses import dataclass
from typing import Any, Callable

from llmex.errors import InputError


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[[dict[str, Any]], Any]


def _calculator(args: dict[str, Any]) -> dict[str, str]:
    expression = args.get("expression")
    if not isinstance(expression, str) or len(expression) > 200:
        raise InputError("calculator.expression은 200자 이내 문자열이어야 합니다")
    allowed = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Add, ast.Sub, ast.Mult, ast.Div,
               ast.Pow, ast.Mod, ast.USub, ast.UAdd, ast.Constant)
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise InputError("calculator.expression이 올바른 산술식이 아닙니다") from exc
    if any(not isinstance(node, allowed) for node in ast.walk(tree)):
        raise InputError("calculator에는 산술식만 허용됩니다")
    try:
        value = eval(compile(tree, "<calculator>", "eval"), {"__builtins__": {}}, {})
    except (ArithmeticError, ValueError, OverflowError) as exc:
        raise InputError("calculator 계산에 실패했습니다") from exc
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise InputError("calculator 결과가 숫자가 아닙니다")
    return {"result": str(value)}


def _current_time(_: dict[str, Any]) -> dict[str, str]:
    return {"utc": dt.datetime.now(dt.UTC).isoformat()}


class ToolRegistry:
    """명시적으로 등록된 tool만 실행하는 allowlist registry."""

    def __init__(self, specs: list[ToolSpec] | None = None) -> None:
        defaults = [
            ToolSpec("calculator", "안전한 산술식을 계산합니다.", {"expression": {"type": "string"}}, _calculator),
            ToolSpec("current_time", "현재 UTC 시각을 반환합니다.", {}, _current_time),
        ]
        self._specs = {spec.name: spec for spec in (specs or defaults)}

    def schemas(self) -> list[dict[str, Any]]:
        return [{"type": "function", "function": {"name": s.name, "description": s.description, "parameters": {"type": "object", "properties": s.parameters}}} for s in self._specs.values()]

    def execute(self, name: str, arguments: str | dict[str, Any]) -> dict[str, Any]:
        spec = self._specs.get(name)
        if spec is None:
            raise InputError(f"허용되지 않은 tool입니다: {name}")
        try:
            args = json.loads(arguments) if isinstance(arguments, str) else arguments
        except json.JSONDecodeError as exc:
            raise InputError("tool arguments가 JSON이 아닙니다") from exc
        if not isinstance(args, dict):
            raise InputError("tool arguments는 object여야 합니다")
        return {"name": name, "result": spec.handler(args)}
