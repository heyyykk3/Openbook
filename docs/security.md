# Security

OpenBook is designed with security as a first-class concern.

## .openbookignore

OpenBook ships with a default `.openbookignore` that excludes:

- `.git`
- `node_modules`, `vendor`
- `dist`, `build`
- `.env` files
- Secrets and private keys
- Generated lockfiles
- Large binary files

You can customize `.openbookignore` for your project.

## Secret Scanning

Before storing any memory, OpenBook scans for common secret patterns:
- API keys
- Passwords
- Tokens
- Private keys
- AWS credentials
- GitHub tokens
- OpenAI keys

If secrets are detected, the memory is **quarantined** instead of approved.

## Redaction

Context packs redact obvious secrets before returning results to agents.

## Quarantine

Quarantined memories:
- Are not included in search results
- Can be reviewed and deleted
- Are flagged for human inspection

## Deletion and Wipe

You can delete individual memories or perform a full local wipe:

```bash
# Delete a specific memory (future feature)
# Full wipe
rm -rf .openbook
```

## Provenance

Every memory tracks:
- Creating agent
- Session ID
- Timestamp
- Source citation

This ensures memories are auditable.

## Never Store Intentionally

OpenBook will never intentionally store:
- API keys
- Passwords
- Private keys
- Personal access tokens

Provider credentials should be supplied through environment variables such as `GEMINI_API_KEY` or `OPENAI_API_KEY`. `.env` files are ignored by git; `.env.example` is the only dotenv file intended for source control.

If you find a case where secrets leak, please report it.
