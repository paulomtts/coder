from dataclasses import dataclass, field

from py_ai_toolkit import LLMConfig, PyAIToolkit
from pygents import Agent, ContextItem, ContextPool, ContextQueue

from coder.agent.loop import create_agent
from coder.agent.memory.store import build_memory_index
from coder.agent.compaction.prompts import (
    BRANCH_SUMMARY_PREAMBLE,
    BRANCH_SUMMARY_PROMPT,
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
{guidelines}

You have persistent memory stored in ~/.coder/memory/.
- Semantic memories (facts, preferences, conventions) are loaded above under "What You Know".
- Episodic memories (past session summaries) exist on disk. The user can search them with /recall.
- You do not need to manage memory explicitly — it is handled automatically.
- If the user says /remember or /forget, acknowledge the action."""


@dataclass
class TokenStats:
    """Tracks token usage across LLM calls."""

    turn_prompt_tokens: int = 0
    turn_completion_tokens: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0

    def reset_turn(self) -> None:
        self.turn_prompt_tokens = 0
        self.turn_completion_tokens = 0

    def record(self, prompt_tokens: int, completion_tokens: int) -> None:
        self.turn_prompt_tokens += prompt_tokens
        self.turn_completion_tokens += completion_tokens
        self.total_prompt_tokens += prompt_tokens
        self.total_completion_tokens += completion_tokens


@dataclass
class Session:
    agent: Agent | None = None
    toolkit: PyAIToolkit | None = None
    pool: ContextPool = field(default_factory=ContextPool)
    cq: ContextQueue = field(default_factory=lambda: ContextQueue(limit=50))
    config: SessionConfig = field(default_factory=SessionConfig)
    token_stats: TokenStats = field(default_factory=TokenStats)
    _active_role: str | None = None
    _allowed_tools: set[str] | None = None

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
        # Load semantic memory into context pool
        memory_index = build_memory_index(base_dir=self.config.memory_dir)
        if memory_index:
            await self.pool.add(
                ContextItem(
                    id="semantic-memory",
                    description="Persistent semantic memory",
                    content=memory_index,
                )
            )
        from coder.agent.state import set_session

        set_session(self)
        self.agent = create_agent(pool=self.pool, cq=self.cq)

        # Run episodic memory decay
        if self.toolkit:
            from coder.agent.memory.decay import run_decay

            await run_decay(self.toolkit, base_dir=self.config.memory_dir)

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
        self._allowed_tools = set(persona.allowed_tools)
        self._active_role = persona_name

    async def clear_role(self) -> None:
        try:
            await self.pool.remove("active-role")
        except KeyError:
            pass
        self._allowed_tools = None
        self._active_role = None
