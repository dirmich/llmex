# syntax=docker/dockerfile:1.7
ARG LLMEX_BASE_IMAGE=nvcr.io/nvidia/pytorch:25.10-py3@sha256:42263b2424fc237b34c4fc4a91c30d603c57eed36e37d31ff6d9a4f1f801edee
FROM ${LLMEX_BASE_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/llmex/.venv

WORKDIR /opt/llmex

RUN python -m pip install --no-cache-dir "uv==0.10.2"
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-install-project
COPY . .
RUN uv sync --frozen

ENTRYPOINT ["uv", "run"]
CMD ["llmex", "--help"]
