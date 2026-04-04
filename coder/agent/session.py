import asyncio
from dataclasses import dataclass, field

from py_ai_toolkit import LLMConfig, PyAIToolkit
from pygents import Agent, ContextItem, ContextPool, ContextQueue

from coder.agent.loop import create_agent
from coder.agent.compaction import (
    BRANCH_SUMMARY_PREAMBLE,
    BRANCH_SUMMARY_PROMPT,
    run_compaction,
    should_compact,
)
from coder.config.loader import SessionConfig, load_config
from coder.agent.personas.definitions import get_persona
from coder.config.resources import (
    discover_project_context,
    load_append_prompt,
    load_system_prompt_override,
)

DEFAULT_BASE_PROMPT = """You are an expert coding assistant operating inside coder, a coding agent harness.
You help users by reading files, executing commands, editing code, and writing new files.

Available tools:
{tools_list}

In addition to the tools above, you may have access to other custom tools depending on the project.

Guidelines:
{guidelines}"""


@dataclass
class Session:
    agent: Agent | None = None
    toolkit: PyAIToolkit | None = None
    pool: ContextPool = field(default_factory=ContextPool)
    cq: ContextQueue = field(default_factory=lambda: ContextQueue(limit=50))
    config: SessionConfig = field(default_factory=SessionConfig)
    steering_queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    allowed_tools: set[str] | None = None
    _active_role: str | None = None

    async def start(self, cwd: str | None = None) -> None:
        self.config = load_config(cwd=cwd)
        llm_config = None
        if self.config.model or self.config.api_key:
            llm_config = LLMConfig(
                model=self.config.model,
                api_key=self.config.api_key,
                base_url=self.config.base_url or None,
            )
        self.toolkit = PyAIToolkit(main_model_config=llm_config)
        self.cq = ContextQueue(limit=self.config.history_limit)
        self.pool = ContextPool()
        override = load_system_prompt_override(self.config.cwd)
        base_prompt = override if override else DEFAULT_BASE_PROMPT
        await self.pool.add(
            ContextItem(
                id="base-prompt", description="Base system prompt", content=base_prompt
            )
        )
        project_ctx = discover_project_context(self.config.cwd)
        if project_ctx:
            await self.pool.add(
                ContextItem(
                    id="project-context",
                    description="Project context from AGENTS.md/CLAUDE.md",
                    content=project_ctx,
                )
            )
        append = load_append_prompt(self.config.cwd)
        if append:
            await self.pool.add(
                ContextItem(
                    id="append-prompt",
                    description="Appended system prompt instructions",
                    content=append,
                )
            )
        self.agent = create_agent(
            session=self, pool=self.pool, cq=self.cq
        )

    async def switch_role(self, persona_name: str) -> None:
        persona = get_persona(persona_name)
        if len(self.cq) > 0 and self.toolkit:
            conversation = "\n".join(
                f"[{item.content.get('role', '?')}]: {item.content.get('content', '')}"
                for item in self.cq.items
                if isinstance(item.content, dict)
            )
            response = await self.toolkit.chat(
                template="{{ conversation }}\n\n{{ prompt }}",
                conversation=conversation,
                prompt=BRANCH_SUMMARY_PROMPT,
            )
            try:
                await self.pool.remove("branch-summary")
            except KeyError:
                pass
            await self.pool.add(
                ContextItem(
                    id="branch-summary",
                    description="Summary of previous conversation branch",
                    content=BRANCH_SUMMARY_PREAMBLE + response.content,
                )
            )
        try:
            await self.pool.remove("active-role")
        except KeyError:
            pass
        await self.pool.add(
            ContextItem(
                id="active-role",
                description=f"Active role: {persona.name}",
                content=persona.system_prompt,
            )
        )
        self.allowed_tools = set(persona.allowed_tools)
        self._active_role = persona_name

    async def clear_role(self) -> None:
        try:
            await self.pool.remove("active-role")
        except KeyError:
            pass
        self.allowed_tools = None
        self._active_role = None

    async def check_compaction(self) -> None:
        if not self.toolkit:
            return
        items = self.cq.items
        max_tokens = 128000
        if not should_compact(items, self.config.compaction_threshold, max_tokens):
            return
        existing_summary = None
        try:
            summary_item = self.pool.get("compaction-summary")
            existing_summary = str(summary_item.content)
        except KeyError:
            pass
        summary, recent = await run_compaction(
            self.toolkit, items, existing_summary, self.config.keep_recent_tokens
        )
        try:
            await self.pool.remove("compaction-summary")
        except KeyError:
            pass
        await self.pool.add(
            ContextItem(
                id="compaction-summary",
                description="Compacted conversation summary",
                content=summary,
            )
        )
        await self.cq.clear()
        for item in recent:
            await self.cq.append(item)
