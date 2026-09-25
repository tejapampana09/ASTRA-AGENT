# ASTRA 2.0 — Tool Registry

## Registered Tools

| Category | Tool Name | Description | Risk Level |
|---|---|---|---|
| Filesystem | `read_file` | Read file contents inside workspace | `READ` |
| Filesystem | `search_files` | Find files by glob pattern | `READ` |
| Filesystem | `create_file` | Create new file with content | `LOW` |
| Filesystem | `edit_file` | Target snippet replacement | `LOW` |
| Filesystem | `delete_file` | Delete file inside workspace | `MEDIUM` |
| Terminal | `run_command` | Execute sandboxed shell command | `HIGH` / `LOW` (tests) |
| Git | `git_status` | Working tree status | `READ` |
| Git | `git_diff` | Diff against HEAD | `READ` |
| Git | `git_commit` | Stage & commit changes | `MEDIUM` |
| Git | `git_branch` | List/create branches | `MEDIUM` |
| Git | `git_checkout` | Switch branches | `MEDIUM` |
| GitHub | `github_issues` | Fetch issue specifications | `READ` |
| GitHub | `github_pull_requests` | Inspect or open PR | `HIGH` |
