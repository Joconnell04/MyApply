from __future__ import annotations

from typing import Any, AsyncIterator, Sequence

from agents import Agent, ModelSettings, Runner
from chatkit.agents import AgentContext, simple_to_agent_input, stream_agent_response
from chatkit.server import ChatKitServer
from chatkit.types import ThreadMetadata, ThreadStreamEvent, UserMessageItem
from openai.types.responses import ResponseInputContentParam, ResponseInputTextParam


class MyChatKitServer(ChatKitServer[Any]):
    """
    ChatKit server implementation that bridges incoming events to the Agents SDK.
    """

    def __init__(self, store, attachment_store=None, *, agent: Agent[AgentContext] | None = None):
        super().__init__(store, attachment_store)
        self.assistant_agent = agent or Agent[AgentContext](
            model="gpt-4.1-mini",
            name="Assistant",
            instructions="You are a helpful assistant for MyApply users.",
            model_settings=ModelSettings(temperature=0.8, max_tokens=2048),
        )

    async def respond(
        self,
        thread: ThreadMetadata,
        input_user_message: UserMessageItem | None,
        context: Any,
    ) -> AsyncIterator[ThreadStreamEvent]:
        agent_context = AgentContext(
            thread=thread,
            store=self.store,
            request_context=context,
        )

        items_page = await self.store.load_thread_items(
            thread.id,
            after=None,
            limit=200,
            order="asc",
            context=context,
        )
        thread_items: Sequence = items_page.data

        agent_input = await simple_to_agent_input(thread_items) if thread_items else []

        # Fallback to the raw user message when no context has been persisted yet.
        if not agent_input and input_user_message:
            agent_input = await simple_to_agent_input(input_user_message)

        # If the conversion still yields no input, feed an empty user prompt to keep the loop alive.
        if not agent_input:
            agent_input = [
                {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": ""}],
                }
            ]

        result_stream = Runner.run_streamed(
            self.assistant_agent,
            agent_input,
            context=agent_context,
        )

        async for event in stream_agent_response(agent_context, result_stream):
            yield event

    async def to_message_content(
        self, input: Any
    ) -> ResponseInputContentParam:
        """
        Convert uploaded files into text content for the model.
        Attachments are not yet supported for MyApply, so we return a placeholder.
        """
        return ResponseInputTextParam(
            type="input_text",
            text="[attachment received but not yet supported]",
        )
