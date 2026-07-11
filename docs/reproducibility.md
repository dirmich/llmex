# 최종 재현성 bundle

```bash
uv sync --frozen
make release-check
uv build
uv run llmex release bundle --output dist/reproducibility
```

bundle은 추적 파일 SHA-256, CycloneDX JSON SBOM, in-toto/SLSA 형식 provenance, 재현 명령과
요약을 생성한다. 원 데이터·가중치·로컬 환경 파일은 포함하지 않는다. clean-room 검증은 새 venv에서
wheel을 설치한 뒤 version/help/audit와 fixture 기반 CLI/pipeline E2E를 수행한다.
