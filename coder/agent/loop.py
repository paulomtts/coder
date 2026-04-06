# coder/agent/loop.py
from pygents import Agent, ContextPool, ContextQueue
from pygents.registry import ToolRegistry

from coder.agent.hooks import extract_memories, trace_tool
from coder.agent.tools import ALL_TOOLS
from coder.agent.tools.compact import compact
from coder.agent.tools.llm_decide import llm_decide
from coder.agent.tools.llm_respond import llm_respond


def create_agent(pool: ContextPool, cq: ContextQueue) -> Agent:
    """Create the pygents agent with all tools and hooks."""
    all_tools = list(ALL_TOOLS) + [llm_decide, llm_respond, compact]

    # Ensure tools are in the registry (needed after registry clears in tests)
    for t in all_tools:
        try:
            ToolRegistry.get(t.__name__)
        except Exception:
            ToolRegistry.register(t)

    agent = Agent(
        "coder",
        "A coding assistant",
        all_tools,
        context_pool=pool,
        context_queue=cq,
    )

    agent.after_turn(trace_tool)
    agent.after_turn(extract_memories)

    return agent
