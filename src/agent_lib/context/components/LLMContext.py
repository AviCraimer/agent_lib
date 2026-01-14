from agent_lib.context.CtxComponent import CtxComponent
from agent_lib.context.Props import JustChildren, NoProps, Props


def render_children(props: JustChildren) -> str:
    return CtxComponent.render_children(props.children)


class SystemPromp(CtxComponent[JustChildren]):
    _PropsClass = JustChildren
    _render_fn = render_children


class UserRoleMsgCtx(CtxComponent[NoProps]):
    def __init__(
        self, context_component: CtxComponent[NoProps], role_name: str = "user"
    ):
        def render_fn(props: NoProps):
            return context_component.render()

        self.role_name = role_name
        super().__init__(render_fn, NoProps)


class AgentRoleMsgCtx(CtxComponent[NoProps]):
    def __init__(
        self, context_component: CtxComponent[NoProps], role_name: str = "assistant"
    ):
        def render_fn(props: NoProps):
            return context_component.render()

        super().__init__(render_fn, NoProps)


type ChatMsgCtx = UserRoleMsgCtx | AgentRoleMsgCtx


class LLMContextProps(Props):
    children: list[ChatMsgCtx]
    system_ctx: CtxComponent[NoProps]
