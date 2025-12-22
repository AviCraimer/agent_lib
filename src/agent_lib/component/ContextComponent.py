from __future__ import annotations

from typing import Any, Callable, Optional, Tuple, cast


type Children = ContextComponent[None] | Tuple[
    ContextComponent[None], Children
] | str | None | list[Children]


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


type Delimitor = Optional[str | Tag | Tuple[str, str]]


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


def is_children(value: Any) -> bool:
    if value is None or isinstance(value, str):
        return True
    if isinstance(value, ContextComponent) and value.props_bound:
        return True
    if isinstance(value, tuple) and len(value) == 2:
        first, second = value
        return (
            isinstance(first, ContextComponent)
            and first.props_bound
            and is_children(second)
        )
    if isinstance(value, list):
        return all(is_children(item) for item in value)
    return False


# Arguments: component, children, props: P
type RenderFn[P = None] = Callable[[ContextComponent[P], Children, P], str]


class ContextComponent[P]:
    __render: RenderFn[P]
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
        self.__render = render
        self._delimitor = delimitor
        self._list_delimitor = list_delimitor
        self._props_bound = props_bound

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
                render_list = [component(None, None)]
            case (ContextComponent() as component, grandchildren):
                render_list = [component(grandchildren, None)]
            case list() as child_list:
                render_list = [self.render_children(child) for child in child_list]
        return "".join([wrap(s, self._list_delimitor) for s in render_list])

    def __rshift__(self, children: Children):
        return self.render_children(children)

    def __call__(self, children: Children, props: P):
        inner = self.__render(self, children, props)
        return wrap(inner, self._delimitor)

    def pass_props(self, props: P) -> ContextComponent[None]:
        def new_render(
            new_component: ContextComponent[None], children: Children, no_props: None
        ) -> str:
            return self.__render(self, children, props)

        return ContextComponent(
            new_render, self._delimitor, self._list_delimitor, props_bound=True
        )

    def _get_children_from_props(self, props: P) -> Children:
        if hasattr(props, "children") and is_children(props.children):
            return cast(Children, props.children)
        return None

    def __getitem__(
        self, props: P
    ) -> ContextComponent[None] | Tuple[ContextComponent[None], Children]:
        comp = self.pass_props(props)
        children = self._get_children_from_props(props)
        if children is not None:
            return (comp, children)
        return comp
