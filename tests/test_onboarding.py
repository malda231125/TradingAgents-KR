from cli.onboarding import collect_onboarding_status


def test_onboarding_status_detects_missing_cli_and_keys():
    status = collect_onboarding_status(environ={}, which=lambda _: None)

    assert not status.has_cli_runtime
    assert not status.is_ready_for_full_korea_research
    assert set(status.missing_api_groups) == {"KIS", "Naver News", "DART", "ECOS"}


def test_onboarding_status_accepts_any_supported_cli():
    def only_codex(command):
        return "/usr/local/bin/codex" if command == "codex" else None

    status = collect_onboarding_status(environ={}, which=only_codex)

    assert status.has_cli_runtime
    assert status.installed_cli["codex"] == "/usr/local/bin/codex"
    assert status.installed_cli["claude"] is None


def test_onboarding_status_ready_when_cli_and_required_keys_exist():
    environ = {
        "KIS_APP_KEY": "x",
        "KIS_APP_SECRET": "x",
        "NAVER_CLIENT_ID": "x",
        "NAVER_CLIENT_SECRET": "x",
        "DART_API_KEY": "x",
        "ECOS_API_KEY": "x",
    }

    status = collect_onboarding_status(
        environ=environ,
        which=lambda command: f"/bin/{command}" if command == "claude" else None,
    )

    assert status.has_cli_runtime
    assert status.missing_api_groups == {}
    assert status.is_ready_for_full_korea_research
