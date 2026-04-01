import asyncio
from pygents import Agent, ContextItem, ContextPool, ContextQueue
from pygents.registry import ToolRegistry

from coder.tools.read import tool_read
from coder.tools.write import tool_write
from coder.tools.edit import tool_edit
from coder.tools.bash import tool_bash
from coder.tools.grep import tool_grep
from coder.tools.find import tool_find
from coder.tools.ls import tool_ls

_ALL_TOOLS = [tool_read, tool_write, tool_edit, tool_bash, tool_grep, tool_find, tool_ls]

from coder.llm_call import run_llm_call


async def run_agent_loop(session) -> None:
    """Run the agent's main loop: call LLM, execute tools, repeat until done."""
    # Check compaction before LLM call
    await session.check_compaction()

    # Inject any steering messages
    while not session.steering_queue.empty():
        try:
            msg = session.steering_queue.get_nowait()
            await session.cq.append(
                ContextItem(content={"role": "user", "content": msg})
            )
        except asyncio.QueueEmpty:
            break

    # Run the LLM call loop (handles tool calling internally)
    await run_llm_call(
        toolkit=session.toolkit,
        cq=session.cq,
        pool=session.pool,
        allowed_tools=session.allowed_tools,
    )

def register_all_tools() -> list:
    for t in _ALL_TOOLS:
        if ToolRegistry._registry.get(t.__name__) is None:
            ToolRegistry.register(t)
    return _ALL_TOOLS

def create_agent(pool: ContextPool, cq: ContextQueue, steering_queue: asyncio.Queue | None = None) -> Agent:
    tools = register_all_tools()
    agent = Agent("coder", "A coding assistant", tools, context_pool=pool, context_queue=cq)
    if steering_queue is not None:
        @agent.before_turn
        async def inject_steering(agent: Agent) -> None:
            while not steering_queue.empty():
                try:
                    msg = steering_queue.get_nowait()
                    await agent.context_queue.append(ContextItem(content={"role": "user", "content": msg}))
                except asyncio.QueueEmpty:
                    break
    return agent
