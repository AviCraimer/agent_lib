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
- PLthon dataclasses are naturally mutable
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

**Decision:** Use DeepDiff with `include_paths` for scoped diffing with correct full paths.

**Flow:**
1. Take snapshot before action runs
2. Action mutates state, returns scope (paths to diff)
3. Pass scope to DeepDiff's `include_paths` parameter
4. DeepDiff only checks specified paths but returns full paths in output
5. Return Delta with correct paths for subscribers

```python
from deepdiff import DeepDiff, Delta
import copy

def _process_action(self, handler, payload) -> Delta:
    """Run action and return Delta representing all changes."""
    snapshot = copy.deepcopy(self._state)
    scope = handler(self._state, payload)

    if not scope:  # no-op
        return Delta({})

    # "." means full diff, otherwise restrict to specified paths
    include = None if "." in scope else list(scope)
    diff = DeepDiff(snapshot, self._state, include_paths=include)
    return Delta(diff)
```

**Why `include_paths` instead of subtree diffing:**
- Subtree diffing produces paths relative to subtree root (e.g., `root` instead of `root.language`)
- `include_paths` diffs full objects but only checks specified paths
- Results in correct full paths for subscribers (e.g., `['language']` not `[]`)
- ~70x faster than full diff, only ~2x slower than subtree diff (see benchmarks)

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
- [x] Decided: Delta for change representation
- [x] Decided: `include_paths` for scoped diffing (replaces glom-based subtree diffing)
- [x] TODO: Implement `_process_action()` in Store
  - [x] Add imports: `from deepdiff import DeepDiff, Delta`
  - [x] Add method `_process_action(self, handler: Callable, payload: Any) -> Delta`
  - [x] Call `snapshot()` before action runs
  - [x] Call action handler, capture returned scope
  - [x] Handle empty scope (no-op) → return `Delta({})`
  - [x] Use `include_paths=list(scope)` for scoped diff, `None` for full diff (".")
  - [x] Write unit test: action returns specific path, verify Delta contains change
  - [x] Write unit test: action returns `no_op`, verify empty Delta
  - [x] Write unit test: action returns `full_diff`, verify full state diffed
  - [x] Write benchmark tests: verify scoped diff is >10x faster than full diff
- [x] TODO: Add `deepdiff` to dependencies
  - [x] Add to `pyproject.toml` under `[project.dependencies]`
  - [x] Run `make setup` to install

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
- [x] TODO: Update `_bind_actions()` to use new flow
  - [x] Rename `_bind_actions()` to `_bind_actions()` (or keep name, update internals)
  - [x] Change bound function signature from `-> S` to `-> None`
  - [x] Replace direct `action.handler(self.get(), payload)` with `self._process_action()`
  - [x] Add call to `self._notify_subscribers(delta)` after processing (stub added, full impl in Section 5)
  - [x] Update `_actions` dict type annotation: `dict[str, Callable[..., None]]`
  - [x] Update existing example code in `transcription_with_store.py` (no changes needed - example already worked)
  - [x] Run `make types` to verify no type errors

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
- [x] TODO: Implement `subscribe()` and `_notify_subscribers()`
  - [x] Add `_subscribers: list[Callable[[Delta], None]]` to Store `__init__`
  - [x] Implement `subscribe(self, callback) -> Callable[[], None]`
  - [x] Return lambda that removes callback from list
  - [x] Implement `_notify_subscribers(self, delta: Delta) -> None`
  - [x] Early return if `not delta.diff` (empty delta)
  - [x] Iterate subscribers, call each with delta
  - [x] Write unit test: subscribe, trigger action, verify callback received Delta
  - [x] Write unit test: unsubscribe, trigger action, verify callback NOT called
  - [x] Write unit test: no-op action does not trigger subscribers
- [ ] Open: Add path-based subscription helpers? (e.g., `subscribe_path("user.*", cb)`)

---

### 6. Async Actions

**Problem:** Can't snapshot during an await—other actions could run between the snapshot and the mutation, making the snapshot stale and change detection incorrect.

**Solution:** Async functions are **read-only**. They return a result that gets passed to a **sync handler** (`on_success`) which performs the actual state mutation with proper snapshot/diff/notify flow.

#### Key Decisions

1. **Hooks are handler functions, not Action objects or strings**
   - `on_success` and `on_error` must be functions with signature `(state: S, payload: T) -> frozenset[str]`
   - This is the same signature as sync action handlers
   - Provides static type checking: the async function's return type must match `on_success`'s payload type
   - NOT strings (no runtime lookup) and NOT Action objects (those are class attributes)

2. **Bound async actions return `None`**
   - Consistent with sync bound actions
   - State changes flow through subscribers via Delta objects
   - Prevents stale state from floating around in variables

3. **Discovery via `AsyncAction` class**
   - Similar to `Action`, create an `AsyncAction` class to wrap async handlers
   - `AsyncAction` stores: the async handler, `on_success` handler, and optional `on_error` handler
   - Discovered and bound in `_bind_actions()` via a helper `_bind_async_actions()` method

4. **No `on_start` hook** (YAGNI for LLM apps)
   - LLM apps are often headless/agent-to-agent
   - Streaming responses don't need loading spinners
   - If needed, call a sync action manually before the async action

#### Usage Example

```python
# Define handlers as external functions for reuse and type checking
def set_transcription(state: AppState, text: str) -> frozenset[str]:
    state.transcription = text
    return frozenset({"transcription"})

def set_error(state: AppState, error: Exception) -> frozenset[str]:
    state.error = str(error)
    return frozenset({"error"})

class TranscriptionStore(Store[AppState]):
    # Can also use handler as standalone sync action
    set_transcription = Store.action(set_transcription)

    # Async action - hooks are handler functions, not Action objects
    @Store.async_action(on_success=set_transcription, on_error=set_error)
    @staticmethod
    async def transcribe(state: AppState, url: str) -> str:
        # Read-only access to state, no mutations here
        text = await api.transcribe(url)
        return text  # This becomes payload for on_success

# Usage
store = TranscriptionStore(AppState(...))
await store.transcribe("http://example.com/audio.mp3")  # Returns None
# State is updated, subscribers notified with Delta
```

#### Internal Flow

```python
async def _run_async_action(self, async_fn, on_success, on_error, payload):
    try:
        # Async work (read-only, no snapshot taken here)
        result = await async_fn(self._state, payload)
        # Sync mutation with full snapshot → mutate → diff → notify flow
        delta = self._process_action(on_success, result)
        self._notify_subscribers(delta)
    except Exception as e:
        if on_error:
            delta = self._process_action(on_error, e)
            self._notify_subscribers(delta)
        else:
            raise
```

#### Implementation Status

- [x] Decided: two hooks (`on_success`, `on_error`)
- [x] Decided: hooks are handler functions `(state, payload) -> frozenset[str]`, not strings or Actions
- [x] Decided: bound async actions return `None`
- [x] Decided: no `on_start` (YAGNI for LLM apps)
- [x] Decided: use `AsyncAction` class, discovered in `_bind_actions()` via `_bind_async_actions()`

- [x] TODO: Create `AsyncAction` class
  - [x] Create `src/agent_lib/store/AsyncAction.py`
  - [x] Generic class `AsyncAction[PL, St, R]` where PL=payload, St=state, R=result
  - [x] Store: `handler` (async fn), `on_success` (handler fn), `on_error` (optional handler fn)
  - [x] `__call__` raises error if accessed on class (like `Action`)

- [x] TODO: Implement `@Store.async_action` decorator
  - [x] Full type signature:
    ```python
    @staticmethod
    def async_action[St, PL, R](
        on_success: Callable[[St, R], frozenset[str]],
        on_error: Callable[[St, Exception], frozenset[str]] | None = None
    ) -> Callable[[Callable[[St, PL], Coroutine[Any, Any, R]]], AsyncAction[PL, St, R]]:
    ```
  - [x] Decorator factory: takes hooks, returns decorator
  - [x] Decorator wraps async function `(St, PL) -> Coroutine[..., R]` and returns `AsyncAction[PL, St, R]`

- [x] TODO: Implement `_bind_async_actions()` in Store
  - [x] Called from `__init__()` after `_bind_actions()`
  - [x] Discover `AsyncAction` attributes on class
  - [x] Create bound async method that calls `_run_async_action()`
  - [x] Bound method signature: `async (payload: T) -> None`

- [x] TODO: Implement `_run_async_action()` in Store
  - [x] `async def _run_async_action(self, async_action: AsyncAction, payload: Any) -> None`
  - [x] Call `await async_action.handler(self._state, payload)` to get result
  - [x] On success: `delta = self._process_action(async_action.on_success, result)`
  - [x] Call `self._notify_subscribers(delta)`
  - [x] On exception: if `on_error`, process it; else re-raise

- [x] TODO: Write unit tests (`tests/store/test_async_action_LLM.py`)
  - [x] Test: async success path triggers `on_success`, state updated, subscribers notified
  - [x] Test: async error path triggers `on_error` when provided
  - [x] Test: async error re-raises when no `on_error`
  - [x] Test: async action returns `None`
  - [x] Test: async action can read state but mutations in async fn don't trigger diff

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
  - [ ] Research PLthon descriptor protocol (`__get__`, `__set__`)
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
Even Redux adopted Immer because writing immutable updates is tedious. In PLthon it's worse—no spread operators, `dataclasses.replace()` chains are verbose. Since we need snapshots anyway for change detection, we get the benefits of immutability (knowing what changed) without the DX cost.

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
# Generic variable names: St=state, PL=payload, R=result

# Action handler signature
(state: St, payload: PL) -> frozenset[str]

# Async handler signature (read-only, returns result for on_success)
async (state: St, payload: PL) -> R

# Subscriber signature
(delta: Delta) -> None

# Unsubscribe function
() -> None
```

### Store API (planned)

```python
class Store[St]:
    # State access
    def get(self) -> St
    def set(self, state: St) -> None

    # Subscriptions
    def subscribe(self, callback: Callable[[Delta], None]) -> Callable[[], None]

    # Decorators
    @staticmethod
    def action[St, PL](
        handler: Callable[[St, PL], frozenset[str]]
    ) -> Action[PL, St]

    @staticmethod
    def async_action[St, PL, R](
        on_success: Callable[[St, R], frozenset[str]],
        on_error: Callable[[St, Exception], frozenset[str]] | None = None
    ) -> Callable[[Callable[[St, PL], Coroutine[Any, Any, R]]], AsyncAction[PL, St, R]]
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