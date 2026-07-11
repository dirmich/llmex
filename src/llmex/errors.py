"""사용자에게 안정적으로 노출하는 오류 코드와 예외."""

from enum import IntEnum


class ExitCode(IntEnum):
    """CLI 프로세스 종료 코드."""

    SUCCESS = 0
    CONFIG = 2
    INPUT = 3
    CONFLICT = 4
    INTEGRITY = 5
    INTERNAL = 70


class LlmexError(Exception):
    """예상 가능한 LLMEX 오류."""

    def __init__(self, message: str, code: ExitCode) -> None:
        super().__init__(message)
        self.code = code


class ConfigError(LlmexError):
    """설정 파일 구문 또는 검증 오류."""

    def __init__(self, message: str) -> None:
        super().__init__(message, ExitCode.CONFIG)


class InputError(LlmexError):
    """입력 파일 오류."""

    def __init__(self, message: str) -> None:
        super().__init__(message, ExitCode.INPUT)


class ConflictError(LlmexError):
    """기존 실행 결과와 입력 fingerprint 충돌."""

    def __init__(self, message: str) -> None:
        super().__init__(message, ExitCode.CONFLICT)


class IntegrityError(LlmexError):
    """checksum, manifest 또는 압축 스트림 무결성 오류."""

    def __init__(self, message: str) -> None:
        super().__init__(message, ExitCode.INTEGRITY)
