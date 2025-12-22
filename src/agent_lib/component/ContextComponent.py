from __future__ import annotations

from typing import Callable, Optional, Tuple


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


# Arguments: component, children, props: P
type RenderFn[P] = Callable[[ContextComponent[P], Children, P], str]


class ContextComponent[P]:
    __render: RenderFn[P]
    _delimitor: Optional[str | Tag]

    def __init__(self, render: RenderFn[P], delimitor: Optional[str | Tag]):
        self.__render = render
        self._delimitor = delimitor

    def render_children(self, children: Children) -> list[str]:

        match children:
            case None:
                return [""]
            case str() as s:
                return [s]
            case ContextComponent() as component:
                return [component(None, None)]
            case (ContextComponent() as component, grandchildren):
                return [component(grandchildren, None)]
            case list() as child_list:
                return [s for child in child_list for s in self.render_children(child)]

    def __call__(self, children: Children, props: P):
        inner = self.__render(self, children, props)
        match self._delimitor:
            case None:
                return inner
            case str() as d:
                return f"{d}{inner}{d}"
            case Tag() as t:
                return t(inner)

    def pass_props(self, props: P) -> ContextComponent[None]:
        def new_render(
            new_component: ContextComponent[None], children: Children, no_props: None
        ) -> str:
            return self.__render(self, children, props)

        return ContextComponent(new_render, self._delimitor)
