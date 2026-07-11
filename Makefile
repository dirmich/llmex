.PHONY: sync lint format-check typecheck test check help ref-check fixture-check

sync:
	uv sync

lint:
	uv run ruff check .

format-check:
	uv run ruff format --check .

typecheck:
	uv run pyright

test:
	uv run pytest -q

help:
	uv run llmex --help >/dev/null

ref-check:
	cd 0.ref && shasum -a 256 -c SHA256SUMS

fixture-check:
	uv run llmex fingerprint file tests/fixtures/kowiki-sample.xml.bz2

check: lint format-check typecheck test help ref-check

