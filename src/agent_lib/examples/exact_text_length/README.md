# Exact Text Length App

This is an agentic application which ensures that a text is generated with an exact word count.

# Current

It is working, but it takes the LLM too many iterations. I believe it might work better to include the whole history using messages.


# Next Steps

Use messages in AgentState and add llm messages with the generated text, interspersed with user messages with the feedback on the wordcount for each attempt.

This will require breaking apart the writer system prompt context component which currently bundles those together.