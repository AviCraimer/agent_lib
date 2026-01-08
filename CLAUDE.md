# Project Conventions for Claude Code

## Intro

This is an attemp to build a lightweight custom library for building LLM powered apps. It focuses on *context engineering* and *predictable state management*. It uses programming paradigms adapted from front-end web development tools like React and Redux. A key difference is that rendering context for LLMs does not require incremental updates since strings are lighter weight than DOM nodes. This simplifies rendering. Therefore, we are mainly borring the paradigms of component compositionality, prop-binding (React) as well as connecting to a single Store as a source of truth and updating through actions to provide controlled state mutation (Redux minus immutability).



## Design Decisions

- **JustChildren uses dict, not dataclass**: The `{"children": [...]}` pattern is intentional. It's simpler to type and doesn't require a special import. A dataclass would offer typo protection but the tradeoff isn't worth it for a single-field wrapper.

- No `dispatch` function. We make a deliberate decision to avoid the Redux pattern of having to manually dispatch actions. Instead Actions are bound to a store when the store is created, and after that any call to that action automatically mutates the store.

## Package Structure

This project uses **implicit namespace packages** (PEP 420). Do NOT add `__init__.py` files to any directories.

## Code Style

- Use `ruff` for linting and formatting (run `make lint`)
- Use `pyright` for type checking in strict mode (run `make types`)
- All functions must have type annotations
- Line length: 100 characters

## Development Commands

Activate venv before tying to run python code.
- `source .venv/bin/activate`

Use the Makefile for common tasks:
- `make setup` - Initial setup (create venv, install deps)
- `make test` - Run tests
- `make types` - Run type checker
- `make lint` - Run linter
- `make check` - Run all checks
- `make run` - Run the CLI entry point


## Unit Tests

Any units tests should be added to `/tests` while mirroring the directory structure of `src/agent_lib`. For example, a test file for `src/agent_lib/store/Store.py` should be under `test/store`.

Add the suffix `_LLM` to any test file you generate. This will allow the development team to track which tests are written (or validated by) humans and which are written by LLMs. Unless given explicit permission, never add tests or modify tests inside an existing test file which does not end in `_LLM.py`.

## Python Type Hints 3.13+ Syntax Few Shot Learning

Where-ever possible, use the newer Python syntax for type hints. Please correct older syntax when you find the old syntax in a file you are working on anyway.

❌OLD SYNTAX
```python
from typing import List, Optional, Union, TypeVar, Generic, Callable, Dict, Any

T = TypeVar("T")
Vector = List[float]

class Node(Generic[T]):
    def __init__(self, val: T, children: Optional[List["Node"]] = None):
        self.children = children

    # Returns class using string quotes
    def add(self, other: Union["Node", int]) -> "Node":
        ...

def process(func: Callable[[int], int], data: Dict[str, Any]) -> Vector:
    ...
```

✅ NEW SYNTAX
```python
from __future__ import annotations
from collections.abc import Callable
from typing import Self, Any

type Vector = list[float]

class Node[T]:
    def __init__(self, val: T, children: list[Node] | None = None):
        self.children = children

    # using unquoted class type (future annotations) in the argument and using Self for correct sub-class typing in the return.
    def add(self, other: Node | int) -> Self:
        ...

def process(func: Callable[[int], int], data: dict[str, Any]) -> Vector:
    ...
```

❌OLD SYTNAX
```python
S = TypeVar("S", bound=str)
def text_proc(val: S) -> S: ...
```

✅ NEW SYNTAX
```python
def text_proc[S: str](val: S) -> S: ...
```