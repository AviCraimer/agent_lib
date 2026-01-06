from __future__ import annotations

from dataclasses import dataclass

from typing import Any, Callable, Tuple, TypeGuard, cast

from agent_lib.component.Props import Props, NoProps, JustChildren


type RequiredChildren = CtxComponent[NoProps] | str | list[Children]

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
    if isinstance(value, CtxComponent) and value.props_bound:
        return True
    if isinstance(value, list):
        return all(is_children(item) for item in value)
    return False


# Arguments: The first argument is props
type RenderFn[P: Props] = Callable[[P], str]


class CtxComponent[P: Props]:
    _render_fn: RenderFn[P]
    _props_bound: bool
    _PropsClass: type[P]

    def __init__(
        self, render: RenderFn[P], props_class: type[P], props_bound: bool = False
    ):
        self._render_fn = render
        self._props_bound = props_bound
        self._PropsClass = props_class  # This should be overridden for subclasses with the actual props constructor

    @classmethod
    def leaf(
        cls,
        render: Callable[[], str],
    ) -> CtxComponent[NoProps]:
        def render_fn(_: NoProps = NoProps()) -> str:
            return render()

        return CtxComponent(render_fn, NoProps, props_bound=True)

    @classmethod
    def wrapper(
        cls,
    ) -> CtxComponent[JustChildren]:
        def render_fn(props: JustChildren) -> str:
            return CtxComponent.render_children(props.children)

        return CtxComponent(render_fn, JustChildren)

    @property
    def props_bound(self) -> bool:
        return self._props_bound

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
            case list() as child_list:
                render_list = [
                    CtxComponent.render_children(child) for child in child_list
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
                    "Could not construct props object from the passed children object. You may need to construct the full props object and passs it in."
                )
        else:
            props = cast(P, props)
            _props = props

        def new_render(_: NoProps) -> str:
            return self.render(_props)

        return CtxComponent[NoProps](new_render, NoProps, props_bound=True)

    def __call__(self, props: P | Children) -> CtxComponent[NoProps]:
        return self.pass_props(props)


@dataclass(frozen=True)
class TagProps(Props):
    children: Children
    line_breaks: bool = False


class Tag(CtxComponent[TagProps]):
    _PropsClass = TagProps

    def __init__(self, tag: str):
        self.tag = tag

        def render_fn(props: TagProps):
            open_tag = self.get_tag(props, True)
            close_tag = self.get_tag(props, False)
            return wrap(
                CtxComponent.render_children(props.children, ""), (open_tag, close_tag)
            )

        self._render_fn = render_fn
        self._props_bound = False  # Once props are bound it is no longer a Tag component but becomes CtxComponent[NoProps].
        # Question: Perhaps for debugging we need to remember the name of the component class that was used before the props were bound?

    def get_tag(self, props: TagProps, open: bool):
        line_break = "\n" if props.line_breaks else ""
        slash = "" if open else "/"
        tag = f"{line_break}<{slash}{self.tag}>{line_break}"
        return tag


# class CodeBlock:
#     def __init__(self, language: str):
#         self.language = language

#     @property
#     def open(self):
#         return f"\n```{self.language}\n"

#     @property
#     def close(self):
#         return f"\n```\n"

#     def __call__(self, inner: str) -> str:
#         inner = inner.strip()
#         return f"{self.open}{inner}{self.close}"


if __name__ == "__main__":
    h1_tag = Tag("h1")

    print(h1_tag("My Title").render())

    system_prompt_tag = Tag("system")
    example_sys_prompt = system_prompt_tag(
        TagProps(
            children=[
                h1_tag(["Important Instructions", " for you.", None]),
                "\nYou are a nice person!",
            ],
            line_breaks=True,
        )
    )
    print(example_sys_prompt.render())
