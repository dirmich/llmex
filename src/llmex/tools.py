"""허용 목록 기반 tool 호출 계약과 안전한 기본 executor."""

from __future__ import annotations

import ast
import datetime as dt
import json
import os
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

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


def _run_readonly(command: list[str], timeout: float = 3.0) -> str:
    """고정된 읽기 전용 argv만 timeout과 함께 실행한다."""
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=timeout, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise InputError("허용된 Linux 명령 실행에 실패했거나 timeout이 발생했습니다") from exc
    if completed.returncode != 0:
        raise InputError(f"Linux 명령이 실패했습니다: {completed.stderr.strip()[:200]}")
    return completed.stdout.strip()[:4000]


def _linux_system_info(_: dict[str, Any]) -> dict[str, str]:
    return {
        "uname": _run_readonly(["uname", "-a"]),
        "memory": _run_readonly(["free", "-h"]),
        "disk": _run_readonly(["df", "-h", "/"]),
    }


class GpioController:
    """gpiozero를 선택적으로 사용하며 기본값은 하드웨어를 건드리지 않는다."""

    def __init__(self, *, dry_run: bool | None = None) -> None:
        self.dry_run = (
            dry_run if dry_run is not None else os.getenv("LLMEX_GPIO_DRY_RUN", "1") != "0"
        )
        self._pins: dict[int, Any] = {}

    def _pin(self, pin: int) -> Any:
        if not isinstance(pin, int) or not 0 <= pin <= 40:
            raise InputError("GPIO pin은 BCM 기준 0~40 정수여야 합니다")
        if self.dry_run:
            return None
        try:
            from gpiozero import DigitalOutputDevice
        except ImportError as exc:
            raise InputError("실제 GPIO에는 gpiozero 설치가 필요합니다") from exc
        if pin not in self._pins:
            self._pins[pin] = DigitalOutputDevice(pin)
        return self._pins[pin]

    def write(self, args: dict[str, Any]) -> dict[str, Any]:
        pin, value = args.get("pin"), args.get("value")
        if not isinstance(pin, int) or not isinstance(value, bool):
            raise InputError("gpio_write는 pin 정수와 value boolean이 필요합니다")
        device = self._pin(pin)
        if device is not None:
            device.on() if value else device.off()
        return {"pin": pin, "value": value, "dry_run": self.dry_run}

    def read(self, args: dict[str, Any]) -> dict[str, Any]:
        pin = args.get("pin")
        if not isinstance(pin, int):
            raise InputError("gpio_read는 pin 정수가 필요합니다")
        device = self._pin(pin)
        value = False if device is None else bool(device.value)
        return {"pin": pin, "value": value, "dry_run": self.dry_run}


class ToolRegistry:
    """명시적으로 등록된 tool만 실행하는 allowlist registry."""

    def __init__(self, specs: list[ToolSpec] | None = None) -> None:
        gpio = GpioController()
        defaults = [
            ToolSpec(
                "calculator",
                "안전한 산술식을 계산합니다.",
                {"expression": {"type": "string"}},
                _calculator,
            ),
            ToolSpec("current_time", "현재 UTC 시각을 반환합니다.", {}, _current_time),
            ToolSpec(
                "linux_system_info",
                "읽기 전용 Linux 시스템 정보를 조회합니다.",
                {},
                _linux_system_info,
            ),
            ToolSpec(
                "gpio_write", "Raspberry Pi BCM GPIO 출력값을 설정합니다.",
                {"pin": {"type": "integer"}, "value": {"type": "boolean"}}, gpio.write
            ),
            ToolSpec(
                "gpio_read", "Raspberry Pi BCM GPIO 입력값을 읽습니다.",
                {"pin": {"type": "integer"}}, gpio.read
            ),
        ]
        self._specs = {spec.name: spec for spec in (specs or defaults)}

    def schemas(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": s.name,
                    "description": s.description,
                    "parameters": {"type": "object", "properties": s.parameters},
                },
            }
            for s in self._specs.values()
        ]

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
