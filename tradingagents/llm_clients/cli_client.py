"""CLI-based LLM client for subscription CLI backends.

Supports multiple non-API coding assistants behind one LangChain-compatible
interface. Each backend has its own invocation strategy:

- Claude CLI: `claude -p ...` and read final text from stdout
- Codex CLI: `codex exec ... -o <tmpfile>` and read the final message from file
"""

import os
import subprocess
import tempfile
import logging
import time
from typing import Any, List, Optional, Sequence, Union

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from .base_client import BaseLLMClient
from tradingagents.runtime_trace import emit_runtime_trace, format_elapsed

logger = logging.getLogger(__name__)

# Backend-specific CLI configurations
CLI_BACKEND_SPECS = {
    "claude": {
        "command": "claude",
        "subcommand": (),
        "prompt_flag": "-p",
        "model_flag": "--model",
        "output_format_flag": "--output-format",
        "output_format": "text",
        "prompt_stdin_sentinel": None,
        "output_file_flag": None,
        "output_mode": "stdout",
        "extra_args": (),
    },
    "codex": {
        "command": "codex",
        "subcommand": ("exec",),
        "prompt_flag": None,
        "model_flag": "--model",
        "output_format_flag": None,
        "output_format": None,
        "prompt_stdin_sentinel": "-",
        "output_file_flag": "--output-last-message",
        "output_mode": "output_file",
        "extra_args": ("--color", "never"),
    },
}

# Model name mapping: user-facing name → CLI model identifier
MODEL_MAPS = {
    # Claude CLI models
    "claude": {
        "claude-opus": "opus",
        "claude-sonnet": "sonnet",
        "claude-haiku": "haiku",
        "opus": "opus",
        "sonnet": "sonnet",
        "haiku": "haiku",
        "opus-4.8": "claude-opus-4-8",
        "opus-4-8": "claude-opus-4-8",
        "claude-opus-4-8": "claude-opus-4-8",
    },
    # Codex CLI models
    "codex": {
        "gpt-5.5": "gpt-5.5",
        "gpt-5.5-mini": "gpt-5.5-mini",
        "gpt-5.4": "gpt-5.4",
        "gpt-5.4-mini": "gpt-5.4-mini",
        "gpt-5-codex": "gpt-5-codex",
    },
}


def _tuple_to_role_content(message: tuple) -> tuple[str, Any] | None:
    """Normalize a two-item tuple message into (role, content)."""
    if not isinstance(message, tuple) or len(message) != 2:
        return None
    role, content = message
    return str(role), content


def _messages_to_prompt(messages: Union[str, List, Sequence[BaseMessage]]) -> str:
    """Convert various input formats to a single prompt string for CLI.

    Handles:
    - Plain string
    - List of LangChain BaseMessage objects
    - List of dicts with 'role' and 'content' keys
    - List of (role, content) tuples
    """
    if isinstance(messages, str):
        return messages

    parts = []
    for msg in messages:
        if isinstance(msg, BaseMessage):
            role = msg.type  # 'human', 'system', 'ai'
            content = msg.content
        elif isinstance(msg, dict):
            role = msg.get("role", "user")
            content = msg.get("content", "")
        elif _tuple_to_role_content(msg):
            role, content = _tuple_to_role_content(msg)
        else:
            parts.append(str(msg))
            continue

        if role in ("system",):
            parts.append(f"[System Instructions]\n{content}")
        elif role in ("human", "user"):
            parts.append(content)
        elif role in ("ai", "assistant"):
            parts.append(f"[Previous Assistant Response]\n{content}")
        else:
            parts.append(content)

    return "\n\n".join(parts)


class CLIChatModel(BaseChatModel):
    """LangChain-compatible chat model that delegates to a CLI subprocess."""

    cli_backend: str = "claude"
    cli_command: str = "claude"
    cli_subcommand: tuple[str, ...] = ()
    cli_prompt_flag: Optional[str] = "-p"
    cli_model_flag: str = "--model"
    cli_model: str = "sonnet"
    cli_output_format_flag: Optional[str] = "--output-format"
    cli_output_format: Optional[str] = "text"
    cli_prompt_stdin_sentinel: Optional[str] = None
    cli_output_file_flag: Optional[str] = None
    cli_output_mode: str = "stdout"
    cli_extra_args: tuple[str, ...] = ()
    cli_timeout: int = 300
    cli_max_retries: int = 2

    @property
    def _llm_type(self) -> str:
        return f"cli-{self.cli_backend}"

    @property
    def _identifying_params(self) -> dict:
        return {
            "cli_backend": self.cli_backend,
            "cli_command": self.cli_command,
            "cli_model": self.cli_model,
            "cli_timeout": self.cli_timeout,
        }

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager=None,
        **kwargs,
    ) -> ChatResult:
        """Generate a response by calling the CLI subprocess."""
        prompt_text = _messages_to_prompt(messages)
        response_text = self._call_cli(prompt_text)

        message = AIMessage(content=response_text, tool_calls=[])
        generation = ChatGeneration(message=message)
        return ChatResult(generations=[generation])

    def _build_command(self, output_path: Optional[str] = None) -> list[str]:
        cmd = [self.cli_command, *self.cli_subcommand]

        if self.cli_prompt_flag:
            cmd.append(self.cli_prompt_flag)

        if self.cli_model_flag:
            cmd.extend([self.cli_model_flag, self.cli_model])

        if self.cli_output_format_flag and self.cli_output_format:
            cmd.extend([self.cli_output_format_flag, self.cli_output_format])

        if output_path and self.cli_output_file_flag:
            cmd.extend([self.cli_output_file_flag, output_path])

        if self.cli_extra_args:
            cmd.extend(self.cli_extra_args)

        if self.cli_prompt_stdin_sentinel:
            cmd.append(self.cli_prompt_stdin_sentinel)

        return cmd

    def _extract_response_text(
        self,
        result: subprocess.CompletedProcess,
        output_path: Optional[str],
    ) -> str:
        if self.cli_output_mode == "output_file" and output_path:
            try:
                with open(output_path, "r", encoding="utf-8") as handle:
                    file_text = handle.read().strip()
            except OSError:
                file_text = ""
            if file_text:
                return file_text

        return result.stdout.strip()

    def _call_cli(self, prompt: str) -> str:
        """Execute the CLI command and return the response text.

        The prompt is delivered via stdin rather than as a command-line
        argument. This avoids three problems with passing very long prompts
        as argv:

        1. Prompt contents leak into `ps` / process listings.
        2. OS-level argv size limits (`ARG_MAX`) become a concern as
           prefetched market/fundamentals payloads grow.
        3. Shell-level quoting bugs become possible when prompts contain
           backticks, $, or other shell metacharacters.

        Backend-specific behavior:
        - Claude CLI reads the final text from stdout.
        - Codex CLI writes the final response to a temporary output file,
          which is more reliable than parsing event/log output from stdout.
        """
        last_error = None
        for attempt in range(1, self.cli_max_retries + 1):
            output_path = None
            run_started = None
            try:
                if self.cli_output_mode == "output_file":
                    with tempfile.NamedTemporaryFile(
                        prefix=f"{self.cli_backend}_cli_",
                        suffix=".txt",
                        delete=False,
                    ) as tmp:
                        output_path = tmp.name

                cmd = self._build_command(output_path=output_path)
                logger.info(
                    "CLI call attempt %d/%d: backend=%s command=%s model=%s (prompt length: %d chars, via stdin)",
                    attempt,
                    self.cli_max_retries,
                    self.cli_backend,
                    self.cli_command,
                    self.cli_model,
                    len(prompt),
                )
                emit_runtime_trace(
                    "cli.start",
                    backend=self.cli_backend,
                    model=self.cli_model,
                    attempt=f"{attempt}/{self.cli_max_retries}",
                    prompt_chars=len(prompt),
                    timeout=f"{self.cli_timeout}s",
                )
                run_started = time.perf_counter()

                result = subprocess.run(
                    cmd,
                    input=prompt,
                    capture_output=True,
                    text=True,
                    timeout=self.cli_timeout,
                )

                if result.returncode != 0:
                    stderr = result.stderr.strip()
                    # claude CLI writes usage-limit / auth / overload errors to
                    # stdout, not stderr — capture a snippet so the real cause is
                    # logged instead of an empty stderr.
                    stdout_snippet = (result.stdout or "").strip()[:600]
                    detail = stderr or stdout_snippet or "<no output>"
                    elapsed = (
                        format_elapsed(time.perf_counter() - run_started)
                        if run_started is not None
                        else None
                    )
                    last_error = RuntimeError(
                        f"CLI command failed (exit {result.returncode}): {detail}"
                    )
                    emit_runtime_trace(
                        "cli.fail",
                        backend=self.cli_backend,
                        model=self.cli_model,
                        attempt=f"{attempt}/{self.cli_max_retries}",
                        elapsed=elapsed,
                        exit_code=result.returncode,
                        stderr=stderr or "<empty>",
                        stdout=stdout_snippet or "<empty>",
                    )
                    logger.warning(
                        "CLI attempt %d failed (exit %d): stderr=%s | stdout=%s",
                        attempt,
                        result.returncode,
                        stderr or "<empty>",
                        stdout_snippet or "<empty>",
                    )
                    continue

                output = self._extract_response_text(result, output_path)
                if not output:
                    elapsed = (
                        format_elapsed(time.perf_counter() - run_started)
                        if run_started is not None
                        else None
                    )
                    last_error = RuntimeError("CLI returned empty output")
                    emit_runtime_trace(
                        "cli.empty",
                        backend=self.cli_backend,
                        model=self.cli_model,
                        attempt=f"{attempt}/{self.cli_max_retries}",
                        elapsed=elapsed,
                    )
                    logger.warning("CLI attempt %d returned empty output", attempt)
                    continue

                elapsed = (
                    format_elapsed(time.perf_counter() - run_started)
                    if run_started is not None
                    else None
                )
                emit_runtime_trace(
                    "cli.end",
                    backend=self.cli_backend,
                    model=self.cli_model,
                    attempt=f"{attempt}/{self.cli_max_retries}",
                    elapsed=elapsed,
                    response_chars=len(output),
                )
                logger.info(
                    "CLI call succeeded (response length: %d chars)", len(output)
                )
                return output

            except subprocess.TimeoutExpired:
                elapsed = (
                    format_elapsed(time.perf_counter() - run_started)
                    if run_started is not None
                    else f"{self.cli_timeout:.2f}s"
                )
                last_error = TimeoutError(
                    f"CLI command timed out after {self.cli_timeout}s"
                )
                emit_runtime_trace(
                    "cli.timeout",
                    backend=self.cli_backend,
                    model=self.cli_model,
                    attempt=f"{attempt}/{self.cli_max_retries}",
                    elapsed=elapsed,
                )
                logger.warning("CLI attempt %d timed out", attempt)
            except FileNotFoundError:
                raise FileNotFoundError(
                    f"CLI command '{self.cli_command}' not found. "
                    f"Make sure it is installed and available in PATH."
                )
            finally:
                if output_path and os.path.exists(output_path):
                    try:
                        os.unlink(output_path)
                    except OSError:
                        pass

        raise last_error

    def invoke(self, input, config=None, **kwargs):
        """Override invoke to handle both string and message inputs."""
        if isinstance(input, str):
            messages = [HumanMessage(content=input)]
        elif isinstance(input, list) and input and isinstance(input[0], dict):
            messages = []
            for msg in input:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "system":
                    messages.append(SystemMessage(content=content))
                elif role in ("user", "human"):
                    messages.append(HumanMessage(content=content))
                elif role in ("assistant", "ai"):
                    messages.append(AIMessage(content=content))
                else:
                    messages.append(HumanMessage(content=content))
            return super().invoke(messages, config, **kwargs)
        elif isinstance(input, list) and input and _tuple_to_role_content(input[0]):
            messages = []
            for msg in input:
                normalized = _tuple_to_role_content(msg)
                if normalized is None:
                    messages.append(HumanMessage(content=str(msg)))
                    continue
                role, content = normalized
                if role == "system":
                    messages.append(SystemMessage(content=str(content)))
                elif role in ("user", "human"):
                    messages.append(HumanMessage(content=str(content)))
                elif role in ("assistant", "ai"):
                    messages.append(AIMessage(content=str(content)))
                else:
                    messages.append(HumanMessage(content=str(content)))
            return super().invoke(messages, config, **kwargs)
        elif isinstance(input, list) and input and isinstance(input[0], BaseMessage):
            messages = input
        else:
            messages = [HumanMessage(content=str(input))]

        return super().invoke(messages, config, **kwargs)


class CLIClient(BaseLLMClient):
    """Client for CLI-based LLM tools.

    Supports Claude CLI and Codex CLI.
    """

    def __init__(
        self,
        model: str,
        base_url: Optional[str] = None,
        cli_backend: str = "claude",
        **kwargs,
    ):
        super().__init__(model, base_url, **kwargs)
        self.cli_backend = cli_backend.lower()

    def get_llm(self) -> Any:
        """Return configured CLIChatModel instance."""
        cli_config = CLI_BACKEND_SPECS.get(
            self.cli_backend,
            CLI_BACKEND_SPECS["claude"],
        )

        # Resolve model name
        model_map = MODEL_MAPS.get(self.cli_backend, {})
        cli_model = model_map.get(self.model, self.model)

        timeout = self.kwargs.get("timeout", 300)
        max_retries = self.kwargs.get("max_retries", 2)
        callbacks = self.kwargs.get("callbacks")
        extra_args = list(cli_config["extra_args"])
        effort = self.kwargs.get("effort")
        if self.cli_backend == "claude" and effort:
            extra_args.extend(["--effort", str(effort)])

        return CLIChatModel(
            cli_backend=self.cli_backend,
            cli_command=cli_config["command"],
            cli_subcommand=cli_config["subcommand"],
            cli_prompt_flag=cli_config["prompt_flag"],
            cli_model_flag=cli_config["model_flag"],
            cli_model=cli_model,
            cli_output_format_flag=cli_config["output_format_flag"],
            cli_output_format=cli_config["output_format"],
            cli_prompt_stdin_sentinel=cli_config["prompt_stdin_sentinel"],
            cli_output_file_flag=cli_config["output_file_flag"],
            cli_output_mode=cli_config["output_mode"],
            cli_extra_args=tuple(extra_args),
            cli_timeout=timeout,
            cli_max_retries=max_retries,
            callbacks=callbacks,
        )

    def validate_model(self) -> bool:
        """Validate model for CLI backend."""
        model_map = MODEL_MAPS.get(self.cli_backend)
        if model_map is None:
            return True
        return self.model in model_map or self.model in model_map.values()
        return True
