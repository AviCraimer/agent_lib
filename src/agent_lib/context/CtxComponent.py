from __future__ import annotations

from dataclasses import replace
import re
from typing import Any, Callable, Sequence, Tuple, TypeGuard, cast

from agent_lib.context.Props import Props, NoProps, JustChildren, propsclass


type RequiredChildren = CtxComponent[NoProps] | str | Sequence[Children]

type Children = RequiredChildren | None

# A delimitor is either a string or a pair of strings. The pair of strings is used when opening and closing are different.
type Delimitor = str | Tuple[str, str]


def wrap(inner: str, delimitor: Delimitor) -> str:
    match delimitor:
        case (str() as open, str() as close):
            return f"{open}{inner}{close}"
        case str() as d:
            return f"{d}{inner}{d}"


def is_children(value: Any) -> TypeGuard[Children]:
    if value is None or isinstance(value, str):
        return True
    if isinstance(value, CtxComponent) and CtxComponent.is_renderable(value):
        return True
    if isinstance(value, list):
        return all(is_children(item) for item in value)
    return False


# Arguments: The first argument is props
type RenderFn[P: Props] = Callable[[P], str]


class CtxComponent[P: Props]:
    _render_fn: RenderFn[P]
    _PropsClass: type[P]

    def __init__(self, render: RenderFn[P], props_class: type[P]):
        self._render_fn = render
        self._PropsClass = props_class  # This should be overridden for subclasses with the actual props constructor

    @classmethod
    def leaf(
        cls,
        render: Callable[[], str],
    ) -> CtxComponent[NoProps]:
        def render_fn(_: NoProps = NoProps()) -> str:
            return render()

        return CtxComponent(render_fn, NoProps)

    @classmethod
    def wrapper(cls, delimiter: Delimitor) -> CtxComponent[JustChildren]:
        def render_fn(props: JustChildren) -> str:
            return CtxComponent.render_children(props.children, delimiter)

        return CtxComponent(render_fn, JustChildren)

    @staticmethod
    def is_renderable(comp: Any) -> TypeGuard[CtxComponent[NoProps]]:
        return isinstance(comp, CtxComponent) and comp._PropsClass == NoProps

    @staticmethod
    def render_children(children: Children, list_item_delimitor: Delimitor = "") -> str:
        render_list: list[str]
        match children:
            case None:
                render_list = [""]
            case str() as s:
                render_list = [s]
            case CtxComponent() as component:
                render_list = [component.render(NoProps())]
            case _:
                render_list = [
                    CtxComponent.render_children(child) for child in children
                ]
        # Note to self: I may remove the delimitor entirelty for now it's just here for reference.
        return "".join([wrap(s, list_item_delimitor) for s in render_list])

    def render(self, props: P = NoProps()) -> str:
        return self._render_fn(props)

    def pass_props(self, props: P | Children) -> CtxComponent[NoProps]:
        if is_children(props):
            try:
                _props: P = self._PropsClass(children=props)
            except:
                raise ValueError(
                    "Could not construct props object from the passed children object. You may need to construct the full props object and pass it in."
                )
        else:
            props = cast(P, props)
            _props = props

        def new_render(_: NoProps) -> str:
            return self.render(_props)

        return CtxComponent[NoProps](new_render, NoProps)

    def preset(self, props: P) -> CtxComponent[JustChildren]:
        """This method lets you pass all the props other than children. Useful to avoid repeatly configuring component instances which vary only in their children."""

        def new_render(children_props: JustChildren) -> str:
            return self.render(replace(props, children=children_props.children))

        return CtxComponent[JustChildren](new_render, JustChildren)

    def __call__(self, props: P | Children) -> CtxComponent[NoProps]:
        return self.pass_props(props)

    def __str__(self) -> str:
        """Render the component to a string if it requires no props.

        Raises:
            TypeError: If the component requires props to render.
        """
        if self._PropsClass is NoProps:
            return self.render(NoProps())  # type: ignore[arg-type]
        raise TypeError(
            f"Cannot convert CtxComponent to string: requires {self._PropsClass.__name__} props. "
            "Use .render(props) or .pass_props(props) first."
        )


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


PromptTag = Tag().preset(TagProps(tag="prompt", line_breaks=True))

SystemTag = Tag().preset(TagProps(tag="system", line_breaks=True))


@propsclass
class CodeBlockProps(Props):
    language: str


class CodeBlock(CtxComponent[CodeBlockProps]):
    _PropsClass = CodeBlockProps

    def __init__(self):

        def render_fn(props: CodeBlockProps):

            code = CodeBlock.strip_code_block(
                CtxComponent.render_children(props.children, "")
            )

            return f"```{props.language}\n{code}\n```"

        self._render_fn = render_fn

    @staticmethod
    def strip_code_block(code: str) -> str:
        """Strip existing code block fences if present."""
        stripped = code.strip()

        pattern = r"^```[a-zA-Z0-9]*\n(.*)\n```$"
        match = re.match(pattern, stripped, re.DOTALL)

        if match:
            return match.group(1)

        return code


@propsclass
class ItemsProps(Props):
    """An example of a higher-order component, which just means a component that takes another component as a prop and does stuff with it."""

    item_wrapper: CtxComponent[JustChildren]
    last_wrapper: CtxComponent[JustChildren] | None = None
    first_wrapper: CtxComponent[JustChildren] | None = None
    children: list[Children] | None = (
        None  # We restrict children, if present to being a list.
    )


def Items_render_fn(props: ItemsProps) -> str:

    if props.children:  # We intentionlly exclude the empty list for this case.
        rest = props.children
        first_wrapper = (
            props.first_wrapper
            if props.first_wrapper
            else (
                props.last_wrapper
                if props.last_wrapper and len(rest) == 1
                else props.item_wrapper
            )
        )

        last_wrapper = (
            props.last_wrapper
            if props.last_wrapper and len(rest) > 1
            else props.item_wrapper
        )

        first: str = first_wrapper(rest[0]).render()
        rest = rest[1:]

        last: str = last_wrapper(rest[-1]).render() if rest else ""

        rest = rest[:-1]

        rendered_rest = (
            "".join([props.item_wrapper(c).render() for c in rest]) if rest else ""
        )

        return "".join([first, rendered_rest, last])
    else:
        return ""


Items = CtxComponent(Items_render_fn, ItemsProps)


Paragraph = CtxComponent.wrapper(("", "\n\n"))

Paragraphs = Items.preset(
    ItemsProps(item_wrapper=Paragraph, last_wrapper=CtxComponent.wrapper(""))
)


if __name__ == "__main__":
    h1_tag = Tag().preset(TagProps(tag="h1"))

    print(h1_tag("My Title").render())

    system_prompt_tag = Tag().preset(TagProps(tag="system", line_breaks=True))

    example_sys_prompt = system_prompt_tag(
        [
            h1_tag(["Important Instructions", " for you.", None]),
            "\nYou are a nice person!",
        ]
    )
    print(example_sys_prompt.render())

    # Testing code block

    md_block = CodeBlock().preset(CodeBlockProps(language="markdown"))

    md_ex1 = md_block("# My Title").render()
    print(md_ex1)

    # Test idemnopotence
    print(md_ex1 == md_block(md_ex1).render())

    # Test with Items
    print(
        md_block(
            Paragraphs(
                [
                    "# My Title",
                    "My first paragraph",
                    "## Another title",
                    "A second paragraph",
                ]
            )
        ).render()
    )
