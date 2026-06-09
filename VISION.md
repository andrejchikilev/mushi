# Mushi Vision

Mushi owns task context.

Agents are replaceable.

Sessions are first-class objects.

A task must survive:

- model changes
- backend changes
- machine changes
- agent restarts

Mushi is not a wrapper around a single coding agent.

Mushi is a persistent task and session manager for coding agents.

Core principles:

- Store durable task context outside agent-specific chats.
- Treat Cursor, OpenCode, Claude Code, Codex, and Aider as interchangeable backends.
- Keep work and personal profiles isolated.
- Prefer explicit handoffs over hidden agent memory.
- Use filesystem storage first.
- Keep the MVP simple and inspectable.
