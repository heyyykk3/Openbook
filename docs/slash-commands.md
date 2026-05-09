# Slash Commands

Agents that support slash commands can use OpenBook via the `/openbook` command.

## Primary Command

```
/openbook
```

## Short Alias

```
/ob
```

## Available Commands

### `/openbook init`
Initialize OpenBook in the current project.

### `/openbook remember <text>`
Store a memory. Example:
```
/openbook remember "Tests run with pytest -q"
```

### `/openbook search <query>`
Search memories. Example:
```
/openbook search "how do tests run?"
```

### `/openbook brief`
Get a small project briefing.

### `/openbook handoff`
Create a handoff context pack for the next agent.

### `/openbook review`
Show pending memory proposals.

### `/openbook export`
Generate Markdown/JSON human-readable exports.

### `/openbook doctor`
Check database, config, providers, and MCP setup.

## Notes

Not all agents support slash commands. For agents that do not, use the MCP tools or CLI directly.
