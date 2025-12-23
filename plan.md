# agent_lib Store — Future Work

See [doc.md](doc.md) for Store documentation.

## 1. Implement Agents

This is the next big task.


### Design Decisions

#### Tools = Async Actions

No new primitive needed. The `@Store.async_action` pattern already supports tools:

```python
@Store.async_action(on_success=handle_search_result)
@staticmethod
async def search_tool(state: AppState, query: str) -> SearchResult:
    return await external_search_api(query)  # Tool call (async, external)

def handle_search_result(state: AppState, result: SearchResult) -> frozenset[str]:
    state.search_results = result  # Sync state update
    return frozenset({"search_results"})
```

A "tool" is just an async action with descriptive metadata (name, description) that gets rendered into the agent's context. The async handler does the external work, `on_success` updates state.

#### State-Triggered Execution

Agents are triggered by state changes, not direct calls. This enables:
- Decoupled agent handoff (Agent A signals via state, Agent B reacts)
- Single source of truth for "who should act"
- Observable execution flow

**Trigger pattern:**

```python
@dataclass
class AgentState[Config]:
    should_act: bool = False
    currently_availale_actions: set(str) # The currently availabe actions. This can change dynamically based on agent actions. Must be a subset of availabe_actions.
    availabe_actions: set(str) # Names of async or sync actions the Store.  This cannot change based on agent actions. It allows setting hard safety limits on what an agent can do.
    init_config: Config  # Does not change
    current_config: Config  # can be updated by actions.
```

There could be an initializer for AgentState, where you pass in the agent instance and it uses this to populate the initial state. What do you think?

```python
@dataclass
class AppState:
    agents: {
        agent_a: AgentState
        agent_b: AgentState
    }

    # ... shared state
```

Flow:
1. Something sets `state.agent_a.should_act = True`
2. Subscriber fires, Agent A runs
3. Agent A finishes, sets `should_act = False`

Natural debouncing: if something tries to trigger mid-run, `should_act` is already `True`, so no state change, no duplicate trigger.

#### Single Trigger Per Agent

**Design constraint:** Each agent has exactly one way to be triggered (its `should_act` flag).

This is consistent with the Store philosophy:
- Predictable execution flow
- Easy to reason about "why did this agent run?"
- Agent behavior varies based on *state*, not *how it was triggered*

The agent sees state indirectly through its context mapping. Different state → different context → different behavior. But the trigger mechanism is always the same.

```python
# Good: one trigger, behavior varies by state
state.translator.should_act = True  # Always triggered this way
# Agent sees context derived from state.document, state.target_language, etc.

# Avoid: multiple trigger paths for same agent
state.translator.translate_now = True   # Don't do this
state.translator.urgent_translate = True  # Or this
```

#### Agent Components

```python
class Agent[Config]:
    # Static context - rendered once at init, good for prompt caching
    static_context: str

    # Dynamic context - ContextComponent[None] wired to state
    context: ContextComponent[None]

    # Available actions (by name)
    actions: set[str]
    generating_function: Coroutine[[Config], str]

    # Text generation (provider-specific)
    # An agent has an async text generating function. This has a generic argument Config which includes any prompts, message history, etc. I'm not going to specify any common format for this because LLM providers have different interfaces and they are changing all the time. But Config should have a field called "context" which can be mapped to the modle providor API anyway the developer likes.
    async def generate(self, config: Config ) -> str:
        config = copy(config)
        config.context = self.context.render()
        retrun self.generating_function(config)



    # Execute the agent. Agent executes until its should act is set to false.
    exec(self, get_agent_state: Callable[[], AgentState]):

        while get_agent_state().should_act:
            res = await self.generate(get_agent_state().current_config)
            if not get_agent_state().should_act: break
            action, payload = self.parse_result(str)
            if # if action is async:
                await action(payload)
            else: action(payload)

    parse_result[T](str) -> (BoundAction[T], T): ...
```

Tools are just async actions with metadata. A `ToolsContext` component can render available tools into the agent's context, pulling tool info from state if needed for dynamic tool sets.



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

### Path-based Subscription Helpers

Consider adding convenience methods for path-based filtering:

```python
store.subscribe_path("user.*", callback)  # Only notified for user.* changes
```

**Status:** Deferred — current approach (filter in subscriber) is flexible enough.

### Performance Optimization

Currently we deepcopy on every action. Potential optimization: only deepcopy when `self._subscribers` is non-empty. If no one's listening for changes, skip the snapshot/diff overhead.

**Status:** Deferred until profiling shows this is a bottleneck.