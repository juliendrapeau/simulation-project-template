# syntax=docker/dockerfile:1.7
#
# simulation-project-template image (Python 3.13) using a multi-stage build:
# builder has compilers + uv; runtime keeps only the built app/venv.
#
# Build:
#   docker build -t simulation-project-template:latest .
#
# Run:
#   docker run --rm simulation-project-template:latest --help
#   docker run --rm simulation-project-template:latest generate 100 -o /results/out.json


# =============================================================================
# STAGE 1 — builder
# =============================================================================
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
ENV UV_PYTHON_DOWNLOADS=0

RUN apt-get update && apt-get install --no-install-recommends -y \
  build-essential=12.9 \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./

RUN --mount=type=cache,target=/root/.cache/uv \
  --mount=type=bind,source=uv.lock,target=uv.lock \
  --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
  uv sync --locked --no-install-project --no-dev

COPY src/ ./src/

RUN --mount=type=cache,target=/root/.cache/uv \
  uv sync --locked --no-dev


# =============================================================================
# STAGE 2 — runtime
# =============================================================================
FROM python:3.13-slim-bookworm

RUN groupadd --system --gid 999 nonroot \
  && useradd --system --gid 999 --uid 999 --create-home nonroot

COPY --from=builder --chown=nonroot:nonroot /app /app

ENV PATH="/app/.venv/bin:$PATH"

USER nonroot
WORKDIR /app

ENTRYPOINT ["spt"]
CMD ["--help"]
