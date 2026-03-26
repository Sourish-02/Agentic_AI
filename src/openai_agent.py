from {{TOOLSET_MODULE}} import {{TOOLSET_CLASS}}  # type: ignore[import-untyped]


def create_agent():
    """Create OpenAI agent and its tools"""
    toolset = {{TOOLSET_CLASS}}()
    tools = toolset.get_tools()

    return {
        'tools': tools,
        'system_prompt': """{{SYSTEM_PROMPT}}""",
    }