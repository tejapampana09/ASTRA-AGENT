# ASTRA-AGENT code audit and fixes

Reviewed on October 25, 2026. Base: `main` at
`40e02f8011bc82bae9196bf4930a2508f58cdca3`.
The audit and validation were completed locally before publication. The user subsequently authorized committing and pushing these fixes to `main`.

## Outcome

The runtime keeps its existing controller/provider/tool architecture. This change
fixes confirmed authorization, execution lifecycle, quota accounting, persistence,
verification, and desktop integration defects. It adds regression coverage and CI.
It does not establish that every possible defect has been eliminated.

## Prioritized findings and implemented changes

| Priority | Finding | Files and resulting behavior |
| --- | --- | --- |
| P0 | Repeated workspace changes expanded trusted roots through each new parent. | `astra/server.py`: approved roots are captured at startup; no implicit parent trust. Start, resume, and rollback revalidate stored or supplied workspace paths. Case-insensitive credential-directory checks and resolved paths block symlink escapes. |
| P0 | WebSockets did not enforce missing-token fail-closed behavior; metadata reads were unprotected. | `astra/server.py`: common constant-time credential verification, protected metadata endpoints, WebSocket origin validation, and actual ASGI listener/client checks. External exposure without a token fails closed even when an alternate launcher bypasses `run_server`. |
| P1 | Concurrent starts, resume, cancel/restart, deletion, or rollback could overlap a live session worker. | `astra/server.py`: atomic reservation under a lock, thread-liveness checks, 409 conflicts, and cleanup in `finally`. Cancellation does not release the reservation until execution exits. Unknown session IDs return 404; changing a session workspace requires a new session. |
| P1 | Checkpoint managers loaded records across unrelated sessions and workspaces. | `astra/checkpoints.py`, `astra/controller.py`, `astra/server.py`: production managers are session-scoped; persisted records are matched to workspace. Cross-session rollback is rejected. Failed text snapshot reads cannot become deletion snapshots. Restore errors are reported instead of silent success. |
| P1 | Generic quota wording was mistaken for daily exhaustion; daily cooldowns lasted an arbitrary 24 hours. | `astra/llm.py`, `astra/quota.py`: inspect structured quota dimensions and retry delays, distinguish daily limits from temporary throttling, and calculate the next midnight in `America/Los_Angeles`, including daylight saving. Cooldowns persist across process restarts and are scoped by project/model. |
| P1 | Iteration limits did not limit total model requests; fallback and optional auxiliary calls consumed quota. | `astra/quota.py`, `astra/llm.py`, `astra/config.py`, `astra/agent.py`, `astra/controller.py`: atomic SQLite reservations, cumulative session budgets across providers, configurable Gemini minute/day caps per model, serialized Gemini transport, one SDK attempt per reservation, and no SDK automatic function execution. Classification defaults to deterministic; cosmetic summary calls are removed. |
| P1 | Desktop sent no configured credential and connected to a global socket that did not receive private task events. | `desktop/electron/main.ts`, `desktop/src/api.ts`, `desktop/src/App.tsx`: desktop launches a token-authenticated backend; main injects credentials only into its trusted renderer's backend traffic. Session-specific subscriptions are acknowledged before task submission; cleanup cannot schedule ghost reconnects. Backend readiness uses health/auth responses instead of just an open port. |
| P1 | Electron IPC could open arbitrary paths using OS file associations. | `desktop/electron/main.ts`: validate sender, resolve selected roots and target real paths, reject escapes and dangerous paths. Reveal files in their folder instead of executing file associations. Navigation permits only the actual bundled entry point or expected dev origin. |
| P1 | Saved tool history lost call IDs, tool names, and native Gemini response metadata, breaking resume. | `astra/session.py`, `astra/agent.py`, `astra/llm.py`, `astra/server.py`: migrate old message tables, persist metadata including thought signatures, restore native contents, and pass saved history into follow-up tasks. Hidden system/tool records are filtered from the chat transcript. Session deletion removes dependent private records. |
| P1 | TypeScript checking combined a command list with `shell=True` and could run the wrong command on POSIX. | `astra/verifier.py`: run the installed project-local TypeScript compiler through Node without a shell. Use the active Python interpreter for pytest. Missing tools and no-check situations do not report success. |
| P1 | Command cancellation referenced an unimported module; command failures were labeled successful; output was unbounded in memory before truncation. | `astra/tools.py`: working cancellation monitor, process-group termination/escalation and reaping, bounded head/tail capture while draining both pipes, actual command-timeout cap, and nonzero-exit failure propagation. |
| P2 | Four distinct repository reads were treated as stagnation, discouraging useful audit work. | `astra/progress.py`: only repeated equivalent read actions trigger that heuristic; exploring different files remains progress. |
| P2 | Usage dashboard displayed fabricated counts/charts and settings only changed React state. | `astra/quota.py`, `astra/server.py`, desktop API/modals: usage comes from recorded attempts and available token metadata; settings are validated and applied to the running backend. Settings updates are blocked while workers run. |
| P2 | Completion status and summary generation could claim verification without recorded checks. | `astra/agent.py`, `astra/verifier.py`: explicit `not_run`/inconclusive states; summaries preserve the actual answer and recorded verification instead of requesting cosmetic success claims. |
| P2 | File explorer could enumerate external symlink targets; protected credential directories were checked only by filename. | `astra/workspace.py`, `astra/tools.py`: contain resolved tree entries; protect credential/repository metadata directory components. Missing question handlers now return an error rather than inventing a user's answer. |
| P2 | CLI runtime dependency was missing and launchers swallowed argument-error exit codes. | `requirements.txt`, `astra.py`, `astra/cli.py`: declare `rich`, preserve `SystemExit`, and use exit 130 for interruption. Upgrade the Google SDK to the tested 1.x API and add portable timezone data. Environment values take precedence over `.env`, including desktop-generated credentials. |

## Gemini RPD behavior and configuration

A model-driven tool loop can make one completion for every round. A 30-round
limit previously permitted around 32 application completions with classification
and summary rewriting, before provider fallbacks or SDK retries. Concurrent
workers made this worse. This explains a plausible consumption mechanism; it is
not a measurement of the user's Google account.

Google documents independent RPM, TPM, and RPD constraints, project-level limits,
and midnight-Pacific RPD resets:
https://ai.google.dev/gemini-api/docs/rate-limits

The new defaults are **local safety caps**, not provider entitlements:

```dotenv
ASTRA_MAX_LLM_CALLS_PER_TASK=20
ASTRA_GEMINI_RPM_BUDGET=5
ASTRA_GEMINI_RPD_BUDGET=50
ASTRA_GEMINI_PROJECT_ID=your-google-project-id
ASTRA_LLM_CLASSIFICATION=false
```

The historical `MAX_LLM_CALLS_PER_TASK` name represents a **cumulative session
budget**, so restarting/resuming the same session cannot bypass it. Create a new
session for a new budget. A zero cap disables that individual check. Set caps
below the active limits shown for the actual project/model in AI Studio.
A request attempt, including a failed request, consumes a local reservation;
local counters deliberately do not assume Google refunded a failure.

All ASTRA processes sharing a Google project should use the same project ID and
`ASTRA_DATA_DIR`. The default project bucket is shared conservatively when no ID
is supplied, so key rotation does not silently reset the local daily counter.
Different model buckets are tracked separately; shared provider quota groups may
require additional grouping for the user's account.

No API keys or prompts are stored in the usage ledger. It stores provider/model,
local session budget key, timestamps, outcomes, and reported token metadata.
The usage dashboard labels these as **local recorded attempts**. Calls from
other applications, machines, or separate data directories are not included.
Token metadata is recorded when available; this patch does not implement a TPM
admission limiter or an authoritative query of Google's remaining quota.

Transient failures use a bounded cooldown and existing ordered provider fallback;
there is no retry loop consuming requests while a daily quota is exhausted.
Fallback can still send context to another configured cloud provider, as in the
original application. Configure only providers you intend to use.

## Workspace and desktop operation

By default, the backend trusts only its startup workspace, not its parent.
Configure additional approved roots explicitly before starting the server:

```dotenv
ASTRA_ALLOWED_WORKSPACES=/absolute/path/project-one,/absolute/path/project-two
```

On Windows, use absolute Windows paths separated by commas. The native folder
picker does not silently widen backend authorization; selections outside these
roots are rejected. This is intentional, and the error should be resolved by
configuring the desired root and restarting.

The desktop generates a runtime API token when launching its own backend. To
reuse an already running backend, launch desktop with that server's token in
`ASTRA_API_TOKEN`; otherwise stop the old server first. The generated token is
kept in main-process state rather than exposed through the preload bridge.
The child server allows the packaged renderer's `null` origin with token auth;
websocket and REST credentials are still mandatory in desktop mode.

Settings changed in the UI apply to the current running server; use `.env` for
startup defaults. `.env` no longer overrides values explicitly set in the launch
environment.

## Validation performed

- Python 3.12: **137 tests passed**. Includes 37 added regression cases, including
  concurrency, actual network exposure, persisted quotas, Pacific DST boundaries,
  cross-session rollback, message migration/metadata, cancellation, multi-megabyte
  stdout/stderr capture, and a real TypeScript compiler rejecting invalid types.
- Desktop Node test runner: **3 tests passed**, covering subscription readiness,
  reconnect cleanup, and Electron IPC trust/path/reveal behavior with mocked OS APIs.
- `npm run build`: passed (TypeScript and production Vite bundle).
- `npm run build:electron`: passed.
- `python astra.py --help`: passed.
- `python -m pip check`: passed in the validation environment.
- `npm audit --omit=dev --json`: zero reported production dependency vulnerabilities
  at review time. This does not cover Electron/dev dependencies or prove absence
  of vulnerabilities.
- `git diff --check`: passed.
- Added `.github/workflows/ci.yml` for Python 3.10/3.12/3.13 tests and desktop checks.
  The workflow was prepared locally; its GitHub run status must be checked after publication.

The local environment emitted a Starlette/httpx TestClient deprecation warning
and a Vite config module-format warning. Neither caused test/build failures.

## Material limits and follow-up validation

- No live Gemini request was made and no Google project usage/billing was accessed.
  Exact provider limits and the original quota incident still need a redacted
  error payload plus the affected project's AI Studio usage.
- Native Electron window launch, Windows installer packaging, OS keychain behavior,
  and Windows process cancellation were not exercised here. Desktop tests use
  mocked OS APIs; builds validate compilation and bundling.
- The API session worker lock protects one server process. Run a **single Uvicorn
  worker**. Separate server processes need a shared job coordinator for task locks.
  Gemini transport serialization also applies within one process; SQLite budget
  reservations are atomic across processes sharing the ledger.
- Shell execution and project tests run with the host user's privileges. File-tool
  containment and command approvals are **not an OS sandbox**. A container or other
  OS isolation is necessary before executing untrusted repositories. The command
  classifier remains a heuristic, not a complete parser/security boundary.
- Checkpoints are text snapshots for explicitly tracked file-tool changes. They
  are not complete filesystem transactions and do not guarantee rollback of arbitrary
  shell-command side effects, binary files, or concurrent user edits.
- Reconnected sockets restore the subscription but do not replay every missed event.
  Persisted session messages/status remain the recovery source.
- Provider SDK/model availability and quotas can change; consult current provider
  model catalogs and account limits. Health metadata that says a key is configured
  does not prove the provider will accept an inference request.

## Apply and review

The accompanying patch targets the base SHA above and includes new files.
On a clean checkout of that commit:

```bash
git apply --check ASTRA-AGENT-fixes.patch
git apply ASTRA-AGENT-fixes.patch
python -m pip install -r requirements.txt
python -m pytest -q
cd desktop
npm ci --ignore-scripts
npm test
npm run build
npm run build:electron
```

For actually launching Electron after `--ignore-scripts`, install its binary with
`node node_modules/electron/install.js` or perform a regular `npm ci` in a trusted
checkout. The source ZIP excludes `.git`, dependencies, build outputs, databases,
credentials, and caches. Publication to `main` was separately authorized by the user.
