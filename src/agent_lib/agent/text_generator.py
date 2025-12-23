from typing import Any, Callable


type LLMAPIConfig = dict[str, Any]



type TextGenerator = Callable[[, LLMAPIConfig]]
