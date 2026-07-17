"""학습 데이터와 품질 평가가 공유하는 민감 출력 탐지 규칙."""

import re
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class SensitiveOutputRule:
    """외부 결과에는 이름만 노출하는 민감 출력 정규식."""

    name: str
    pattern: str
    category: str


SENSITIVE_OUTPUT_SCAN_MAX_CHARS = 65_536
SENSITIVE_OUTPUT_LENGTH_RULE_NAME = "assistant-content-length-limit"
SAFE_EXTRA_PATTERN_MAX_CHARS = 256
SAFE_ASSERTION_PATTERN_MAX_CHARS = 1_024
_UNSAFE_EXTRA_PATTERN_SYNTAX = re.compile(r"[()|{}*+?]|\\[1-9]")
_BOUNDED_REPEAT = re.compile(r"\{(?:(\d+)(?:,(\d*))?|,(\d+))\}")
_REVIEWED_COMPLEX_ASSERTION_PATTERNS = frozenset({r"(?i)(?:api[_ -]?key|secret)\s*[:=]"})


BUILTIN_SENSITIVE_OUTPUT_RULES: tuple[SensitiveOutputRule, ...] = (
    SensitiveOutputRule(
        name="korean-resident-registration-number",
        pattern=r"(?<!\d)\d{6}-?[1-4]\d{6}(?!\d)",
        category="pii",
    ),
    SensitiveOutputRule(
        name="korean-mobile-phone",
        pattern=r"(?<!\d)01[016789]-?\d{3,4}-?\d{4}(?!\d)",
        category="pii",
    ),
    SensitiveOutputRule(
        name="email-address",
        pattern=(
            r"(?<![A-Za-z0-9._%+-])"
            r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
            r"(?![A-Za-z0-9._%+-])"
        ),
        category="pii",
    ),
    SensitiveOutputRule(
        name="api-key-secret-assignment",
        pattern=(
            r"(?ai)(?<![A-Za-z0-9_])(?:api[_ -]?key|secret)\s*[:=]\s*"
            r"[A-Za-z0-9_-]{8,}(?![A-Za-z0-9_])"
        ),
        category="secret",
    ),
)

BUILTIN_SENSITIVE_OUTPUT_RULE_NAMES = frozenset(
    rule.name for rule in BUILTIN_SENSITIVE_OUTPUT_RULES
)
BUILTIN_SENSITIVE_OUTPUT_PATTERNS = frozenset(
    rule.pattern for rule in BUILTIN_SENSITIVE_OUTPUT_RULES
)
BUILTIN_PII_PATTERNS = tuple(
    rule.pattern for rule in BUILTIN_SENSITIVE_OUTPUT_RULES if rule.category == "pii"
)
BUILTIN_SECRET_PATTERNS = tuple(
    rule.pattern for rule in BUILTIN_SENSITIVE_OUTPUT_RULES if rule.category == "secret"
)
_COMPILED_BUILTINS = tuple(
    (rule.name, rule.category, re.compile(rule.pattern)) for rule in BUILTIN_SENSITIVE_OUTPUT_RULES
)


def matched_sensitive_output_rules(
    text: str, extra_rules: Iterable[tuple[str, str]] = ()
) -> frozenset[str]:
    """문자열에 맞은 built-in 및 추가 규칙 이름을 중복 없이 반환한다."""

    if len(text) > SENSITIVE_OUTPUT_SCAN_MAX_CHARS:
        return frozenset({SENSITIVE_OUTPUT_LENGTH_RULE_NAME})
    matched = {name for name, _category, pattern in _COMPILED_BUILTINS if pattern.search(text)}
    matched.update(name for name, pattern in extra_rules if re.search(pattern, text))
    return frozenset(matched)


def validate_safe_extra_pattern(pattern: str) -> None:
    """고정 폭 token만 허용해 사용자 정규식의 비선형 backtracking을 차단한다."""

    if len(pattern) > SAFE_EXTRA_PATTERN_MAX_CHARS:
        raise ValueError("민감 출력 추가 정규식이 너무 깁니다")
    if _UNSAFE_EXTRA_PATTERN_SYNTAX.search(pattern):
        raise ValueError("민감 출력 추가 정규식은 고정 폭 안전 부분집합만 허용합니다")
    try:
        re.compile(pattern)
    except re.error as exc:
        raise ValueError("올바르지 않은 민감 출력 추가 정규식") from exc


@dataclass(frozen=True)
class _AssertionStructure:
    has_repeat: bool = False
    has_branch: bool = False
    branch_count: int = 0
    whitespace_atom: bool = False
    fixed_non_whitespace_atom: bool = False


@dataclass(frozen=True)
class _AssertionQuantifier:
    present: bool = False
    variable: bool = False


class _AssertionPatternParser:
    """공개 stdlib API만 사용해 assertion 정규식의 위험 중첩 구조를 검사한다."""

    def __init__(self, pattern: str) -> None:
        self.pattern = pattern
        self.index = 0

    def parse(self) -> None:
        structure = self._expression(in_group=False)
        if self.index != len(self.pattern):
            raise ValueError("quality assertion 정규식 구조가 올바르지 않습니다")
        if structure.branch_count > 1:
            raise ValueError("quality assertion 정규식의 교대 분기는 하나만 허용합니다")

    def _expression(self, *, in_group: bool) -> _AssertionStructure:
        has_repeat = False
        has_branch = False
        nested_branch_count = 0
        has_local_branch = False
        previous_variable_kind: str | None = None
        fixed_separator_since_variable = False
        while self.index < len(self.pattern):
            character = self.pattern[self.index]
            if character == ")":
                if not in_group:
                    raise ValueError("quality assertion 정규식 괄호가 올바르지 않습니다")
                break
            if character == "|":
                has_branch = True
                has_local_branch = True
                previous_variable_kind = None
                fixed_separator_since_variable = False
                self.index += 1
                continue
            atom = self._atom()
            quantifier = self._consume_quantifier()
            if quantifier.present:
                if atom.has_repeat or atom.has_branch:
                    raise ValueError("quality assertion 정규식에 비선형 반복 구조가 있습니다")
                has_repeat = True
            if atom.has_repeat and previous_variable_kind is not None:
                raise ValueError("quality assertion 정규식에 여러 모호한 반복이 있습니다")
            if atom.has_repeat:
                previous_variable_kind = "complex"
                fixed_separator_since_variable = False
            if quantifier.variable:
                current_kind = "whitespace" if atom.whitespace_atom else "other"
                if previous_variable_kind is not None and not (
                    previous_variable_kind == current_kind == "whitespace"
                    and fixed_separator_since_variable
                ):
                    raise ValueError("quality assertion 정규식에 여러 모호한 반복이 있습니다")
                previous_variable_kind = current_kind
                fixed_separator_since_variable = False
            elif atom.fixed_non_whitespace_atom and previous_variable_kind is not None:
                fixed_separator_since_variable = True
            has_repeat = has_repeat or atom.has_repeat
            has_branch = has_branch or atom.has_branch
            nested_branch_count += atom.branch_count
        return _AssertionStructure(
            has_repeat=has_repeat,
            has_branch=has_branch,
            branch_count=nested_branch_count + int(has_local_branch),
        )

    def _atom(self) -> _AssertionStructure:
        character = self.pattern[self.index]
        if character in "*+?":
            raise ValueError("quality assertion 정규식 반복 위치가 올바르지 않습니다")
        if character == "\\":
            self.index += 1
            if self.index >= len(self.pattern) or self.pattern[self.index].isdigit():
                raise ValueError("quality assertion 정규식 backreference는 허용하지 않습니다")
            escaped = self.pattern[self.index]
            self.index += 1
            return _AssertionStructure(
                whitespace_atom=escaped == "s",
                fixed_non_whitespace_atom=escaped in "dw",
            )
        if character == "[":
            self._character_class()
            return _AssertionStructure()
        if character == "(":
            return self._group()
        self.index += 1
        return _AssertionStructure(
            fixed_non_whitespace_atom=character not in ".^$" and not character.isspace()
        )

    def _character_class(self) -> None:
        self.index += 1
        if self.index < len(self.pattern) and self.pattern[self.index] == "^":
            self.index += 1
        if self.index < len(self.pattern) and self.pattern[self.index] == "]":
            self.index += 1
        while self.index < len(self.pattern):
            if self.pattern[self.index] == "\\":
                self.index += 2
                continue
            if self.pattern[self.index] == "]":
                self.index += 1
                return
            self.index += 1
        raise ValueError("quality assertion 정규식 문자 클래스가 닫히지 않았습니다")

    def _group(self) -> _AssertionStructure:
        self.index += 1
        if self.pattern.startswith("?P=", self.index):
            raise ValueError("quality assertion 정규식 backreference는 허용하지 않습니다")
        if self.index < len(self.pattern) and self.pattern[self.index] == "?":
            self.index += 1
            if self.index < len(self.pattern) and self.pattern[self.index] in "=!<":
                raise ValueError("quality assertion 정규식 lookaround는 허용하지 않습니다")
            if self.index < len(self.pattern) and self.pattern[self.index] == ":":
                self.index += 1
            else:
                while self.index < len(self.pattern) and self.pattern[self.index] in "aiLmsux-":
                    self.index += 1
                if self.index >= len(self.pattern):
                    raise ValueError("quality assertion inline flag가 올바르지 않습니다")
                if self.pattern[self.index] == ")":
                    self.index += 1
                    return _AssertionStructure()
                if self.pattern[self.index] != ":":
                    raise ValueError("quality assertion 특수 그룹은 허용하지 않습니다")
                self.index += 1
        structure = self._expression(in_group=True)
        if self.index >= len(self.pattern) or self.pattern[self.index] != ")":
            raise ValueError("quality assertion 정규식 그룹이 닫히지 않았습니다")
        self.index += 1
        return structure

    def _consume_quantifier(self) -> _AssertionQuantifier:
        if self.index >= len(self.pattern):
            return _AssertionQuantifier()
        character = self.pattern[self.index]
        if character in "*+?":
            self.index += 1
            variable = True
        elif character == "{":
            matched = _BOUNDED_REPEAT.match(self.pattern, self.index)
            if matched is None:
                return _AssertionQuantifier()
            self.index = matched.end()
            _minimum, maximum, upper_only = matched.groups()
            variable = upper_only is not None or maximum is not None
        else:
            return _AssertionQuantifier()
        if self.index < len(self.pattern) and self.pattern[self.index] in "?+":
            self.index += 1
        return _AssertionQuantifier(present=True, variable=variable)


def validate_safe_assertion_pattern(pattern: str) -> None:
    """기존 표현력을 유지하며 비선형 assertion 정규식 구조를 거부한다."""

    if len(pattern) > SAFE_ASSERTION_PATTERN_MAX_CHARS:
        raise ValueError("quality assertion 정규식이 너무 깁니다")
    try:
        re.compile(pattern)
    except re.error as exc:
        raise ValueError("올바르지 않은 quality assertion 정규식") from exc
    if (
        pattern in BUILTIN_SENSITIVE_OUTPUT_PATTERNS
        or pattern in _REVIEWED_COMPLEX_ASSERTION_PATTERNS
    ):
        return
    _AssertionPatternParser(pattern).parse()


def has_builtin_sensitive_output(text: str, *, category: str) -> bool:
    """품질 gate가 같은 built-in 규칙을 범주별로 재사용한다."""

    return any(
        pattern.search(text)
        for _name, rule_category, pattern in _COMPILED_BUILTINS
        if rule_category == category
    )
