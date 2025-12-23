# agent_lib Store Documentation

## Overview

The **Store** component provides predictable state management for LLM-powered applications. Inspired by Redux, it's adapted for context engineering with these core principles:

- **Mutation-based state** for developer ergonomics
- **Automatic change detection** via snapshots + diffing
- **Subscribers receive Delta objects** with detailed change information
- **Async operations separated** from sync state mutations

## Key Concepts

### State Mutation Model

Unlike Redux's immutability, we allow direct state mutation:

```python
@Store.action
@staticmethod
def set_language(state: AppState, lang: str) -> frozenset[str]:
    state.language = lang  # Direct mutation
    return frozenset({"language"})
```

**Why mutation?**
- Easier to write (no spread operators or `dataclasses.replace()` chains)
- Python dataclasses are naturally mutable
- Change detection is handled by diffing snapshots, not reference comparison

### Action Scope

Actions return a `frozenset[str]` indicating **where** they mutated—not what changed, just where to look:

| Return Value | Meaning |
|--------------|---------|
| `frozenset()` | No-op—skip diff and notifications |
| `frozenset({"."})` | Full diff—check entire state |
| `frozenset({"user.settings"})` | Scoped diff—check only this subtree |

Helper constants avoid magic strings:

```python
from agent_lib.store.Action import Action

Action.scope.no_op      # frozenset()
Action.scope.full_diff  # frozenset({"."})
```

### Change Detection Flow

1. Snapshot state before action runs
2. Action mutates state, returns scope
3. DeepDiff compares snapshot vs current state (restricted to scope paths)
4. Delta object captures all changes with full paths
5. Subscribers receive Delta

**Performance:** Scoped diffing is ~17x faster than full-state diff while maintaining correct paths.

### Subscriptions

Subscribers receive Delta objects and filter by path themselves:

```python
def on_language_change(delta: Delta):
    for row in delta.to_flat_rows():
        if 'language' in row.path:
            trigger_translation_agent()

unsubscribe = store.subscribe(on_language_change)
# later: unsubscribe()
```

### Async Actions

**Problem:** Can't snapshot during an await—other actions could run between snapshot and mutation.

**Solution:** Async functions are **read-only**. They return a result passed to a sync `on_success` handler which performs the actual mutation.

```python
def set_transcription(state: AppState, text: str) -> frozenset[str]:
    state.transcription = text
    return frozenset({"transcription"})

class TranscriptionStore(Store[AppState]):
    @Store.async_action(on_success=set_transcription, on_error=set_error)
    @staticmethod
    async def transcribe(state: AppState, url: str) -> str:
        # Read-only access to state
        text = await api.transcribe(url)
        return text  # Becomes payload for on_success

# Usage
await store.transcribe("http://example.com/audio.mp3")  # Returns None
# State is updated, subscribers notified
```

## API Reference

### Store Class

```python
class Store[St]:
    def __init__(self, initial_state: St): ...

    # State access
    def get(self) -> St
    def set(self, state: St) -> None

    # Subscriptions
    def subscribe(self, callback: Callable[[Delta], None]) -> Callable[[], None]

    # Decorators (defined as static methods)
    @staticmethod
    def action(handler) -> Action

    @staticmethod
    def async_action(on_success, on_error=None) -> decorator
```

### Type Signatures

```python
# Generic variable names: St=state, PL=payload, R=result

# Sync action handler
(state: St, payload: PL) -> frozenset[str]

# Async handler (read-only, returns result for on_success)
async (state: St, payload: PL) -> R

# Subscriber
(delta: Delta) -> None

# Unsubscribe function
() -> None
```

### Delta Object

From the `deepdiff` library:

```python
# Dict access
delta.diff  # {'values_changed': {'root.language': {'new_value': 'es', 'old_value': 'en'}}}

# Flat rows (recommended for iteration)
for row in delta.to_flat_rows():
    print(row.path, row.action, row.value)
    # ['language'], 'values_changed', 'es'
```

## Complete Example

```python
from dataclasses import dataclass
from agent_lib.store.Store import Store
from agent_lib.store.Action import Action

@dataclass
class AppState:
    language: str
    count: int

class AppStore(Store[AppState]):
    @Store.action
    @staticmethod
    def set_language(state: AppState, lang: str) -> frozenset[str]:
        if state.language == lang:
            return Action.scope.no_op  # Early exit, no diff
        state.language = lang
        return frozenset({"language"})

    @Store.action
    @staticmethod
    def increment(state: AppState, amount: int) -> frozenset[str]:
        state.count += amount
        return frozenset({"count"})

# Usage
store = AppStore(AppState(language="en", count=0))

# Subscribe to changes
def log_changes(delta):
    for row in delta.to_flat_rows():
        print(f"Changed: {row.path} = {row.value}")

unsubscribe = store.subscribe(log_changes)

store.set_language("es")  # Prints: Changed: ['language'] = es
store.increment(5)        # Prints: Changed: ['count'] = 5

# Access state
print(store.get())  # AppState(language='es', count=5)

unsubscribe()  # Stop receiving notifications
```

## Design Rationale

### Why Mutation Over Immutability?

Even Redux adopted Immer because writing immutable updates is tedious. In Python it's worse—no spread operators, `dataclasses.replace()` chains are verbose. Since we need snapshots anyway for change detection, we get the benefits of immutability (knowing what changed) without the DX cost.

### Scope vs Changed Paths

The `frozenset[str]` returned by actions is **where to look**, NOT **what changed**. The action says "I touched `user.settings`" and the system diffs that subtree to find the actual leaf changes. This means:
- Developer doesn't need to track every leaf mutation
- System discovers actual changes via diff
- More efficient than full-state diff when scope is narrow

### No `dispatch()` Function

Unlike Redux, we don't require manual dispatch. Actions are auto-bound to store instances: `store.set_language("es")` instead of `store.dispatch(set_language, "es")`.

### Why Subscriptions Not Re-Rendering?

LLM apps generate context on-demand when agents are called—not reactively when state changes. Subscriptions are for triggering agent calls or side effects, not for re-rendering UI.

### Async Action Design

Hooks (`on_success`, `on_error`) are handler functions, not Action objects or strings:
- Same signature as sync handlers: `(state, payload) -> frozenset[str]`
- Provides static type checking
- No runtime lookup required

No `on_start` hook (YAGNI for LLM apps):
- LLM apps are often headless/agent-to-agent
- Streaming responses don't need loading spinners
- If needed, call a sync action manually before the async action

## Dependencies

| Package | Purpose |
|---------|---------|
| `deepdiff` | Diffing and Delta objects |
