from __future__ import annotations

from dataclasses import replace

from typing import Any, Callable, Sequence, Tuple, TypeGuard, cast

from agent_lib.context.Props import Props, NoProps, JustChildren
from agent_lib.util.class_property import ClassPropertyMetaClass, class_property

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


class CtxComponent[P: Props](metaclass=ClassPropertyMetaClass):
    _render_fn: RenderFn[P]
    _props_class: type[P]
    name: str = __name__
    # This should be overridden for subclasses with the actual props constructor

    @class_property
    def Props(cls) -> type[P]:
        """We use a read-only class property to access the props class publically.
        This avoids the need to import props classes separately.
        Note for Future: In the future Python my add support for unpacking the keyword arguments of dataclasses. Currently, this is a gap in the Python static type system which necessitates using Props class explicitly to construct the props rather than simply passing along the keywork arguments with generic type-safety.
        """
        return cls._props_class

    def __init__(self, render: RenderFn[P], props_class: type[P]):
        self._render_fn = render
        self._props_class = props_class

    @staticmethod
    def fc[Q: Props](
        props_class: type[Q],
    ) -> Callable[[RenderFn[Q]], "CtxComponent[Q]"]:
        """Decorator to turn a render function into a CtxComponent. Note that "fc" stands for "functional component". This terminology is borrowed from the React world.
        Usage:
            class MyProps(Props):
                ...
            @CtxComponent.fc(MyProps)
            def MyComponent(props: MyProps) -> str:
                ...
        """

        def decorator(render_fn: RenderFn[Q]) -> CtxComponent[Q]:
            component = CtxComponent(render_fn, props_class)
            component.name = render_fn.__name__
            return component

        return decorator

    @staticmethod
    def leaf(render: Callable[[], str], name: str) -> CtxComponent[NoProps]:
        """This can be used for components that return string values with no props. Mainly useful if you wish to define them in one-line using a lambda function"""

        def render_fn(_: NoProps = NoProps()) -> str:
            return render()

        component = CtxComponent(render_fn, NoProps)
        component.name = name
        return component

    @staticmethod
    def wrapper(delimiter: Delimitor, name: str) -> CtxComponent[JustChildren]:
        def render_fn(props: JustChildren) -> str:
            return CtxComponent.render_children(props.children, delimiter)

        component = CtxComponent(render_fn, JustChildren)
        component.name = name

        return component

    @staticmethod
    def is_renderable(comp: Any) -> TypeGuard[CtxComponent[NoProps]]:
        return isinstance(comp, CtxComponent) and comp._props_class == NoProps

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
                _props: P = self._props_class(children=props)
            except:
                raise ValueError(
                    "Could not construct props object from the passed children object. You may need to construct the full props object and pass it in."
                )
        else:
            props = cast(P, props)
            _props = props

        def new_render(_: NoProps) -> str:
            return self.render(_props)

        component = CtxComponent[NoProps](new_render, NoProps)
        component.name = self.name
        return component

    def preset(self, props: P) -> CtxComponent[JustChildren]:
        """This method lets you pass all the props other than children. Useful to avoid repeatly configuring component instances which vary only in their children."""

        def new_render(children_props: JustChildren) -> str:
            return self.render(replace(props, children=children_props.children))

        component = CtxComponent[JustChildren](new_render, JustChildren)
        component.name = self.name
        return component

    def __call__(self, props: P | Children) -> CtxComponent[NoProps]:
        return self.pass_props(props)

    def __str__(self) -> str:
        """Render the component to a string if it requires no props.

        Raises:
            TypeError: If the component requires props to render.
        """
        if self._props_class is NoProps:
            return self.render(NoProps())  # type: ignore[arg-type]
        raise TypeError(
            f"Cannot convert CtxComponent to string: requires {self._props_class.__name__} props. "
            "Use Component.render(props) or Component(props) first."
        )


if __name__ == "__main__":
    pass
