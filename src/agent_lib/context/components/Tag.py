from agent_lib.context.CtxComponent import CtxComponent, wrap
from agent_lib.context.Props import Props, propsclass


@propsclass
class TagProps(Props):
    tag: str
    line_breaks: bool = False


class Tag(CtxComponent[TagProps]):
    _PropsClass = TagProps

    def __init__(self):

        def render_fn(props: TagProps):
            open_tag = self.get_tag(props, True)
            close_tag = self.get_tag(props, False)
            return wrap(
                CtxComponent.render_children(props.children, ""), (open_tag, close_tag)
            )

        self._render_fn = render_fn

        # Question: Perhaps for debugging we need to remember the name of the component class that was used before the props were bound?

    def get_tag(self, props: TagProps, open: bool):
        line_break = "\n" if props.line_breaks else ""
        slash = "" if open else "/"
        tag = f"{line_break}<{slash}{props.tag}>{line_break}"
        return tag


# Some common presets

PromptTag = Tag().preset(TagProps(tag="prompt", line_breaks=True))

SystemTag = Tag().preset(TagProps(tag="system", line_breaks=True))

InstructionTag = Tag().preset(TagProps(tag="instruction", line_breaks=True))
