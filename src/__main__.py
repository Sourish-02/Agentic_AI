import logging
import os
import click
import uvicorn

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from dotenv import load_dotenv
from openai_agent import create_agent
from openai_agent_executor import OpenAIAgentExecutor
from starlette.applications import Starlette

load_dotenv()
logging.basicConfig()

@click.command()
@click.option('--host', 'host', default='localhost')
@click.option('--port', 'port', default=5000)
def main(host: str, port: int):
    # 1. Verify the OpenRouter API key is set.
    if not os.getenv('OPENROUTER_API_KEY'):
        raise ValueError('OPENROUTER_API_KEY environment variable not set')

    # 2. Define the Agent Skill
    skill = AgentSkill(
        id='data_pipeline_orchestrator',
        name='Data Pipeline Orchestrator',
        description='Orchestrates multi-step data workflows. Decomposes instructions, handles API failures via code-level retries, and outputs structured JSON logs.',
        tags=['pipeline', 'data', 'reporting'],
        examples=[
            "Fetch Q3 sales data from v2_api, transform it using standard strategy, create a bar chart, compose a report, and email it to team@company.com."
        ],
    )

    # 3. Define the Agent Card (This is what went missing!)
    agent_card = AgentCard(
        name='data-pipeline-agent',
        description='An autonomous agent that manages end-to-end data pipeline workflows.',
        url=f'http://{host}:{port}/',
        version='1.0.0',
        default_input_modes=['text'],
        default_output_modes=['text'],
        capabilities=AgentCapabilities(streaming=True),
        skills=[skill],
    )

    # 4. Create agent tools
    agent_data = create_agent()

    # 5. Initialize the Executor
    agent_executor = OpenAIAgentExecutor(
        card=agent_card,
        tools=agent_data['tools'],
        api_key=os.getenv('OPENROUTER_API_KEY'),
        system_prompt=agent_data['system_prompt'],
    )

    request_handler = DefaultRequestHandler(
        agent_executor=agent_executor, task_store=InMemoryTaskStore()
    )

    a2a_app = A2AStarletteApplication(
        agent_card=agent_card, http_handler=request_handler
    )
    routes = a2a_app.routes()
    app = Starlette(routes=routes)

    uvicorn.run(app, host=host, port=port)

if __name__ == '__main__':
    main()