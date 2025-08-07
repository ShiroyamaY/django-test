FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS build

ARG ENVIRONMENT=dev

WORKDIR /tms

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV ENVIRONMENT=${ENVIRONMENT}
COPY pyproject.toml /tms/pyproject.toml

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    if [ "$ENVIRONMENT" = "prod" ]; then \
        uv sync --frozen --no-install-project --no-dev; \
    else \
        uv sync --frozen --no-install-project; \
    fi

COPY . .

FROM python:3.13-slim AS final

RUN useradd -mu 1000 node
USER node

WORKDIR /tms

ENV VIRTUAL_ENV=./.venv
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"

COPY --chown=node --from=build /tms /tms
COPY --chown=node start.sh ./start.sh

RUN chmod +x ./start.sh

ENTRYPOINT ["./start.sh"]
