import json
import logging
import inspect
import os
from collections import defaultdict
from typing import Any, List

from a2a.server.agent_execution import AgentExecutor
from a2a.server.agent_execution.context import RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import (
    AgentCard,
    TaskState,
    TextPart,
    UnsupportedOperationError,
)
from a2a.utils.errors import ServerError
from openai import AsyncOpenAI


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class OpenAIAgentExecutor(AgentExecutor):
    """
    An AgentExecutor that manages persistent sessions and recovers 
    intelligently from pauses/HITL events.
    """

    def __init__(self, card: AgentCard, tools: dict[str, Any], api_key: str, system_prompt: str):
        self._card = card
        self.tools = tools
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
            default_headers={"HTTP-Referer": "http://localhost:8080", "X-Title": "A2A Data Agent"}
        )
        self.model = 'openai/gpt-4o-mini'
        self.system_prompt = system_prompt
        
        # PERSISTENCE: Path to store conversation history
        self.sessions_file = "sessions.json"
        self.sessions = self._load_sessions()

    def _load_sessions(self):
        """Loads sessions from a JSON file to persist state across restarts."""
        if os.path.exists(self.sessions_file):
            try:
                with open(self.sessions_file, 'r') as f:
                    data = json.load(f)
                    return defaultdict(list, data)
            except Exception as e:
                logger.error(f"Failed to load sessions: {e}")
        return defaultdict(list)

    def _save_sessions(self):
        """Saves history to JSON. Essential for the agent to remember after pausing."""
        try:
            with open(self.sessions_file, 'w') as f:
                json.dump(dict(self.sessions), f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save sessions: {e}")

    async def _process_request(self, message_text: str, context: RequestContext, task_updater: TaskUpdater) -> None:
        session_id = str(context.context_id)
        
        # Check if we are resuming a paused session
        is_resuming = session_id in self.sessions and len(self.sessions[session_id]) > 1
        
        if not is_resuming:
            self.sessions[session_id] = [{'role': 'system', 'content': self.system_prompt}]
        else:
            # IRONCLAD RESUMPTION NOTICE: Injected right before user input
            resumption_msg = (
                "CRITICAL RESUMPTION NOTICE: You are continuing a paused session. "
                "Look at your history. DO NOT call 'submit_plan'. DO NOT call any tool "
                "that has already returned a successful result. "
                "The human has provided guidance. Use it to call the NEXT tool in the sequence."
            )
            self.sessions[session_id].append({'role': 'system', 'content': resumption_msg})

        # Append user instruction and save immediately
        self.sessions[session_id].append({'role': 'user', 'content': message_text})
        self._save_sessions()
        
        messages = self.sessions[session_id]
        
        # Determine if we force submit_plan or let the LLM choose (auto)
        is_new_session = not is_resuming

        openai_tools = [{'type': 'function', 'function': self._extract_function_schema(f)} for f in self.tools.values()]
        iteration = 0
        tool_retries = defaultdict(int)

        while iteration < 20:
            iteration += 1
            
            # Forced Tool Choice Logic
            current_tool_choice = "auto"
            if is_new_session and iteration == 1:
                current_tool_choice = {"type": "function", "function": {"name": "submit_plan"}}

            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=openai_tools,
                    tool_choice=current_tool_choice,
                    temperature=0.1
                )
                
                message = response.choices[0].message
                messages.append({
                    'role': 'assistant', 
                    'content': message.content, 
                    'tool_calls': [t.model_dump() for t in message.tool_calls] if message.tool_calls else None
                })
                self._save_sessions()

                if message.tool_calls:
                    for tool_call in message.tool_calls:
                        function_name = tool_call.function.name
                        function_args = json.loads(tool_call.function.arguments)

                        # AUTOCORRECT: Fixes LLM formatting errors for list types
                        if function_name == 'submit_plan' and isinstance(function_args.get('steps'), str):
                            raw_steps = function_args['steps'].split('\n')
                            function_args['steps'] = [s.strip().lstrip('0123456789. ') for s in raw_steps if s.strip()]

                        logger.debug(f'Iteration {iteration}: Executing {function_name}')

                        if function_name in self.tools:
                            func = self.tools[function_name]
                            try:
                                result = func(**function_args)
                                if inspect.iscoroutine(result):
                                    result = await result
                                
                                # Process tool output
                                if hasattr(result, 'model_dump'):
                                    res_dict = result.model_dump()
                                elif isinstance(result, dict):
                                    res_dict = result
                                else:
                                    res_dict = {"status": "success", "result": str(result)}
                                res_json = json.dumps(res_dict)
                            except Exception as e:
                                res_json = json.dumps({"status": "error", "message": str(e)})
                        else:
                            res_json = json.dumps({"status": "error", "message": f"Tool {function_name} not found"})

                        messages.append({'role': 'tool', 'tool_call_id': tool_call.id, 'content': res_json})
                        self._save_sessions()

                        # HITL EXIT: Return control to user if pause tool is called
                        if function_name == 'request_human_input':
                            logger.info("Session paused via tool call.")
                            await task_updater.add_artifact([TextPart(text=res_json)])
                            await task_updater.complete()
                            return 

                        # Retry Logic - FIXED: Now checks 'status' field specifically
                        try:
                            # Parse the JSON and check for explicit error status
                            res_obj = json.loads(res_json)
                            is_error = res_obj.get("status") == "error"
                        except:
                            # Fallback if result isn't JSON
                            is_error = "error" in res_json.lower()

                        if is_error and function_name != 'escalate':
                            tool_retries[function_name] += 1
                            if tool_retries[function_name] >= 2:
                                messages.append({
                                    'role': 'system', 
                                    'content': f"NOTIFICATION: '{function_name}' has failed {tool_retries[function_name]} times. DO NOT call escalate. You MUST call 'request_human_input' to ask the user for help."
                                })
                            else:
                                messages.append({
                                    'role': 'system', 
                                    'content': f"NOTIFICATION: '{function_name}' failed. Modify parameters and retry."
                                })
                            self._save_sessions()

                    await task_updater.update_status(TaskState.working)
                    continue
                
                if message.content:
                    await task_updater.add_artifact([TextPart(text=message.content)])
                    await task_updater.complete()
                break

            except Exception as e:
                logger.error(f'System failure: {e}')
                await task_updater.add_artifact([TextPart(text=f'{{"status": "ERROR", "message": "{e!s}"}}')])
                await task_updater.complete()
                break

    def _extract_function_schema(self, func):
        """Extracts JSON Schema from a Python function, ensuring list types are correctly typed as arrays."""
        sig = inspect.signature(func)
        docstring = (inspect.getdoc(func) or func.__name__).split('\n')[0]
        
        properties = {}
        required = []

        for name, param in sig.parameters.items():
            param_type = 'string'
            if param.annotation != inspect.Parameter.empty:
                ann_str = str(param.annotation).lower()
                if param.annotation == int: param_type = 'integer'
                elif param.annotation == bool: param_type = 'boolean'
                elif 'list' in ann_str:
                    param_type = 'array'
            
            prop = {'type': param_type, 'description': f'Input for {name}'}
            if param_type == 'array':
                prop['items'] = {'type': 'string'}
                
            properties[name] = prop
            if param.default == inspect.Parameter.empty:
                required.append(name)

        return {
            'name': func.__name__,
            'description': docstring,
            'parameters': {
                'type': 'object',
                'properties': properties,
                'required': required
            }
        }

    async def execute(self, context: RequestContext, event_queue: EventQueue):
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        if not context.current_task: await updater.submit()
        await updater.start_work()
        
        # Combined text part extraction
        text_parts = []
        for p in context.message.parts:
            # Handle different SDK versions for text access
            if hasattr(p, 'root') and hasattr(p.root, 'text'):
                text_parts.append(p.root.text)
            elif hasattr(p, 'text'):
                text_parts.append(p.text)
                
        text = "".join(text_parts)
        await self._process_request(text, context, updater)

    async def cancel(self, context, event_queue): 
        raise ServerError(error=UnsupportedOperationError())