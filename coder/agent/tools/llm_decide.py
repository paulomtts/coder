# coder/agent/tools/llm_decide.py
import json

from pygents import ContextItem, ContextPool, ContextQueue, Turn, tool

from coder.agent.llm.decide import AgentResponse
from coder.agent.llm.prompt import (
    build_conversation,
    build_messages,
    build_system_prompt,
    build_tool_schemas,
    get_allowed_tools,
    get_compaction_summary,
)
from coder.shared.console import dbg


@tool()
async def llm_decide(cq: ContextQueue, pool: ContextPool):
    """Structured LLM call that decides: execute tools or respond to user."""
    session = pool.get("session").content
    toolkit = session.toolkit
    allowed_tools = get_allowed_tools(pool)
    system_prompt = build_system_prompt(pool, allowed_tools)
    compaction_summary = get_compaction_summary(pool)
    messages_list = build_messages(cq, compaction_summary)
    tool_schemas = build_tool_schemas(allowed_tools)

    conversation = build_conversation(messages_list)

    dbg("DECIDE", f"cq has {len(list(cq.items))} items", "36")
    dbg("DECIDE", f"allowed_tools = {allowed_tools}", "36")
    dbg("DECIDE", f"tool_schemas count = {len(tool_schemas)}", "36")
    dbg("DECIDE", f"conversation:\n{conversation}", "34")

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

    dbg("DECIDE", f"tool_ref:\n{tool_ref}", "35")

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

    dbg(
        "DECIDE",
        f"text = {agent_response.text!r}",
        "32" if agent_response.tool_calls else "31",
    )
    dbg(
        "DECIDE",
        f"tool_calls = {agent_response.tool_calls}",
        "32" if agent_response.tool_calls else "31",
    )

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
            dbg(
                "DECIDE", f"yielding Turn({tool_name}, kwargs={tc.arguments})", "33"
            )
            yield Turn(tool_name, kwargs=tc.arguments)
        dbg("DECIDE", "yielding Turn(llm_decide) for re-entry", "33")
        yield Turn(llm_decide)  # self-enqueue after all tools (FIFO)
    else:
        from coder.agent.tools.llm_respond import llm_respond

        dbg("DECIDE", "no tool_calls → yielding Turn(llm_respond)", "35")
        yield Turn(llm_respond)
