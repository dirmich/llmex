"""비밀정보를 artifact에 남기지 않는 OpenAI 호환 HTTP client."""

import hmac
import json
import os
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from time import time
from typing import Any, cast

from llmex.config import DistillationConfig
from llmex.errors import InputError, IntegrityError


@dataclass(frozen=True)
class HttpFailure(Exception):
    status: int | None
    retry_after: float | None = None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        del req, fp, code, msg, headers, newurl
        return None


def _headers(config: DistillationConfig) -> dict[str, str]:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if config.api_key_env:
        secret = os.environ.get(config.api_key_env)
        if not secret:
            raise InputError(f"API key 환경 변수가 설정되지 않았습니다: {config.api_key_env}")
        try:
            secret.encode("latin-1")
        except UnicodeEncodeError as exc:
            raise InputError("API key는 HTTP header로 표현할 수 없는 문자를 포함합니다") from exc
        headers["Authorization"] = f"Bearer {secret}"
    return headers


def _constant_time_contains(value: str, candidate: str) -> bool:
    encoded = value.encode("utf-8")
    needle = candidate.encode("utf-8")
    if not needle or len(needle) > len(encoded):
        return False
    return any(
        hmac.compare_digest(encoded[index : index + len(needle)], needle)
        for index in range(len(encoded) - len(needle) + 1)
    )


def response_contains_secret(config: DistillationConfig, response: str) -> bool:
    """설정된 자격증명의 exact/Bearer echo를 값 노출 없이 검사한다."""

    if config.api_key_env is None:
        return False
    credential = os.environ.get(config.api_key_env)
    if not credential:
        return False
    return _constant_time_contains(response, credential) or _constant_time_contains(
        response, f"Bearer {credential}"
    )


def _retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            return max(0.0, parsedate_to_datetime(value).timestamp() - time())
        except (TypeError, ValueError, OverflowError):
            return None


def _open(request: urllib.request.Request, timeout: float, max_response_bytes: int) -> bytes:
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
        with opener.open(request, timeout=timeout) as response:
            length_header = response.headers.get("Content-Length")
            if length_header is not None:
                try:
                    content_length = int(length_header)
                except ValueError as exc:
                    raise IntegrityError("invalid_content_length") from exc
                if content_length < 0 or content_length > max_response_bytes:
                    raise IntegrityError("response_too_large")
            body = response.read(max_response_bytes + 1)
            if len(body) > max_response_bytes:
                raise IntegrityError("response_too_large")
            return body
    except urllib.error.HTTPError as exc:
        raise HttpFailure(exc.code, _retry_after(exc.headers.get("Retry-After"))) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise HttpFailure(None) from None


def preflight_model(config: DistillationConfig) -> dict[str, Any]:
    request = urllib.request.Request(f"{config.endpoint}/models", headers=_headers(config))
    try:
        raw = _open(request, config.timeout_seconds, config.max_response_bytes)
    except HttpFailure as exc:
        status = "network" if exc.status is None else str(exc.status)
        raise InputError(f"teacher preflight HTTP 실패: {status}") from None
    try:
        value = json.loads(raw)
        models = value["data"]
        identifiers = [item["id"] for item in models]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise IntegrityError("teacher /models 응답 schema가 올바르지 않습니다") from exc
    if config.model not in identifiers:
        raise InputError(f"teacher model을 찾을 수 없습니다: {config.model}")
    return {"status": "ok", "endpoint": config.endpoint, "model": config.model}


def request_body(config: DistillationConfig, prompt: str) -> bytes:
    payload: dict[str, Any] = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": config.system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def completion(config: DistillationConfig, prompt: str) -> tuple[bytes, str, bytes]:
    body = request_body(config, prompt)
    request = urllib.request.Request(
        f"{config.endpoint}/chat/completions", data=body, headers=_headers(config), method="POST"
    )
    raw = _open(request, config.timeout_seconds, config.max_response_bytes)
    try:
        parsed: object = json.loads(raw)
        if not isinstance(parsed, Mapping):
            raise TypeError
        value = cast(Mapping[str, object], parsed)
        choices_value = value.get("choices")
        if not isinstance(choices_value, list):
            raise TypeError
        choices = cast(list[object], choices_value)
        if len(choices) != 1:
            raise TypeError
        choice_value = choices[0]
        if not isinstance(choice_value, Mapping):
            raise TypeError
        choice = cast(Mapping[str, object], choice_value)
        message_value = choice.get("message")
        if not isinstance(message_value, Mapping):
            raise TypeError
        message = cast(Mapping[str, object], message_value)
        content = message.get("content")
        if set(message) - {"role", "content", "reasoning_content"}:
            raise IntegrityError("unexpected_message_fields")
        if message.get("role") != "assistant":
            raise IntegrityError("message_role_not_assistant")
        if choice.get("finish_reason") != "stop":
            raise IntegrityError("finish_reason_not_stop")
        if message.get("reasoning_content") not in {None, ""}:
            raise IntegrityError("reasoning_content_not_empty")
        if not isinstance(content, str) or not content.strip():
            raise IntegrityError("empty_content")
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise IntegrityError("teacher completion 응답 schema가 올바르지 않습니다") from exc
    return body, content, raw
