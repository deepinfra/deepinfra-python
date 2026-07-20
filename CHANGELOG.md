# Changelog

## 0.2.0 (2026-07-10)

- New feature: **Sandboxes** — `Sandbox.create/from_id/list`, `exec`,
  `run_python`, `fs.read/write`, `stop/start/terminate`, context managers, and
  async twins (`acreate`, `aexec`, ...) for everything. `stop()`/`start()`
  block until the state transition completes (`wait=False` to fire-and-forget),
  so `sb.stop(); sb.start()` never races the server.
- New unified `DeepInfraClient` built on httpx (sync + async, pooled
  connections, explicit timeouts, typed errors, retry policy: connect-error
  retries where marked, 502/503/504 retries only on GETs).
- Typed exception hierarchy under `deepinfra` /`deepinfra.exceptions`;
  `MaxRetriesExceededError` is now a subclass of `APIConnectionError`.
  429 maps to `RateLimitError` (`TooManySandboxesError` is an alias), and
  `SandboxTimeoutError`/`SandboxFailedError` carry `.sandbox_id` so a failed
  `Sandbox.create(wait=True)` can still be cleaned up.
- The inference wrappers (`TextGeneration`, `Embeddings`,
  `AutomaticSpeechRecognition`, `TextToImage`) keep their public API but now
  run on the unified client; `requests`/`requests-toolbelt` dependencies
  replaced by `httpx` + `pydantic`.
- `from deepinfra import TextGeneration` now works (it was missing from the
  package exports in 0.1.0).
- Packaging modernized: pyproject (hatchling), `py.typed`, Python >= 3.9.

Breaking (low impact):
- `DeepInfraClient(url, token)` positional constructor replaced by
  `DeepInfraClient(api_key=..., base_url=...)` with per-request paths.
- Network failures raise SDK exceptions instead of `requests` exceptions.

## 0.1.0 (2024-03-21)

- Initial release: inference API wrappers over `requests`.
