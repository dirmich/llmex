# 0.7.0에서 1.0.0으로 이전

1. `uv sync --frozen`으로 1.0 환경을 새로 만든다.
2. 기존 M0–M6 config와 artifact schema는 유지되며 공개 전에 `release audit`을 실행한다.
3. 배포 후보는 `release bundle`의 checksum·SBOM·provenance와 함께 관리한다.
4. 외부 공개 자동화는 반드시 `release gate` 성공 뒤에만 실행한다.

1.0은 `0.ref`, raw data, checkpoint를 wheel 실행 경계에서 제외한다. 내부 모듈 직접 import는 CLI 또는
명시된 schema로 이전한다.
