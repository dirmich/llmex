"""Git에 봉인된 보호 CI 정책과 서명 진술 검증."""
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import stat
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from llmex.errors import IntegrityError

POLICY_PATH = Path(".llmex/trust-policy.json")
CANONICAL_DIGEST = re.compile(r"[0-9a-f]{64}")
CANONICAL_COMMIT = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")


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


def _load_policy(repository: Path) -> tuple[dict[str, Any], dict[str, str]]:
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
        secrets = cast(dict[str, str], json.loads(os.environ["LLMEX_PROTECTED_SIGNING_KEYS"]))
    except (
        OSError,
        subprocess.CalledProcessError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
    ) as exc:
        raise IntegrityError("보호 CI trust policy/서명 key를 검증할 수 없습니다") from exc
    if raw != committed or mode & 0o022:
        raise IntegrityError("trust policy가 HEAD와 다르거나 group/other 쓰기 가능합니다")
    if not isinstance(policy, dict) or policy.get("schema_version") != 1:
        raise IntegrityError("보호 CI trust policy schema가 유효하지 않습니다")
    if policy.get("authority") != "protected-ci":
        raise IntegrityError("로컬 self-signed policy는 권위 있는 판정이 아닙니다")
    issuers = policy.get("issuers")
    if not isinstance(issuers, dict) or not issuers:
        raise IntegrityError("보호 CI issuer policy가 비었습니다")
    if set(secrets) != set(issuers):
        raise IntegrityError("보호 CI signing key 집합이 policy issuer와 다릅니다")
    for issuer, secret in secrets.items():
        item = issuers.get(issuer)
        if (
            not secret
            or not isinstance(item, dict)
            or not hmac.compare_digest(
                hashlib.sha256(secret.encode()).hexdigest(), str(item.get("key_sha256", ""))
            )
        ):
            raise IntegrityError(f"{issuer}: 보호 CI signing key가 policy와 다릅니다")
    return policy, secrets


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
) -> None:
    """정책 role/kind, 유효 기간과 canonical HMAC 서명을 검증한다."""
    policy, secrets = _load_policy(repository)
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
        issued = rfc3339(statement.get("issued_at"))
        expires = rfc3339(statement.get("expires_at"))
    except (ValueError, TypeError) as exc:
        raise IntegrityError(f"{expected_kind}: RFC3339 시각이 유효하지 않습니다") from exc
    now = datetime.now(UTC)
    if not issued <= now < expires or expires <= issued:
        raise IntegrityError(f"{expected_kind}: 아직 유효하지 않거나 만료되었습니다")
    canonical = json.dumps(
        signed_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    expected = hmac.new(secrets[cast(str, issuer)].encode(), canonical.encode(), hashlib.sha256)
    signature = statement.get("signature")
    if not isinstance(signature, str) or not CANONICAL_DIGEST.fullmatch(signature):
        raise IntegrityError(f"{expected_kind}: canonical 서명이 없습니다")
    if not hmac.compare_digest(signature, expected.hexdigest()):
        raise IntegrityError(f"{expected_kind}: 신뢰 가능한 서명 검증 실패")
