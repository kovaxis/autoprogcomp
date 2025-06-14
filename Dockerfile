# ========= RUN =========
FROM python:3.12-slim-bookworm

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy the app source into the container
WORKDIR /app

# Install dependencies
COPY ./pyproject.toml ./uv.lock ./.python-version ./
RUN uv sync --frozen --no-dev

# Copy the rest of the app source
# IMPORTANT: This must be updated if new config or source directories are added
COPY ./app/ ./app/
COPY ./typings/ ./typings/

# Mount configuration
VOLUME /app/config

# Run the production single-threaded FastAPI server
CMD ["uv", "run", "--no-sync", "python", "-m", "app.recurrent"]
