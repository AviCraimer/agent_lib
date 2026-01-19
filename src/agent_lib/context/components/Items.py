# Items is used for a formatted list with a custom delimiter around each item in the list. It optionally allows special treatment of first and last items.
from agent_lib.context.CtxComponent import Children, CtxComponent
from agent_lib.context.Props import Props, propsclass, JustChildren


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
