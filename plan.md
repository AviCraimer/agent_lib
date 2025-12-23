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
- [x] TODO: Create `snapshot()` wrapper function for easy library swap later
  - [x] Create `src/agent_lib/store/snapshot.py`
  - [x] Define `def snapshot[S](state: S) -> S` using `copy.deepcopy`
  - [x] Add docstring noting this can be swapped for `duper`, pickle, or `orjson` later
  - [x] Import and use in Store instead of direct `copy.deepcopy` call (deferred to Phase 2 when `_process_action` is implemented)

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
- [x] TODO: Implement scope helpers in Action class
  - [x] Add nested `class scope` inside `Action`
  - [x] Define `no_op: ClassVar[frozenset[str]] = frozenset()`
  - [x] Define `full_diff: ClassVar[frozenset[str]] = frozenset({"."})`
  - [x] Update type annotations: handler returns `frozenset[str]`
  - [x] Run `make types` to verify pyright accepts
  - [x] Verify that example `src/agent_lib/examples/demo_1/transcription_with_store.py` still works with new action format.

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
- [x] TODO: Implement `_process_action()` in Store
  - [x] Add imports: `from deepdiff import DeepDiff, Delta` and `from glom import T, glom`
  - [x] Add method `_process_action(self, handler: Callable, payload: Any) -> Delta`
  - [x] Call `snapshot()` before action runs
  - [x] Call action handler, capture returned scope
  - [x] Handle empty scope (no-op) → return `Delta({})`
  - [x] Loop through scope paths, glom subtrees, diff, combine with `+` (note: uses `T` for root access when path is ".")
  - [x] Write unit test: action returns specific path, verify Delta contains change
  - [x] Write unit test: action returns `no_op`, verify empty Delta
  - [x] Write unit test: action returns `full_diff`, verify full state diffed
- [x] TODO: Add `deepdiff` and `glom` to dependencies
  - [x] Add to `pyproject.toml` under `[project.dependencies]`
  - [x] Run `make setup` to install
  - [x] Verify imports work: `python -c "from deepdiff import Delta; from glom import glom"`

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
  - [ ] Rename `_bind_actions()` to `_bind_actions()` (or keep name, update internals)
  - [ ] Change bound function signature from `-> S` to `-> None`
  - [ ] Replace direct `action.handler(self.get(), payload)` with `self._process_action()`
  - [ ] Add call to `self._notify_subscribers(delta)` after processing
  - [ ] Update `_actions` dict type annotation: `dict[str, Callable[..., None]]`
  - [ ] Update existing example code in `transcription_with_store.py`
  - [ ] Run `make types` to verify no type errors

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
  - [ ] Add `_subscribers: list[Callable[[Delta], None]]` to Store `__init__`
  - [ ] Implement `subscribe(self, callback) -> Callable[[], None]`
  - [ ] Return lambda that removes callback from list
  - [ ] Implement `_notify_subscribers(self, delta: Delta) -> None`
  - [ ] Early return if `not delta.diff` (empty delta)
  - [ ] Iterate subscribers, call each with delta
  - [ ] Write unit test: subscribe, trigger action, verify callback received Delta
  - [ ] Write unit test: unsubscribe, trigger action, verify callback NOT called
  - [ ] Write unit test: no-op action does not trigger subscribers
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
  - [ ] Create `@staticmethod async_action(on_success, on_error=None)` on Store
  - [ ] Return a decorator that wraps async function
  - [ ] Wrapper should call `_run_async_action()` with captured hooks
  - [ ] Ensure decorated function is bound to store instance (similar to `action`)
  - [ ] Type annotations: accept `Callable[[S, T], Awaitable[R]]`, return bound async method
  - [ ] Run `make types` to verify pyright accepts
- [ ] TODO: Implement `_run_async_action()`
  - [ ] Add method `async _run_async_action(self, async_fn, on_success, on_error, payload)`
  - [ ] Call `await async_fn(self._state, payload)` to get result
  - [ ] On success: call bound `on_success` action with result as payload
  - [ ] On exception: if `on_error` provided, call it with exception; else re-raise
  - [ ] Write unit test: async success path triggers `on_success`
  - [ ] Write unit test: async error path triggers `on_error`
  - [ ] Write unit test: async error with no `on_error` re-raises exception


---

## Deferred / Future

### @staticmethod Requirement

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

**Status: FOR LATER, IGNORE FOR NOW**
- [ ] Experiment with Option A and pyright
  - [ ] Create test file with external function + class assignment pattern
  - [ ] Define plain function: `def set_language(state: AppState, lang: str) -> frozenset[str]`
  - [ ] Assign in class body: `set_language = Store.action(set_language)`
  - [ ] Run `make types` - check for pyright errors
  - [ ] If passes: document as recommended pattern, update examples
  - [ ] If fails: note specific error for Option B investigation
- [ ] If A fails, try descriptor approach
  - [ ] Research Python descriptor protocol (`__get__`, `__set__`)
  - [ ] Modify `Action` class to implement `__get__` for instance binding
  - [ ] `__get__` should return bound method that doesn't include `self` in signature
  - [ ] Test with pyright
  - [ ] If works: update `Action` class, document pattern


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

## Design Rationale (Context for Future Self)

### Why Mutation Over Immutability?
Even Redux adopted Immer because writing immutable updates is tedious. In Python it's worse—no spread operators, `dataclasses.replace()` chains are verbose. Since we need snapshots anyway for change detection, we get the benefits of immutability (knowing what changed) without the DX cost.

### Scope vs Changed Paths (Critical Distinction)
The `frozenset[str]` returned by actions is **where to look**, NOT **what changed**. The action says "I touched `user.settings`" and the system diffs that subtree to find the actual leaf changes. This means:
- Developer doesn't need to track every leaf mutation
- System discovers actual changes via diff
- More efficient than full-state diff when scope is narrow

### Why Delta Over Raw DeepDiff?
- Delta supports `+` operator for combining multiple diffs
- Provides `.to_flat_rows()` for easy iteration
- Can be applied to objects for replay/undo (future feature)
- Raw DeepDiff results don't support combination

### DeepDiff Path Format
DeepDiff paths have `root.` prefix and may use bracket notation: `root['key']` or `root.key`. When diffing subtrees, paths are relative to subtree root. May need path normalization when presenting to subscribers.

### Why glom?
Glom uses dot-notation paths (`user.settings.language`) which is the same format we expose to users. It also supports the root path `"."` for full-state access.

### No `dispatch()` Function
Unlike Redux, we don't require manual dispatch. Actions are auto-bound to store instances on creation: `store.set_language("es")` instead of `store.dispatch(set_language, "es")`. See CLAUDE.md.

### Why Subscriptions Not Re-Rendering?
LLM apps generate context on-demand when agents are called—not reactively when state changes. Subscriptions are for triggering agent calls or side effects, not for re-rendering UI.

### Performance Note
Currently we deepcopy on every action. Potential optimization: only deepcopy when `self._subscribers` is non-empty. If no one's listening for changes, skip the snapshot/diff overhead.

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

### Phase 1: Dependencies & Foundation
1. [ ] Add `deepdiff` and `glom` to `pyproject.toml`
2. [ ] Create `snapshot.py` wrapper module
3. [ ] Add `Action.scope` helpers (`no_op`, `full_diff`)

### Phase 2: Core Diffing
4. [ ] Implement `_process_action()` with Delta support
5. [ ] Write unit tests for `_process_action()`

### Phase 3: Action Flow
6. [ ] Update `_bind_actions()` for void return
7. [ ] Implement `subscribe()` / `_notify_subscribers()`
8. [ ] Write unit tests for subscriptions

### Phase 4: Async Support
9. [ ] Implement `@Store.async_action` decorator
10. [ ] Implement `_run_async_action()`
11. [ ] Write unit tests for async actions

### Phase 5: DX Improvements
12. [ ] Experiment with external function assignment (eliminate @staticmethod)
13. [ ] Update examples with new patterns
14. [ ] Update CLAUDE.md with new design decisions