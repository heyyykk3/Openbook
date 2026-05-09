# Public Alpha Checklist

Status: brutal readiness gate, last reviewed 2026-05-09.

Public alpha means "useful, honest, and debuggable," not polished. OpenBook should launch only when a curious developer can install it, understand what it does, trust its boundaries, and recover cleanly when it disappoints them.

## Non-Negotiable Launch Criteria

- A fresh user can install OpenBook and create a repo-local memory book from the README alone.
- The default path does not require a hosted service, external database, or model provider account.
- The memory book location is obvious, documented, and easy to delete.
- At least two different coding-agent integration paths can read the same repo memory book.
- The docs explain what OpenBook stores, what it does not store, and who/what can write to it.
- Every command shown in public docs has been run successfully on a clean machine or clean container.
- There is a one-command smoke test for "initialize, write memory, search/read memory, inspect database." (`openbook smoke-test`)
- The project does not claim benchmark wins without published reproduction steps and raw data.
- Known limitations are visible before installation, not buried after the hype.

## Product Readiness

- Repository detection is deterministic and documented.
- Memory book creation is idempotent.
- Schema migrations are explicit, reversible where possible, and tested against an older sample database.
- Concurrent reads/writes from multiple agents do not corrupt the SQLite file.
- Failed writes are visible to the user or agent; they do not silently disappear.
- Search results include enough provenance for the agent to judge whether a memory is relevant.
- Stale or wrong memory can be corrected without hand-editing opaque blobs.
- There is a clear policy for memory confidence, source, timestamps, and supersession.
- Large repositories do not cause OpenBook to ingest or summarize the whole codebase by accident.
- The system works without network access after dependencies are installed.

## Agent Integration Readiness

- MCP configuration is documented for at least the primary intended clients.
- CLI usage is documented for agents that cannot or should not use MCP.
- Agents receive concise tool descriptions that discourage dumping chat transcripts into memory.
- Write paths require structured intent: decision, convention, task handoff, gotcha, command, or file note.
- Read paths support focused retrieval by query and by repository context.
- The same memory written by one agent can be found by another agent in a realistic follow-up task.
- Integration docs include failure modes: wrong repo, missing database, locked database, schema mismatch, and stale memory.
- Prompts/instructions tell agents when not to write memory.
- The public examples show mundane coding memories, not idealized demo memories.

## Documentation Readiness

- README answers in the first screen: what it is, who it is for, and what makes it different.
- README links to the comparison doc and this alpha checklist.
- Installation docs include prerequisites, exact commands, expected output, and uninstall/reset steps.
- "Why not just use X?" is answered with respect, especially for Mem0, Basic Memory, Cognee, Zep/Graphiti, Letta Code, and Memento MCP.
- The comparison does not misrepresent competitors or flatten them into strawmen.
- The docs state that OpenBook is early and benchmark results are pending.
- A troubleshooting page or section covers the top five expected alpha failures. (`docs/troubleshooting.md`)
- Security/privacy notes explain local storage, possible sensitive data, backups, sharing, and deletion.
- Contribution docs define what memory-related changes need tests.

## Benchmark And Evidence Readiness

- Benchmark tasks are defined before results are published.
- Fixtures are checked in or downloadable from stable public URLs.
- Reproduction commands include dependency installation, seed data, model/provider configuration, and expected artifacts.
- Raw outputs are saved, not only summarized.
- Failed runs are included or explicitly counted.
- Metrics distinguish retrieval quality, task completion, token cost, latency, and human cleanup burden.
- The harness compares against baselines fairly: no privileged OpenBook-specific prompts unless the competitor gets equivalent integration help.
- Results are dated and versioned by OpenBook commit, competitor version, model, provider, OS, and hardware/runtime assumptions.
- Public claims use cautious language: "in this benchmark" and "under these conditions."

## Security And Privacy Readiness

- The docs warn that memory may contain secrets if agents write them.
- There is guidance for excluding secrets, credentials, customer data, and private personal details.
- Users can inspect all stored memory without a proprietary viewer.
- Users can delete selected memories and wipe the whole book.
- Backups, sync, and checked-in database behavior are documented.
- The default docs say whether the SQLite file should be committed to git.
- There is a documented path for reporting security issues.
- Tool descriptions and prompts discourage storing API keys, tokens, passwords, private keys, and full customer records.

## Strong Launch Criteria

These are not required for a minimal alpha, but they decide whether the launch earns trust:

- A 3-minute demo using two different coding agents on the same repository.
- A small, reproducible benchmark that shows both wins and failures.
- A "memory hygiene" command or documented workflow for reviewing stale records.
- A migration/export command that makes users feel they own the data.
- A sample repository with realistic memories and tasks.
- A public issue template for false memories, retrieval misses, integration bugs, and docs confusion.
- A clear roadmap that names what OpenBook will not become.
- Screenshots or terminal recordings that match the actual CLI output.
- A launch post that leads with the problem and constraints, not grand claims.

## Red Flags: Delay The Launch

- Any public doc says or implies OpenBook beats competitors before reproducible data exists.
- The happy path requires undocumented local state.
- Another coding agent cannot read memory written by the first one.
- The SQLite file can be corrupted by normal concurrent use.
- The reset/delete story is unclear.
- The project cannot explain when memory should expire or be superseded.
- Setup requires editing more than one config file without a copy-paste example.
- The docs hide current weaknesses.
- A new user cannot tell whether OpenBook is a memory substrate, a coding agent, or a knowledge graph product.

## Alpha Messaging

Use this framing:

"OpenBook is a public alpha for repo-local memory shared by coding agents. It stores a local SQLite memory book in or near your repository so different agents can reuse project decisions, conventions, gotchas, and handoff notes. It is early. We are publishing it now to test the workflow, harden integrations, and gather reproducible evidence before making performance claims."

Avoid this framing:

"OpenBook is the universal memory layer for AI agents."

"OpenBook replaces Mem0, Cognee, Zep, Letta, or Basic Memory."

"OpenBook gives coding agents perfect long-term memory."
