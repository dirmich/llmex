"""JSON Lines 구조화 로그."""

import json
import logging
from datetime import UTC, datetime
from typing import Any, cast


class JsonFormatter(logging.Formatter):
    """한 줄 JSON으로 로그를 직렬화한다."""

    def format(self, record: logging.LogRecord) -> str:
        event: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        fields = getattr(record, "fields", None)
        if isinstance(fields, dict):
            event.update(cast(dict[str, Any], fields))
        return json.dumps(event, ensure_ascii=False, sort_keys=True)


def configure_logging(level: str = "INFO") -> None:
    """root logger를 구조화 stderr 출력으로 설정한다."""

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=level.upper(), handlers=[handler], force=True)
