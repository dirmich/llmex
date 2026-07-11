"""고정 root와 Ed25519 체인으로 Git에 봉인된 신뢰 정책·진술을 검증한다."""
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from __future__ import annotations

import base64
import json
import re
import stat
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from llmex.errors import IntegrityError

POLICY_PATH = Path(".llmex/trust-policy.json")
CANONICAL_COMMIT = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
# 이 키만 production trust anchor다. 저장소 policy가 자신의 권위를 선언할 수 없다.
PINNED_ROOT_PUBLIC_KEY = "7Ye4+UNipKIjUGrNl/+Ri1EbNmAKuEd7QH+FE3TPcWM="


def _canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _public_key(encoded: object, label: str) -> Ed25519PublicKey:
    try:
        if not isinstance(encoded, str):
            raise ValueError
        raw = base64.b64decode(encoded, validate=True)
        if len(raw) != 32:
            raise ValueError
        return Ed25519PublicKey.from_public_bytes(raw)
    except (ValueError, TypeError) as exc:
        raise IntegrityError(f"{label}: Ed25519 공개키가 유효하지 않습니다") from exc


def _verify(signature: object, payload: dict[str, Any], key: Ed25519PublicKey, label: str) -> None:
    try:
        if not isinstance(signature, str):
            raise ValueError
        raw = base64.b64decode(signature, validate=True)
        key.verify(raw, _canonical(payload))
    except (ValueError, TypeError, InvalidSignature) as exc:
        raise IntegrityError(f"{label}: Ed25519 서명 검증 실패") from exc


def repository_commit(repository: Path) -> tuple[Path, str]:
    """명시 경로가 가리키는 저장소 root와 canonical HEAD commit을 반환한다."""
    root = repository.resolve()
    try:
        top = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=root,
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()
        commit = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD^{commit}"],
            cwd=root,
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise IntegrityError(f"subject repository Git commit을 확인할 수 없습니다: {root}") from exc
    if Path(top).resolve() != root:
        raise IntegrityError("subject repository는 명시적인 Git 최상위 root여야 합니다")
    if not CANONICAL_COMMIT.fullmatch(commit):
        raise IntegrityError("subject repository commit이 비었거나 canonical hex가 아닙니다")
    return root, commit


def _load_policy(repository: Path, root_public_key: str | None = None) -> dict[str, Any]:
    policy_path = repository / POLICY_PATH
    try:
        raw = policy_path.read_bytes()
        mode = stat.S_IMODE(policy_path.stat().st_mode)
        committed = subprocess.run(
            ["git", "show", f"HEAD:{POLICY_PATH.as_posix()}"],
            cwd=repository,
            check=True,
            capture_output=True,
        ).stdout
        policy = json.loads(raw)
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        raise IntegrityError("서명된 trust policy를 검증할 수 없습니다") from exc
    if raw != committed or mode & 0o022:
        raise IntegrityError("trust policy가 HEAD와 다르거나 group/other 쓰기 가능합니다")
    if not isinstance(policy, dict) or policy.get("schema_version") != 2:
        raise IntegrityError("trust policy schema가 유효하지 않습니다")
    signature = policy.get("signature")
    payload = {key: value for key, value in policy.items() if key != "signature"}
    _verify(
        signature, payload, _public_key(root_public_key or PINNED_ROOT_PUBLIC_KEY, "root"), "policy"
    )
    issuers = policy.get("issuers")
    if not isinstance(issuers, dict) or not issuers:
        raise IntegrityError("issuer policy가 비었습니다")
    return policy


def rfc3339(value: object) -> datetime:
    if not isinstance(value, str) or not value.endswith(("Z", "+00:00")):
        raise ValueError("UTC RFC3339 시각이 아닙니다")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timezone이 없습니다")
    return parsed.astimezone(UTC)


def verify_statement(
    statement: dict[str, Any],
    *,
    repository: Path,
    expected_role: str,
    expected_kind: str,
    signed_payload: dict[str, Any],
    root_public_key: str | None = None,
) -> None:
    """고정 root가 승인한 issuer의 role/kind, 기간, Ed25519 서명을 검증한다."""
    policy = _load_policy(repository, root_public_key)
    issuer, role = statement.get("issuer"), statement.get("role")
    issuers = cast(dict[str, Any], policy["issuers"])
    item = issuers.get(issuer) if isinstance(issuer, str) else None
    if (
        not isinstance(item, dict)
        or role != expected_role
        or role not in item.get("roles", [])
        or expected_kind not in item.get("kinds", [])
        or statement.get("kind") != expected_kind
    ):
        raise IntegrityError(f"{expected_kind}: issuer-role-kind policy 위반")
    try:
        issued, expires = rfc3339(statement.get("issued_at")), rfc3339(statement.get("expires_at"))
    except (ValueError, TypeError) as exc:
        raise IntegrityError(f"{expected_kind}: RFC3339 시각이 유효하지 않습니다") from exc
    now = datetime.now(UTC)
    if not issued <= now < expires or expires <= issued:
        raise IntegrityError(f"{expected_kind}: 아직 유효하지 않거나 만료되었습니다")
    _verify(
        statement.get("signature"),
        signed_payload,
        _public_key(item.get("public_key"), str(issuer)),
        expected_kind,
    )
