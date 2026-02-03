# agent_lib

A Python library for building reactive agentic applications with LLMs.

This is a work in progress. It is inspired by patterns from modern front-end web development.

- Component based rendering of context.
- State managed by a store for a single source of truth
- An agent runtime to create LLMs agents, and grant them access to tools which allow controlled state updates.
- A subscription system for orchestration rules triggered by state changes.

## Examples

Currently the main example app is here: src/agent_lib/examples/exact_text_length

It uses a single agent to iteratively generate a text with an exact word count.

## Setup

```bash
make setup
```

## Usage

```bash
make run
```

## Development

Run tests:
```bash
make test
```

Type checking:
```bash
make types
```

Linting:
```bash
make lint
```

All checks:
```bash
make check
```


