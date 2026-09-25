# ASTRA 2.0 — Security & Sandboxing Architecture

## Security Principles

1. **Untrusted Codebase Assumption**: All user repositories and files are treated as untrusted input.
2. **Workspace Isolation**: Workspaces reside in isolated sandbox directories with strict path validation forbidding directory traversal (`../`).
3. **Command Filtering**: Terminal execution blocks dangerous destructive patterns (`rm -rf /`, `mkfs`, fork bombs, etc.).
4. **Human In The Loop**: High risk operations (`git push`, `github_create_pr`, production commands) halt execution until explicit human authorization is granted.
5. **Prompt Injection Defense**: Repository content is sanitized to prevent prompt injections from overriding ASTRA's system instructions.
