# Public Release Security Checklist

Use this checklist before making the repository public or cutting a release.

## Secrets that must never be committed

- `.env`
- KIS app key / secret
- KIS account number or real trading account identifiers
- Naver Client ID / Client Secret
- DART API key
- ECOS API key
- FRED API key
- Notion API token
- Telegram bot token / chat ID
- OpenAI / Anthropic / Google API keys
- Personal email addresses in `SEC_USER_AGENT`
- Private Notion report URLs
- Private local paths such as `<private-home>/.openclaw/...` in public docs

## Required checks

```bash
git status --short

grep -RIn --exclude-dir=.git --exclude-dir=.venv --exclude-dir=__pycache__ --exclude=.env \
  -E 'NOTION_API_TOKEN|KIS_APP|KIS_SECRET|DART_API_KEY|ECOS_API_KEY|FRED_API_KEY|OPENAI_API_KEY|sk-[A-Za-z0-9]|app\.notion\.com|/root/\.openclaw' .
```

The grep command may find documentation references to variable names. That is fine. It must not reveal real values.

## Files that should exist before public release

- `.env.example`
- `.gitignore`
- `README.md`
- `LICENSE`
- `NOTICE.md`
- `CREDITS.md`
- `docs/configuration.md`
- `docs/data-sources.md`
- `docs/architecture.md`
- `examples/reports/*-demo.md`

## Safe demo policy

Demo reports should be:

- generated from public market data only
- sanitized
- clearly labeled as examples
- free of private comments, account data, personal positions, or real trades
- marked as not financial advice

## Runtime safety

- This project is for analysis and research.
- Do not expose order or account APIs in public examples.
- Do not present generated outputs as guaranteed investment returns.
- Always include a financial-risk disclaimer in README and sample reports.
