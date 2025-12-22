# Project Conventions for Claude Code

## Package Structure

This project uses **implicit namespace packages** (PEP 420). Do NOT add `__init__.py` files to any directories.

## Code Style

- Use `ruff` for linting and formatting (run `make lint`)
- Use `pyright` for type checking in strict mode (run `make types`)
- All functions must have type annotations
- Line length: 100 characters

## Development Commands

Use the Makefile for common tasks:
- `make setup` - Initial setup (create venv, install deps)
- `make test` - Run tests
- `make types` - Run type checker
- `make lint` - Run linter
- `make check` - Run all checks
- `make run` - Run the CLI entry point
