# coder/agent/loop.py
import asyncio

from pygents import Agent, ContextItem, ContextPool, ContextQueue, Turn, tool
from pygents.registry import ToolRegistry
from py_ai_toolkit import PyAIToolkit

from coder.agent.tools import ALL_TOOLS
from coder.agent.compaction.summarizer import run_compaction, should_compact


def _register_tools(tools: list) -> None:
    for t in tools:
        if ToolRegistry._registry.get(t.__name__) is None:
            ToolRegistry.register(t)


def create_agent(session, pool: ContextPool, cq: ContextQueue) -> Agent:
    """Create the pygents agent with all tools, llm_decide, llm_respond, and hooks."""
    from coder.agent.llm.decide import llm_decide
    from coder.agent.llm.respond import llm_respond

    all_tools = list(ALL_TOOLS) + [llm_decide, llm_respond]
    _register_tools(all_tools)

    agent = Agent(
        "coder",
        "A coding assistant",
        all_tools,
        context_pool=pool,
        context_queue=cq,
    )

    # Hook: inject steering messages before llm_decide turns
    @agent.before_turn
    async def inject_steering(agent: Agent) -> None:
        if agent.current_turn.tool.metadata.name != "llm_decide":
            return
        while not session.steering_queue.empty():
            try:
                msg = session.steering_queue.get_nowait()
                await agent.context_queue.append(
                    ContextItem(content={"role": "user", "content": msg})
                )
            except asyncio.QueueEmpty:
                break

    # Hook: compaction before llm_decide invocation
    @llm_decide.before_invoke
    async def check_compaction(
        cq: ContextQueue, pool: ContextPool, toolkit: PyAIToolkit
    ) -> None:
        items = cq.items
        max_tokens = 128_000
        if not should_compact(items, session.config.compaction_threshold, max_tokens):
            return
        existing_summary = None
        try:
            summary_item = pool.get("compaction-summary")
            existing_summary = str(summary_item.content)
        except KeyError:
            pass
        summary, recent = await run_compaction(
            toolkit, items, existing_summary, session.config.keep_recent_tokens
        )
        try:
            await pool.remove("compaction-summary")
        except KeyError:
            pass
        await pool.add(
            ContextItem(
                id="compaction-summary",
                description="Compacted conversation summary",
                content=summary,
            )
        )
        await cq.clear()
        for item in recent:
            await cq.append(item)

    return agent
