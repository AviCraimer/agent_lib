# agent_lib Store Design Plan

## Overview

This document captures design decisions for the **Store** component of agent_lib—a lightweight library for building LLM-powered applications. The Store provides predictable state management inspired by Redux, adapted for LLM context engineering.

**Core philosophy:**
- Mutation-based state for developer ergonomics
- Automatic change detection via snapshots + diffing
- Subscribers receive detailed change information (Delta objects)
- Async operations separated from sync state mutations

**Key dependencies:**
- `deepdiff` - diffing and Delta objects
- `glom` - path-based state access
- `copy.deepcopy` - snapshots (swappable for performance)

---

## Decisions Made

### 1. State Mutation Model

**Decision:** Embrace mutation for DX, use snapshots for change detection.

Unlike Redux's immutability, we allow direct state mutation because:
- Easier to write (no spread operators or `dataclasses.replace()` chains)
- Python dataclasses are naturally mutable
- Change detection handled by diffing snapshots, not reference comparison

**Implementation status:**
- [x] Decided: mutation-based approach
- [x] Decided: use `copy.deepcopy()` for snapshots
- [ ] TODO: Create `snapshot()` wrapper function for easy library swap later

---

### 2. Action Return Type (Scope)

**Decision:** Actions return `frozenset[str]` of glom-style paths indicating *where* they mutated.

The scope tells the system which subtrees to diff—not the exact changes, just where to look.

| Return Value | Meaning |
|--------------|---------|
| `frozenset()` | No-op, nothing changed—skip diff and notifications |
| `frozenset({"."})` | Full diff, Unknown scope—diff entire state |
| `frozenset({"user.settings"})` | Diff only this subtree |

**Helper constants** (avoid magic strings):
```python
class Action:
    class scope:
        no_op: frozenset[str] = frozenset()
        full_diff: frozenset[str] = frozenset({"."})
```

**Example action:**
```python
@Store.action
@staticmethod
def set_language(state: AppState, lang: str) -> frozenset[str]:
    if state.language == lang:
        return Action.scope.no_op  # early exit, no diff needed
    state.language = lang
    return frozenset({"language"})
```

**Implementation status:**
- [x] Decided: frozenset of paths
- [x] Decided: empty set = no-op, root path = full diff
- [x] Decided: helpers on `Action.scope`
- [ ] TODO: Implement in Action class

---

### 3. Diffing Flow

**Decision:** Use DeepDiff with Delta objects for combining multiple subtree diffs.

**Flow:**
1. Take snapshot before action runs
2. Action mutates state, returns scope (paths to diff)
3. For each path in scope, extract subtree from snapshot and current state
4. Diff subtrees, combine results using `Delta` + operator
5. Return combined Delta

```python
from deepdiff import DeepDiff, Delta
from glom import glom
import copy

def _process_action(self, action, payload) -> Delta:
    """Run action and return Delta representing all changes."""
    snapshot = copy.deepcopy(self._state)
    scope = action(self._state, payload)

    if not scope:  # no-op
        return Delta({})

    combined = Delta({})
    for scope_path in scope:
        old_subtree = glom(snapshot, scope_path)
        new_subtree = glom(self._state, scope_path)
        diff = DeepDiff(old_subtree, new_subtree)
        combined = combined + Delta(diff)

    return combined
```

**Accessing changes from Delta:**
```python
# Dict access
delta.diff  # {'values_changed': {'root.lang': {'old_value': 'en', 'new_value': 'es'}}}

# Flat rows (good for iteration/logging)
for row in delta.to_flat_rows():
    print(row['path'], row['action'], row['value'])
```

**Implementation status:**
- [x] Decided: DeepDiff for diffing
- [x] Decided: Delta for combining (supports `+` operator)
- [x] Decided: glom for path-based access
- [ ] TODO: Implement `_process_action()` in Store
- [ ] TODO: Add `deepdiff` and `glom` to dependencies

---

### 4. Bound Actions Return Void

**Decision:** Bound actions return `None`. State mutation is the side effect.

```python
class Store[S]:
    def _make_bound_action(self, action: Action) -> Callable[..., None]:
        def bound(payload: Any) -> None:
            delta = self._process_action(action.handler, payload)
            self._notify_subscribers(delta)
        return bound
```

**Rationale:**
- Previous design returned state, but relied on mutation anyway (misleading)
- Delta goes to subscribers, not caller
- Clean mental model: `call action → state mutates → subscribers notified`

**Implementation status:**
- [x] Decided: void return
- [ ] TODO: Update `_bind_actions()` to use new flow

---

### 5. Subscription System

**Decision:** Subscribers receive Delta objects and filter by path themselves.

```python
class Store[S]:
    _subscribers: list[Callable[[Delta], None]]

    def subscribe(self, callback: Callable[[Delta], None]) -> Callable[[], None]:
        """Subscribe to changes. Returns unsubscribe function."""
        self._subscribers.append(callback)
        return lambda: self._subscribers.remove(callback)

    def _notify_subscribers(self, delta: Delta) -> None:
        if not delta.diff:  # empty = no changes
            return
        for subscriber in self._subscribers:
            subscriber(delta)
```

**Example subscriber with path filtering:**
```python
def on_language_change(delta: Delta):
    for row in delta.to_flat_rows():
        if 'language' in row['path']:
            trigger_translation_agent()

unsubscribe = store.subscribe(on_language_change)
# later: unsubscribe()
```

**Implementation status:**
- [x] Decided: subscribers receive Delta
- [x] Decided: returns unsubscribe function
- [ ] TODO: Implement `subscribe()` and `_notify_subscribers()`
- [ ] Open: Add path-based subscription helpers? (e.g., `subscribe_path("user.*", cb)`)

---

### 6. Async Actions

**Decision:** Separate async work from state mutation using `on_success`/`on_error` hooks.

**Problem:** Can't snapshot during an await—other actions could run, making snapshot stale.

**Solution:** Async function is read-only; it returns a result that gets passed to a sync action.

```python
@Store.async_action(
    on_success=set_transcription,  # sync action, receives result
    on_error=set_error,            # sync action, receives exception (optional)
)
async def transcribe(state, audio_url):  # read-only access to state
    text = await api.transcribe(audio_url)
    return text  # passed to on_success
```

**Internal flow:**
```python
async def _run_async_action(self, async_fn, on_success, on_error, payload):
    try:
        # Async work (read-only, no snapshot)
        result = await async_fn(self._state, payload)
        # Sync mutation (snapshot → mutate → diff → notify)
        self._run_bound_action(on_success, result)
    except Exception as e:
        if on_error:
            self._run_bound_action(on_error, e)
        else:
            raise
```

**Why no `on_start` hook?**

LLM apps typically don't need loading spinners:
- Often headless/agent-to-agent
- Streaming responses (not loading → done)
- If needed, call sync action manually before async

**Implementation status:**
- [x] Decided: two hooks (`on_success`, `on_error`)
- [x] Decided: no `on_start` (YAGNI for LLM apps)
- [ ] TODO: Implement `@Store.async_action` decorator
- [ ] TODO: Implement `_run_async_action()`

---

## Open Questions

### 7. @staticmethod Requirement

**Problem:** Actions currently require awkward decorator stacking:

```python
@Store.action
@staticmethod  # required to avoid pyright errors
def set_language(state: AppState, lang: str) -> frozenset[str]:
    ...
```

**Potential solutions:**

| Option | Approach | Pros | Cons |
|--------|----------|------|------|
| A | External function assignment | Clean, no decorators | Less discoverable |
| B | Descriptor-based | Automatic, no staticmethod | Complex implementation |
| C | Metaclass | Process at class creation | Magic, harder to debug |

**Option A example:**
```python
def set_language(state: AppState, lang: str) -> frozenset[str]:
    state.language = lang
    return frozenset({"language"})

class TranscriptionStore(Store[AppState]):
    set_language = Store.action(set_language)
```

**Status:**
- [ ] TODO: Experiment with Option A and pyright
- [ ] TODO: If A fails, try descriptor approach

---

## Deferred / Future

### History & Undo

Consider storing Deltas for undo/redo, debugging, or audit trails:

```python
class Store[S]:
    _history: list[Delta]

    def _process_action(...):
        ...
        if delta.diff:
            self._history.append(delta)
```

**Status:** Deferred until concrete use case arises.

---

## Quick Reference

### Key Types

```python
# Action handler signature
(state: S, payload: T) -> frozenset[str]

# Async action signature
async (state: S, payload: T) -> R  # R passed to on_success

# Subscriber signature
(delta: Delta) -> None

# Unsubscribe function
() -> None
```

### Store API (planned)

```python
class Store[S]:
    # State access
    def get(self) -> S
    def set(self, state: S) -> None

    # Subscriptions
    def subscribe(self, callback) -> Callable[[], None]

    # Decorators
    @staticmethod
    def action(handler) -> Action

    @staticmethod
    def async_action(on_success, on_error=None) -> Callable
```

### Dependencies

| Package | Purpose | Version |
|---------|---------|---------|
| `deepdiff` | Diffing, Delta objects | 8.x |
| `glom` | Path-based access | 24.x |

---

## Next Steps

1. [ ] Implement `_process_action()` with Delta support
2. [ ] Update `_bind_actions()` for void return + notifications
3. [ ] Implement `subscribe()` / `_notify_subscribers()`
4. [ ] Experiment with external function assignment (pyright)
5. [ ] Implement `@Store.async_action` decorator
6. [ ] Add `deepdiff` and `glom` to pyproject.toml