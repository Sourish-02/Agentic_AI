## Adaptive Workflow Orchestrative Agent (Data Pipeline & Report Delivery)

Project Overview - This project is a fully functional autonomous Agent-to-Agent (A2A) service built on top of the provided template (Template 3). We have transformed it from a bare-bones placeholder into a production-ready Workspace Data Agent capable of receiving natural language instructions, executing multi-step data pipelines, and returning structured results. The agent is named the Data Pipeline Orchestrator. It connects to an OpenRouter-backed LLM (GPT-4o-mini), maintains persistent conversation sessions, and exposes eight specialized tools for data analysis, visualization, vision AI, and human-in-the-loop escalation.

__main__.py        → boots the server, wires everything together
openai_agent.py    → defines the tools + system prompt
agent_toolset.py   → the actual tool implementations (fetch, transform, chart, etc.)
openai_agent_executor.py → the loop that drives the LLM turn by turn

When you run python -m src, this file runs first.
It does 5 things in order:
1.	Checks that OPENROUTER_API_KEY is set in your .env file. Crashes early if not.
2.	Creates an AgentSkill : this is just a metadata object describing what the agent can do. Think of it as a business card entry.
3.	Creates an AgentCard : the full identity of the agent: its name, URL (http://localhost:5000), version, and the skill from step 2. This is what other systems use to discover and call this agent via the A2A protocol.
4.	Calls create_agent() : this returns a dict with two things: the tools (the actual Python functions) and the system prompt (instructions for the LLM).
5.	Creates the OpenAIAgentExecutor, passing in the card, tools, API key, and system prompt. Then wraps it in A2A's DefaultRequestHandler and A2AStarletteApplication, and starts a uvicorn HTTP server on port 5000.
From this point the server is live and waiting for HTTP requests.

Tools and prompt are defined (openai_agent.py + agent_toolset.py)
openai_agent.py is very simple ; it just calls get_tools() and pairs it with the system prompt string. The system prompt is the core set of rules the LLM must follow: always call submit_plan first, never re-run a successful step, follow the fixed sequence, retry on error, escalate if stuck.
agent_toolset.py is where all the actual tools live inside a class called DataPipelineToolset. Here's what each tool does:
•	submit_plan(steps) : just accepts the plan and returns success. It's a forcing function to make the LLM commit to an ordered list before doing anything.
•	fetch_data(source, query) - deliberately fails the first time with a 429 error (simulating a rate limit). On the second call it returns 3 rows of sales data, one of which has a corrupt "ERROR_NAN" value in the sales column.
•	transform_data(raw_data_json, strategy) : uses pandas to clean the data. If strategy="drop_corrupt", it converts sales to numeric (which turns "ERROR_NAN" into NaN) then drops that row.
•	generate_chart(transformed_data_json, chart_type) : uses matplotlib to draw a real PNG bar or pie chart, saves it to /app/pipeline_chart.png.
•	compose_report(summary_text, chart_url) : just builds a markdown string combining the summary and chart.
•	dispatch_email(report_content, recipient) : simulates sending email, always returns success.
•	request_human_input(reason, question) : pauses the workflow and returns control to the user.
•	escalate(reason, failed_step) : hard stops the workflow with a failure message.

When an HTTP POST hits the server (from a client sending something like "Fetch Q3 sales data and email it to team@company.com"), A2A's framework calls execute() on the executor.
execute() does three things:
1.	Creates a TaskUpdater to send progress updates back to the caller.
2.	Calls updater.submit() and updater.start_work() to notify the caller the task has started.
3.	Extracts the plain text from the message parts and hands it to _process_request().

The executor has a sessions dict (loaded from sessions.json on disk). Each session is keyed by context_id : a unique ID for this conversation thread.
If it's a new session: a fresh message list is created with just the system prompt at the top.
If it's a resuming session (the user previously called request_human_input and is now replying): a special CRITICAL RESUMPTION NOTICE system message is injected telling the LLM "don't re-run things that already succeeded, jump to the next unfinished step."
Either way, the user's message is appended and the whole thing is saved to sessions.json immediately. This is why the agent survives restarts — its memory is on disk.
Now the while loop runs, up to 20 iterations. Each iteration is one round-trip to the LLM.
Iteration 1 (new session only): tool_choice is forced to submit_plan. The LLM has no choice — it must call that tool first. This prevents it from hallucinating and jumping straight to execution.
The executor calls client.chat.completions.create(...) with the full message history and all tool schemas. The LLM responds with a tool call (or occasionally text).

For every tool call the LLM makes:
1.	The function name and JSON arguments are extracted.
2.	AUTOCORRECT: If the tool is submit_plan and the LLM passed steps as a string instead of a JSON array (a common LLM mistake), Python splits it on newlines and cleans it up before passing it to the actual function.
3.	The tool function is looked up in self.tools dict and called with the arguments.
4.	The result is normalised to a dict - Pydantic models get .model_dump() called, plain dicts stay as-is, anything else gets wrapped.
5.	The result is appended to messages as a role: tool entry (this is what the LLM reads on the next iteration to know what happened).
6.	The session is saved to disk again.

After each tool result, two special checks happen:
HITL check: If the tool that was just called was request_human_input, the executor immediately returns the paused response to the user and exits the loop. The session is saved. Next time the user sends a message with the same context_id, it resumes from exactly this point.
Error check: The result JSON is parsed and status == "error" is checked (strictly — not a loose string search). If it's an error:
•	tool_retries[function_name] is incremented.
•	If retries < 2: a system message is injected saying "failed, modify parameters and retry."
•	If retries >= 2: a system message is injected saying "you MUST call request_human_input to ask the user for help."

The whole thing works because of one shared state between the LLM and Python. The LLM decides what to call next based on the message history
Python controls whether that call is allowed (forced submit_plan, retry injection, HITL exit). The sessions.json file means neither loses memory if the process restartsThe LLM is the brain deciding the sequence. Python is the guardrails enforcing the rules.


How is our project better than a normal LLM?

Agency vs. Chatting
•	The LLM: If you ask ChatGPT to "Fetch sales data and make a chart," it will write the Python code for you and tell you to run it. It is an advisor.
•	Our Agent: It doesn't ask you to run code. It opens its agent_toolset.py, imports Pandas and Matplotlib, and executes the commands itself. It is a worker.

2. State-Aware Memory (The "Sessions")
•	The LLM: If ChatGPT crashes or the tab refreshes, it forgets exactly which step of the pipeline it was on.
•	Our Agent:  Our executor.py saves everything to a sessions.json. If the system restarts, the agent looks at its "notebook," sees it already fetched the data, and skips straight to the cleaning step. This saves time and money (tokens).

3. Structural Resilience (The "429 Test")
•	The LLM: If an LLM calls a tool and gets a "429 Rate Limit Error," it often gets confused and says "I can't do this right now."
•	Our Agent:  We wrote Python logic that forces the agent to be resilient. When it hits that error, your code injects a System Notification saying: "Re-plan and try again." The agent doesn't just stop; it recalculates its path until it succeeds.

4. Real-World Deliverables
•	The LLM: Usually gives you text or a code block.
•	Our Agent: It produces a physical file (pipeline_chart.png) and sends a simulated email. It interacts with the local file system and network, which a sandboxed LLM cannot do.

5. Deterministic Logic (The "Safety Brake")
•	The LLM: Can "hallucinate" and try to use tools that don't exist.
•	Our Agent:  Our _extract_function_schema logic strictly defines what the agent can and cannot do. If it fails twice, the Escalation Tool forces it to stop. We have "Human-in-the-Loop" safety that a standard LLM lacks.

