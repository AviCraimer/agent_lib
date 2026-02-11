from dataclasses import Field
from typing import Final, Sequence

from attr import field
from pydantic import InstanceOf
from agent_lib.context.CtxComponent import CtxComponent, wrap
from agent_lib.context.Props import Props
from dataclasses import field

type AttributeValue = str | int | bool | float


class TagProps(Props):
    tag: str
    line_breaks: bool = False
    attributes: dict[str, AttributeValue] = field(default_factory=dict)


class Tag(CtxComponent[TagProps]):
    _props_class = TagProps

    def __init__(self):

        def render_fn(props: TagProps):
            open_tag = Tag.tag(props, True)
            close_tag = Tag.tag(props, False)

            return wrap(
                CtxComponent.render_children(props.children, ""), (open_tag, close_tag)
            )

        self._render_fn = render_fn

    @staticmethod
    def tag(props: TagProps, open: bool):
        line_break = "\n" if props.line_breaks else ""

        slash = "" if open else "/"
        attributes: str = (
            " " + " ".join([Tag.attr(k, v) for k, v in props.attributes.items()])
            if open
            else ""
        )

        tag = f"{line_break}<{slash}{props.tag}{attributes}>{line_break}"
        return tag

    @staticmethod
    def attr(key: str, val: AttributeValue):

        match val:
            case bool():
                return f"{key}={str(val).lower()}"  # e.g., true
            case int() | float():
                return f"{key}={val}"
            case str():
                return f'{key}="{val}"'


# Some common presets

PromptTag = Tag().preset(Tag.Props(tag="prompt", line_breaks=True))

SystemTag = Tag().preset(TagProps(tag="system", line_breaks=True))

InstructionTag = Tag().preset(TagProps(tag="instruction", line_breaks=True))

EmTag = Tag().preset(TagProps(tag="em"))


if __name__ == "__main__":

    example = Tag()(
        Tag.Props(
            tag="character",
            line_breaks=True,
            attributes={"name": "Fred", "age": 45, "action": "speaking"},
        )
    )

    print(example)
