# agent_lib Store — Future Work

See [doc.md](doc.md) for Store documentation.

## 1. Implement Agents

This is the next big task.


### Design Decisions

When we are thinking about how to make a complex app with multiple agents, it might be helpful to have a way for stores to be compositional.
  What I mean is that a store instance may need to be built out of other store instances. For example, If you have an app with three agents,
  you might have a part of the store for each agent, and a shared part of the store. In that case, you'd want to be able to build the
  agent-specific stores with the individual agenets and then assemble the peices together into the whole app. You need to be able to mix and
  match. Is this kind of design pattern something we can just do with out existing set up, or is something missing?

#### State-Triggered Execution

Agents are triggered by state changes, not direct calls. This enables:
- Decoupled agent handoff (Agent A signals via state, Agent B reacts)
- Single source of truth for "who should act"
- Observable execution flow

**Trigger pattern:**

```python
@dataclass
class ModelConfig:
    """Base config - all agent configs must have context field."""
    context: str = ""

@dataclass
class AgentState[Config: ModelConfig]:
    should_act: bool = False
    currently_availale_actions: set(str) # The currently availabe actions. This can change dynamically based on agent actions. Must be a subset of availabe_actions.
    availabe_actions: set(str) # Names of async or sync actions the Store.  This cannot change based on agent actions. It allows setting hard safety limits on what an agent can do.
    init_config: Config  # Does not change
    current_config: Config  # can be updated by actions.
```

There could be an initializer for AgentState, where you pass in the agent instance and it uses this to populate the initial state. What do you think?

```python
@dataclass
class AgentsState:
    """Each app defines its own AgentsState with typed agent fields."""
    translator: AgentState[TranslatorConfig]
    summarizer: AgentState[SummarizerConfig]

@dataclass
class AppState:
    agents: AgentsState
    # ... shared state
```

Access: `state.agents.translator.should_act = True`

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
class Agent[Config: ModelConfig]:
    # Static context - rendered once at init, good for prompt caching
    static_context: str

    # Dynamic context - ContextComponent[None] wired to state
    context: ContextComponent[None]

    # Available actions (by name)
    actions: set[str]
    generating_function: Coroutine[[Config], str]

    @staticmethod
    get_agent_state: Callable[[],AgentState[Config]]

    # Text generation (provider-specific)
    # An agent has an async text generating function. This has a generic argument Config which includes any prompts, message history, etc. I'm not going to specify any common format for this because LLM providers have different interfaces and they are changing all the time. But Config should have a field called "context" which can be mapped to the modle providor API anyway the developer likes.
    async def generate(self, config: Config ) -> str:
        config = copy(config)
        config.context = self.context.render()
        retrun self.generating_function(config)



    # Execute the agent. Agent executes until its should act is set to false.
    exec(self):
        get_agent_state = self.get_agent_state

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

#### Agent receives actions

Agent receives bound actions (from AIApp during wiring — see Section 2):

```python
class Agent[Config: ModelConfig]:
    actions: dict[str, BoundAction[Any]]  # name -> bound action, set by AIApp
```

#### parse_result Implementation

```python
import json
from inspect import iscoroutinefunction

def parse_result(self, result: str) -> tuple[BoundAction[Any], Any]:
    """Parse LLM output to extract action name and payload."""
    # Assumes LLM returns JSON like: {"action": "search_tool", "payload": {"query": "..."}}
    parsed = json.loads(result)
    action_name = parsed["action"]
    payload = parsed["payload"]

    if action_name not in self.actions:
        raise ValueError(f"Unknown action: {action_name}")
    if action_name not in get_agent_state().currently_available_actions:
        raise ValueError(f"Action not currently available: {action_name}")

    return self.actions[action_name], payload

# In exec loop, check if async:
action, payload = self.parse_result(res)
if iscoroutinefunction(action):
    await action(payload)
else:
    action(payload)
```

#### Error Handling in exec()

```python
async def exec(self, get_agent_state: Callable[[], AgentState]):
    while get_agent_state().should_act:
        try:
            res = await self.generate(get_agent_state().current_config)
            if not get_agent_state().should_act:
                break
            action, payload = self.parse_result(res)
            if iscoroutinefunction(action):
                await action(payload)
            else:
                action(payload)
        except json.JSONDecodeError:
            # LLM returned invalid JSON - could retry or set error state
            pass
        except ValueError as e:
            # Unknown/unavailable action - could retry or set error state
            pass
```

#### Type Correction

```python
# Correct type for generating_function
generating_function: Callable[[Config], Coroutine[Any, Any, str]]

# Not: Coroutine[[Config], str] (that's the return value, not the function)
```



---

## 2. AIApp Class

Orchestration layer that wires Agents to the Store.

```python
class AIApp[S]:
    store: Store[S]
    agents: dict[str, Agent]
    _tasks: list[asyncio.Task]

    def __init__(self, store: Store[S], agents: list[Agent]):
        self.store = store
        self.agents = {agent.name: agent for agent in agents}
        self._tasks = []
        self._validate()
        self._wire_agents()

    def _validate(self):
        """Validate that all agents have valid action references, etc."""
        for name, agent in self.agents.items():
            # Check agent's actions exist in store
            store_actions = set(self.store.get_actions().keys())
            if not agent.action_names.issubset(store_actions):
                missing = agent.action_names - store_actions
                raise ValueError(f"Agent '{name}' references unknown actions: {missing}")

    def _wire_agents(self):
        """Set get_agent_state selector and actions on each agent."""
        for name, agent in self.agents.items():
            # Create closure for this agent's state selector
            def make_selector(agent_name: str):
                return lambda: getattr(self.store.get().agents, agent_name)
            agent.get_agent_state = make_selector(name)
            agent.actions = self.store.get_actions(*agent.action_names)

    async def run(self):
        """Start all agent exec loops."""
        for agent in self.agents.values():
            task = asyncio.create_task(agent.exec())
            self._tasks.append(task)
        # Wait for all (they run forever until shutdown)
        await asyncio.gather(*self._tasks)

    async def shutdown(self):
        """Stop all agent loops."""
        for agent in self.agents.values():
            agent.running = False  # Agent checks this in exec loop
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
```

**Wiring happens at init:**
- `get_agent_state` selector set on each Agent
- Bound actions provided to each Agent
- No subscriber-based triggering — agents poll via their exec loop

**Agent exec loop (polling):**
```python
async def exec(self):
    self.running = True
    while self.running:
        if not self.get_agent_state().should_act:
            await asyncio.sleep(0.1)  # Poll interval
            continue
        # ... do work
```

**Orchestration rules (what subscribers are for):**

Subscribers handle algorithmic agent triggering — react to state and set `should_act`:

```python
class AIApp[S]:
    orchestration_rules: list[Callable[[S, Delta], None]]

    def _setup_orchestration(self):
        def on_change(delta: Delta):
            state = self.store.get()
            for rule in self.orchestration_rules:
                rule(state, delta)
        self.store.subscribe(on_change)

# Example rules:
def trigger_summarizer_on_new_doc(state: AppState, delta: Delta) -> None:
    """When new document arrives, summarizer should act."""
    if 'documents' in str(delta.diff):
        state.agents.summarizer.should_act = True

def chain_translator_after_summary(state: AppState, delta: Delta) -> None:
    """When summary is ready, trigger translator."""
    if 'summary' in str(delta.diff) and state.summary:
        state.agents.translator.should_act = True
```

**Separation of concerns:**
- **Polling loop**: Agent checks if it should act
- **Orchestration rules**: React to state changes, flip `should_act` flags
- **Agent logic**: What to do when acting (generate, parse, call actions)

**Responsibilities:**
- Validate agent/store compatibility at startup
- Wire `get_agent_state` selectors and actions to agents
- Set up orchestration rules (subscribers)
- Start/stop all agent exec loops
- Optional persistance of state to file, database, etc.
- Graceful shutdown

**Open questions:**
- Poll interval: configurable per agent?
- Should AIApp own the Store, or receive it?
- How to handle agent-specific error callbacks?
- Should orchestration rules be passed to AIApp init, or defined elsewhere?

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