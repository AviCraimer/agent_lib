from os import write
from agent_lib.context.components.Tag import PromptTag, SystemTag, Tag, TagProps
from agent_lib.context.CtxComponent import CtxComponent
from agent_lib.context.Props import Props, propsclass
from agent_lib.examples.exact_text_length.store import ExactLengthStore


@propsclass
class WriterProps(Props):
    user_prompt: str
    target_wordcount: int
    prev_generated_text: str | None
    current_wordcount: int | None


PreviousTextTag = Tag().preset(TagProps(tag="previous-text", line_breaks=True))


def greater_render_fn(props: WriterProps) -> str:
    if props.current_wordcount:

        greater = props.current_wordcount > props.target_wordcount
        diff = abs(props.current_wordcount - props.target_wordcount)
        return f"{diff} {"greater" if greater else "less"}"
    else:
        raise ValueError("Should not be called when current_wordcount is empty.")


GreaterLess = CtxComponent(greater_render_fn, WriterProps)


def writer_render_fn(props: WriterProps):

    instruction = f"""Your goal is to write text based on the following prompt:{PromptTag(props.user_prompt)}The generated text should have a wordcount of exactly {props.target_wordcount}. No other text should be generated."""

    if props.prev_generated_text and props.current_wordcount:
        instruction += f"""\n\nYou have previously attempted this task and you generated the following text:{PreviousTextTag(props.prev_generated_text)}This has a wordcount of {props.current_wordcount} words. This wordcount is {GreaterLess(props)} than the target wordcount of {props.target_wordcount}."""

    system_prompt = SystemTag(instruction).render()

    return system_prompt


WriterComponent = CtxComponent(writer_render_fn, WriterProps)


def map_store_to_writer(store: ExactLengthStore) -> WriterProps:
    return WriterProps(
        user_prompt=store.state.user_prompt,
        target_wordcount=store.state.target_wordcount,
        prev_generated_text=store.state.current_text,
        current_wordcount=store.state.wordcount,
    )


if __name__ == "__main__":

    # Testing context generation. This illustrates a useful feature. We can test context generation independantly from LLM calls and even independly from the Store data. This is very helpful when iterating on context construction.

    no_text_props1 = WriterProps(
        target_wordcount=1,
        current_wordcount=0,
        prev_generated_text="",
        user_prompt="Write 'hello'",
    )
    print(writer_render_fn(no_text_props1))

    fewer_props = WriterProps(
        target_wordcount=2,
        current_wordcount=1,
        prev_generated_text="hello",
        user_prompt="Write 'hello world'",
    )
    print(writer_render_fn(fewer_props))

    greater_props = WriterProps(
        target_wordcount=1,
        current_wordcount=3,
        prev_generated_text="hello world you",
        user_prompt="Write 'hello'",
    )
    print(writer_render_fn(greater_props))
