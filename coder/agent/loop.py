# coder/agent/loop.py
import asyncio
import json
import sys

from pygents import Agent, ContextItem, ContextPool, ContextQueue, Turn, tool
from pygents.registry import ToolRegistry


# ── debug helpers ──────────────────────────────────────────────────────────
def _dbg(label: str, msg: str, color: str = "36") -> None:
    """Print colored debug line. Colors: 31=red 32=green 33=yellow 34=blue 35=magenta 36=cyan."""
    from coder.shared.console import console
    if console.verbosity != "debug":
        return
    sys.stderr.write(f"\033[{color};1m[{label}]\033[0m \033[{color}m{msg}\033[0m\n")
    sys.stderr.flush()

from coder.agent.tools import ALL_TOOLS
from coder.agent.compaction.summarizer import run_compaction, should_compact
from coder.agent.llm.decide import (
    AgentResponse,
    get_allowed_tools,
    get_compaction_summary,
)
from coder.agent.llm.prompt import (
    build_system_prompt,
    build_messages,
    build_tool_schemas,
)


def create_agent(session, pool: ContextPool, cq: ContextQueue) -> Agent:
    """Create the pygents agent with all tools, llm_decide, llm_respond, and hooks."""

    @tool()
    async def llm_decide(cq: ContextQueue, pool: ContextPool):
        """Structured LLM call that decides: execute tools or respond to user."""
        toolkit = session.toolkit
        allowed_tools = get_allowed_tools(pool)
        system_prompt = build_system_prompt(pool, allowed_tools)
        compaction_summary = get_compaction_summary(pool)
        messages_list = build_messages(cq, compaction_summary)
        tool_schemas = build_tool_schemas(allowed_tools)

        # Build conversation string from messages
        conversation = _build_conversation(messages_list)

        _dbg("DECIDE", f"cq has {len(list(cq.items))} items", "36")
        _dbg("DECIDE", f"allowed_tools = {allowed_tools}", "36")
        _dbg("DECIDE", f"tool_schemas count = {len(tool_schemas)}", "36")
        _dbg("DECIDE", f"conversation:\n{conversation}", "34")

        # Build tool reference string (include parameter schemas so the LLM
        # knows the exact argument names and types for each tool)
        tool_ref_parts: list[str] = []
        for s in tool_schemas:
            fn = s["function"]
            entry = f"- {fn['name']}: {fn.get('description', '')}"
            if "parameters" in fn:
                entry += f"\n  Parameters: {json.dumps(fn['parameters'])}"
            tool_ref_parts.append(entry)
        tool_ref = "\n".join(tool_ref_parts)

        _dbg("DECIDE", f"tool_ref:\n{tool_ref}", "35")

        # Structured LLM call
        response = await toolkit.asend(
            response_model=AgentResponse,
            template=(
                "{{ system_prompt }}\n\n"
                "## Available Tools\n{{ tool_ref }}\n\n"
                "## Conversation\n{{ conversation }}"
            ),
            system_prompt=system_prompt,
            tool_ref=tool_ref,
            conversation=conversation,
        )

        agent_response = response.content

        _dbg("DECIDE", f"text = {agent_response.text!r}", "32" if agent_response.tool_calls else "31")
        _dbg("DECIDE", f"tool_calls = {agent_response.tool_calls}", "32" if agent_response.tool_calls else "31")

        # Yield assistant message -> agent routes to cq
        assistant_content = ""
        if agent_response.text:
            assistant_content = agent_response.text
        if agent_response.tool_calls:
            calls_desc = ", ".join(
                f"{tc.name}({tc.arguments})" for tc in agent_response.tool_calls
            )
            assistant_content = (
                f"{assistant_content}\nCalling: {calls_desc}"
                if assistant_content
                else f"Calling: {calls_desc}"
            )
        yield ContextItem(content={"role": "assistant", "content": assistant_content})

        # Route next step
        if agent_response.tool_calls:
            for tc in agent_response.tool_calls:
                # Re-prefix tool name if LLM returned stripped name
                tool_name = (
                    f"tool_{tc.name}" if not tc.name.startswith("tool_") else tc.name
                )
                _dbg("DECIDE", f"yielding Turn({tool_name}, kwargs={tc.arguments})", "33")
                yield Turn(tool_name, kwargs=tc.arguments)
            _dbg("DECIDE", "yielding Turn(llm_decide) for re-entry", "33")
            yield Turn(llm_decide)  # self-enqueue after all tools (FIFO)
        else:
            _dbg("DECIDE", "no tool_calls → yielding Turn(llm_respond)", "35")
            yield Turn(llm_respond)

    @tool()
    async def llm_respond(cq: ContextQueue, pool: ContextPool):
        """Streaming LLM call that yields text chunks for the REPL to print."""
        _dbg("RESPOND", f"entering llm_respond, cq has {len(list(cq.items))} items", "35")
        toolkit = session.toolkit
        allowed_tools = get_allowed_tools(pool)
        system_prompt = build_system_prompt(pool, allowed_tools)
        compaction_summary = get_compaction_summary(pool)
        messages_list = build_messages(cq, compaction_summary)

        # Build conversation string from messages
        conversation = _build_conversation(messages_list)

        # Streaming LLM call (no tool schemas — text only)
        full_text = ""
        async for chunk in toolkit.stream(
            template="{{ system_prompt }}\n\n## Conversation\n{{ conversation }}",
            system_prompt=system_prompt,
            conversation=conversation,
        ):
            full_text += chunk.content
            yield chunk.content

        # Yield full assistant message -> agent routes to cq
        yield ContextItem(content={"role": "assistant", "content": full_text})

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
        turn = agent._current_turn
        if turn is None or turn.tool.metadata.name != "llm_decide":
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
    async def check_compaction(cq: ContextQueue, pool: ContextPool) -> None:
        toolkit = session.toolkit
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

    # Hook: show tool traces after tool turns complete
    _internal_tools = {llm_decide.__name__, llm_respond.__name__}

    @agent.after_turn
    async def trace_tool(agent: Agent, turn: Turn) -> None:
        from coder.shared.console import console
        raw_name = turn.tool.metadata.name
        if raw_name in _internal_tools:
            return
        # Extract result preview from yielded ContextItems
        result_preview = ""
        if isinstance(turn.output, list):
            for item in turn.output:
                if isinstance(item, ContextItem) and isinstance(item.content, dict):
                    result_preview = str(item.content.get("content", ""))
                    break
        display = result_preview[:200] + "..." if len(result_preview) > 200 else result_preview
        display = display.replace("\n", " ")
        # Extract context hint from kwargs
        context = (
            turn.kwargs.get("command")
            or turn.kwargs.get("path")
            or turn.kwargs.get("pattern")
            or ""
        )
        display_name = raw_name[5:] if raw_name.startswith("tool_") else raw_name
        console.tool_trace(display_name, display, context=context)

    # Store references for external access (e.g., repl.py enqueues Turn(llm_decide))
    session._llm_decide = llm_decide
    session._llm_respond = llm_respond

    return agent


def _build_conversation(messages: list[dict]) -> str:
    """Build a conversation string from a list of message dicts."""
    parts: list[str] = []
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        if content:
            parts.append(f"[{role}]: {content}")
    return "\n\n".join(parts)


def _register_tools(tools: list) -> None:
    for t in tools:
        try:
            ToolRegistry.get(t.__name__)
        except Exception:
            ToolRegistry.register(t)
