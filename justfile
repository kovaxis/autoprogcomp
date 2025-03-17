
default:
    just --list

run:
    uv run python3 -m app.main

lint:
    uv run pyright
    uv run ruff check --fix
    uv run ruff format

# Setup commands

init:
    cp --no-clobber .env.example .env
    uv sync
