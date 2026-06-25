FROM python:3.12-slim

# uv binary (deps + runner), aligned with the repo's tooling conventions (§18)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

ENV PORT_BACKEND=8200
EXPOSE 8200

# Bind 0.0.0.0 so phones on the LAN can reach the server (cahier §2 scénario A)
CMD ["uv", "run", "--no-dev", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8200"]
