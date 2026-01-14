from dataclasses import dataclass
from agent_lib.context.CtxComponent import CtxComponent
from agent_lib.context.Props import JustChildren, NoProps, Props


def render_children(props: JustChildren) -> str:
    return CtxComponent.render_children(props.children)


class SystemPromp(CtxComponent[JustChildren]):
    _PropsClass = JustChildren
    _render_fn = render_children


class UserRoleMsgCtx(CtxComponent[NoProps]):
    def __init__(self, context_component: CtxComponent[NoProps]):
        def render_fn(props: NoProps):
            return context_component.render()

        super().__init__(render_fn, NoProps)


class AgentRoleMsgCtx(CtxComponent[NoProps]):
    def __init__(self, context_component: CtxComponent[NoProps]):
        def render_fn(props: NoProps):
            return context_component.render()

        super().__init__(render_fn, NoProps)


type ChatMsgCtx = UserRoleMsgCtx | AgentRoleMsgCtx


@dataclass
class LLMContext:
    messages: list[ChatMsgCtx]
    system_prompt: CtxComponent[NoProps]
