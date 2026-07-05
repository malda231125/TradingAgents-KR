import os
import shutil
from dataclasses import dataclass
from typing import Callable, Mapping


CLI_INSTALL_GUIDES = {
    "codex": {
        "label": "Codex CLI",
        "command": "npm install -g @openai/codex && codex login",
        "link": "https://github.com/openai/codex",
    },
    "claude": {
        "label": "Claude Code CLI",
        "command": "npm install -g @anthropic-ai/claude-code && claude",
        "link": "https://docs.anthropic.com/en/docs/claude-code",
    },
}


API_KEY_GUIDES = {
    "KIS": {
        "env": ("KIS_APP_KEY", "KIS_APP_SECRET"),
        "link": "https://apiportal.koreainvestment.com/",
    },
    "Naver News": {
        "env": ("NAVER_CLIENT_ID", "NAVER_CLIENT_SECRET"),
        "link": "https://developers.naver.com/apps/#/register",
    },
    "DART": {
        "env": ("DART_API_KEY",),
        "link": "https://opendart.fss.or.kr/",
    },
    "ECOS": {
        "env": ("ECOS_API_KEY",),
        "link": "https://ecos.bok.or.kr/api/",
    },
}


@dataclass(frozen=True)
class OnboardingStatus:
    installed_cli: dict[str, str | None]
    missing_api_groups: dict[str, dict[str, object]]

    @property
    def has_cli_runtime(self) -> bool:
        return any(self.installed_cli.values())

    @property
    def is_ready_for_full_korea_research(self) -> bool:
        return self.has_cli_runtime and not self.missing_api_groups


def collect_onboarding_status(
    environ: Mapping[str, str] | None = None,
    which: Callable[[str], str | None] = shutil.which,
) -> OnboardingStatus:
    """Collect local setup status without printing secrets."""
    env = environ if environ is not None else os.environ
    installed_cli = {
        name: which(name)
        for name in CLI_INSTALL_GUIDES
    }
    missing_api_groups: dict[str, dict[str, object]] = {}

    for group, guide in API_KEY_GUIDES.items():
        env_names = tuple(guide["env"])
        missing = [name for name in env_names if not str(env.get(name, "")).strip()]
        if missing:
            missing_api_groups[group] = {
                "missing": missing,
                "link": guide["link"],
            }

    return OnboardingStatus(
        installed_cli=installed_cli,
        missing_api_groups=missing_api_groups,
    )
