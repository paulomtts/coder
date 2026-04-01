import asyncio
from pygents import Agent, ContextItem, ContextPool, ContextQueue
from pygents.registry import ToolRegistry

from coder.agent.tools import ALL_TOOLS
from coder.agent.llm.call import run_llm_call


async def run_agent_loop(session) -> None:
    """Run the agent's main loop: call LLM, execute tools, repeat until done."""
    await session.check_compaction()

    while not session.steering_queue.empty():
        try:
            msg = session.steering_queue.get_nowait()
            await session.cq.append(
                ContextItem(content={"role": "user", "content": msg})
            )
        except asyncio.QueueEmpty:
            break

    await run_llm_call(
        toolkit=session.toolkit,
        cq=session.cq,
        pool=session.pool,
        allowed_tools=session.allowed_tools,
    )


def register_all_tools() -> list:
    for t in ALL_TOOLS:
        if ToolRegistry._registry.get(t.__name__) is None:
            ToolRegistry.register(t)
    return ALL_TOOLS


def create_agent(
    pool: ContextPool, cq: ContextQueue, steering_queue: asyncio.Queue | None = None
) -> Agent:
    tools = register_all_tools()
    agent = Agent(
        "coder", "A coding assistant", tools, context_pool=pool, context_queue=cq
    )
    if steering_queue is not None:

        @agent.before_turn
        async def inject_steering(agent: Agent) -> None:
            while not steering_queue.empty():
                try:
                    msg = steering_queue.get_nowait()
                    await agent.context_queue.append(
                        ContextItem(content={"role": "user", "content": msg})
                    )
                except asyncio.QueueEmpty:
                    break

    return agent
