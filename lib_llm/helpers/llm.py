from __future__ import annotations
import json
from enum import Enum
from app.llm_provider import apply_openrouter_request_overrides, create_async_llm_client

class LLM:
    # GPT Models
    models = {
        "4": "gpt-4-turbo", 
        "35": "gpt-3.5-turbo", 
        "4+": "gpt-4-1106-preview",
        "36" : "gpt-3.5-turbo-1106",
        "37" : "gpt-3.5-turbo-16k",
        "4++" : "gpt-4-0125-preview",
        "35++" : "gpt-3.5-turbo-0125",
        "4o-mini" : "gpt-4o-mini",
        "4o" : "gpt-4o",
        "kimi-k2.5": "moonshotai/kimi-k2.5",
        "claude-haiku-4.5": "anthropic/claude-haiku-4.5",
        "claude-sonnet-4.6": "anthropic/claude-sonnet-4.6",
        "glm-5": "z-ai/glm-5.1",
        "glm-5.1": "z-ai/glm-5.1",
        "qwen3.6-plus": "qwen/qwen3.6-plus",
        "qwen/qwen3.6-plus": "qwen/qwen3.6-plus",
        "deepseek-v3.2": "deepseek/deepseek-v3.2",
        "deepseek/deepseek-v3.2": "deepseek/deepseek-v3.2",
        "minimax-m2.7": "minimax/minimax-m2.7",
        "minimax/minimax-m2.7": "minimax/minimax-m2.7",
        "gemini-3-flash": "google/gemini-3-flash-preview",
        "google/gemini-3-flash": "google/gemini-3-flash-preview",
        "gpt-5.4": "openai/gpt-5.4",
        "openai/gpt-5.4": "openai/gpt-5.4",
    }

    class Role(Enum):
        USER = "user"
        TOOL = "tool"
        SYSTEM = "system"
        ASSISTANT = "assistant"

    class LLMMessage:
        def __init__(self, role: LLM.Role, content: str , tool_call_id : str = None) -> None:
            self.role = role
            self.content = content
            self.tool_call_id = tool_call_id
            

        def __str__(self) -> str:
            return f"{self.role.value}: {self.content}"

    def __init__(self, guid , prompt_generator, api_key , model="gpt-5-mini", custom_functions=None):
        self.api_key = api_key
        self.guid = guid
        self.prompt_generator = prompt_generator
        self.model = LLM.models.get(model, model)
        self.client = create_async_llm_client(model=self.model)
        self.custom_functions = custom_functions or custom_functions
        self.function_responses = []
        


        self.reset()
        print(f"GPT_Model :> {self.model}")


    def _apply_model_defaults(self, params: dict) -> dict:
        if self.model == "gpt-5":
            params.pop("temperature", None)
            params["max_completion_tokens"] = 1000
            params["reasoning_effort"] = "minimal"
        elif self.model == "gpt-5-mini":
            params.pop("temperature", None)
            params["max_completion_tokens"] = 1000
            params["reasoning_effort"] = "low"
        elif self.model == "gpt-5.2":
            params.pop("temperature", None)
            params["max_completion_tokens"] = 1000
            params["reasoning_effort"] = "none"
        elif self.model == "gpt-5.2-pro":
            params.pop("temperature", None)
            params["max_completion_tokens"] = 1000
            params["reasoning_effort"] = "medium"
        return params


    def reset(self):
        self.messages = []
        self.add_message(
            message=LLM.LLMMessage(LLM.Role.SYSTEM, str(self.prompt_generator))
        )

    def add_message(self, message: LLMMessage) -> None:
        if message.role == LLM.Role.TOOL : 
            self.messages.append(
                {"role": message.role.value, "content": message.content , "tool_call_id": message.tool_call_id}
            )
        else : 
            self.messages.append(
                {"role": message.role.value, "content": message.content}
            )

    async def interaction(self, message: LLM.LLMMessage) -> str:
        if message.content != "":
            self.add_message(message)

        words = []

        stream = await self.client.chat.completions.create(
            **apply_openrouter_request_overrides(self._apply_model_defaults({
                "model": self.model,
                "messages": self.messages,
                "stream": True,
                "tools": self.custom_functions,
                "function_call": "auto",
                "temperature": 0.3,
            }))
        )

        function_name = None
        function_args = ""

        async for part in stream:
            if part.choices[0].delta.content:
                words.append(part.choices[0].delta.content or "")
                yield words[-1]
            elif part.choices[0].delta.function_call:
                if part.choices[0].delta.function_call.name:
                    function_name = part.choices[0].delta.function_call.name
                if part.choices[0].delta.function_call.arguments:
                    function_args += part.choices[
                        0
                    ].delta.function_call.arguments

        if function_name:
            yield {
                "type": "function_call",
                "name": function_name,
                "args": function_args,
            }

        message = LLM.LLMMessage(
            role=LLM.Role.ASSISTANT,
            content="".join(words).strip().replace("\n", " "),
        )
        self.add_message(message)
    
    async def create_completion(self, message: LLM.LLMMessage):
        """Create a new completion with the given message."""
        if message.content != "":
            self.add_message(message)

        stream = await self.client.chat.completions.create(
            **apply_openrouter_request_overrides(self._apply_model_defaults({
                "model": self.model,
                "messages": self.messages,
                "stream": True,
                "tools": self.tools,
                "tool_choice": "auto",
                "temperature": 0.3,
                # response_format={ "type": "json_object" }
            }))
        )

        words = []
        tool_calls_buffer = {}
        content = ""

        async for part in stream:
            choice = part.choices[0]
            delta = choice.delta

            # Collect normal content (assistant message)
            if delta.content:
                words.append(delta.content)
                yield delta.content


            # Collect streaming tool calls
            if delta.tool_calls:
                for tool_call in delta.tool_calls:
                    idx = tool_call.index
                    # Initialize if first time seeing this tool call
                    if idx not in tool_calls_buffer:
                        tool_calls_buffer[idx] = {
                            "id": tool_call.id,
                            "function": {
                                "name": tool_call.function.name or "",
                                "arguments": ""
                            },
                            "type": tool_call.type
                        }

                    # Append function name if streaming
                    if tool_call.function.name:
                        tool_calls_buffer[idx]["function"]["name"] = tool_call.function.name

                    # Append arguments as they stream in
                    if tool_call.function.arguments:
                        tool_calls_buffer[idx]["function"]["arguments"] += tool_call.function.arguments

            # Detect finish
            if choice.finish_reason == "tool_calls":
                # At this point, tool_calls_buffer has full function calls ready
                for call in tool_calls_buffer.values():
                    # You can now process or execute the tool function
                    tool_name = call["function"]["name"]
                    args_json = call["function"]["arguments"]

                    try:
                        args = json.loads(args_json)
                    except json.JSONDecodeError:
                        print("Failed to decode tool arguments:", args_json)
                        continue

                    # Example: yield to calling code
                    yield {
                        "type": "function_call",
                        "name": tool_name,
                        "args": args,
                        "id": call["id"],
                    }

                # Reset after tool call is handled
                tool_calls_buffer = {}

        # json_content="".join(words).strip().replace("\n", " ")
        # json_content = json_content.replace("```json", "").replace("```", "")
        # json_content = json.loads(json_content)
        # print("------------","LLM",json_content,"------------")

        if words:
            message = LLM.LLMMessage(
                role=LLM.Role.ASSISTANT,
                content="".join(words).strip().replace("\n", " "),
                # content=json_content["response"]
            )
            self.add_message(message)

    async def continue_with_tool_response(self, assistant_message, tool_outputs):
        """Continue the conversation with tool responses."""
        # First add the assistant's message with tool calls
        self.messages.append({
            "role": "assistant",
            "content": assistant_message.content,
            "tool_calls": assistant_message.tool_calls
        })
        
        # Then add the tool responses
        for tool_output in tool_outputs:
            self.messages.append({
                "role": "tool",
                "tool_call_id": tool_output["tool_call_id"],
                "content": tool_output["content"]
            })
        
        # Get the model's response to the tool outputs
        completion = await self.client.chat.completions.create(
            **apply_openrouter_request_overrides({
                "model": self.model,
                "messages": self.messages,
                "tools": self.tools,
                "temperature": 0.3,
            })
        )
        
        return completion
    











        # words = []
        # async for part in stream:
        #     print(part.choices[0] , "CHOICES")
        #     if part.choices[0].delta.content:
        #         words.append(part.choices[0].delta.content or "")
        #         yield words[-1]
        #     elif part.choices[0].delta.tool_calls:
        #         if part.choices[0].delta.tool_calls.name:
        #             function_name = part.choices[0].delta.tool_calls.name
        #         if part.choices[0].delta.tool_calls.arguments:
        #             function_args += part.choices[
        #                 0
        #             ].delta.tool_calls.arguments
