from __future__ import annotations

from typing import Any, Callable, Literal, Optional, Tuple, cast


type Children = ContextComponent[None] | str | None | list[Children]


class Tag:
    def __init__(self, tag: str, line_breaks: bool):
        self.tag = tag
        self.line_breaks = line_breaks

    @property
    def open(self):
        return f"<{self.tag}>"

    @property
    def close(self):
        return f"</{self.tag}>"

    def __call__(self, inner: str) -> str:
        if self.line_breaks:
            return f"\n{self.open}\n{inner}\n{self.close}\n"
        else:
            return f"{self.open}{inner}{self.close}"


class CodeBlock:
    def __init__(self, language: str):
        self.language = language

    @property
    def open(self):
        return f"\n```{self.language}\n"

    @property
    def close(self):
        return f"\n```\n"

    def __call__(self, inner: str) -> str:
        inner = inner.strip()
        return f"{self.open}{inner}{self.close}"


type Delimitor = Optional[str | Tag | CodeBlock | Tuple[str, str]]


def wrap(inner: str, delimitor: Delimitor) -> str:
    match delimitor:
        case None:
            return inner
        case (str() as open, str() as close):
            return f"{open}{inner}{close}"
        case str() as d:
            return f"{d}{inner}{d}"
        case Tag() as t:
            return t(inner)
        case CodeBlock() as b:
            return b(inner)


def is_children(value: Any) -> bool:
    if value is None or isinstance(value, str):
        return True
    if isinstance(value, ContextComponent) and value.props_bound:
        return True
    if isinstance(value, list):
        return all(is_children(item) for item in value)
    return False


def get_children_from_props(props: Any) -> Children:
    # Handle dict-like props
    if isinstance(props, dict):
        if "children" in props and is_children(props["children"]):
            return cast(Children, props["children"])
    # Handle class instances
    elif hasattr(props, "children") and is_children(props.children):
        return cast(Children, props.children)
    return None


# Arguments: The first argument is props, the second argument is the string of the rendred children.
type RenderFn[P = None] = Callable[[P, str], str]


class ContextComponent[P]:
    _render_fn: RenderFn[P]
    _delimitor: Delimitor
    _list_delimitor: Delimitor
    _props_bound: bool

    def __init__(
        self,
        render: RenderFn[P],
        delimitor: Delimitor = None,
        list_delimitor: Delimitor = None,
        props_bound: bool = False,
    ):
        self._render_fn = render
        self._delimitor = delimitor
        self._list_delimitor = list_delimitor
        self._props_bound = props_bound

    @classmethod
    def leaf(
        cls,
        render: Callable[[], str],
        delimitor: Delimitor = None,
    ) -> ContextComponent[None]:
        def render_fn(_: None, __: str) -> str:
            return render()

        return ContextComponent(render_fn, delimitor, None, props_bound=True)

    @classmethod
    def wrapper(
        cls,
        delimitor: Delimitor = None,
        list_delimitor: Delimitor = None,
    ) -> ContextComponent[JustChildren]:
        def render_fn(_: JustChildren, children: str) -> str:
            return children

        return ContextComponent(render_fn, delimitor, list_delimitor)

    @property
    def props_bound(self):
        return self._props_bound

    def render_children(self, children: Children) -> str:
        render_list: list[str]
        match children:
            case None:
                render_list = [""]
            case str() as s:
                render_list = [s]
            case ContextComponent() as component:
                render_list = [component.render(None)]
            case list() as child_list:
                render_list = [self.render_children(child) for child in child_list]
        return "".join([wrap(s, self._list_delimitor) for s in render_list])

    def _render(self, props: P = None, to_wrap: bool = True) -> str:
        inner = self._render_fn(
            props, self.render_children(get_children_from_props(props))
        )
        return wrap(inner, self._delimitor) if to_wrap else inner

    def render(self, props: P = None) -> str:
        return self._render(props, to_wrap=True)

    def pass_props(self, props: P) -> ContextComponent[None]:
        def new_render(no_props: None, _: str) -> str:
            return self._render(props, to_wrap=False)

        return ContextComponent[None](
            new_render, self._delimitor, None, props_bound=True
        )

    def __call__(self, props: P) -> ContextComponent[None]:
        return self.pass_props(props)


type JustChildren = dict[Literal["children"], Children]
