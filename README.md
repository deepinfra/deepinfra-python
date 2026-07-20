# deepinfra

[![CI](https://github.com/deepinfra/deepinfra-python/actions/workflows/ci.yml/badge.svg)](https://github.com/deepinfra/deepinfra-python/actions/workflows/ci.yml)
[![PyPI version](https://badge.fury.io/py/deepinfra.svg)](https://pypi.org/project/deepinfra/)
[![Python Version](https://img.shields.io/pypi/pyversions/deepinfra.svg)](https://pypi.org/project/deepinfra/)
[![License](https://img.shields.io/github/license/deepinfra/deepinfra-python.svg)](LICENSE)

The official Python SDK for the [DeepInfra](https://deepinfra.com) API:
**Sandboxes** (isolated microVMs for running untrusted code) and inference.

## Installation

```bash
pip install deepinfra
```

Authentication uses your DeepInfra API key — pass `api_key=` or set the
`DEEPINFRA_API_KEY` environment variable (the same key you use for inference,
from [deepinfra.com/dash/api_keys](https://deepinfra.com/dash/api_keys)).

## Sandboxes

Create an isolated Linux microVM, run bash/python inside it, move files in and
out, and tear it down — in a few lines:

```python
from deepinfra import Sandbox

sb = Sandbox.create(plan="medium", timeout="10m")     # blocks until running

r = sb.exec("bash", "-c", "pip install pandas && python -c 'import pandas; print(pandas.__version__)'")
print(r.stdout, r.stderr, r.returncode)

out = sb.run_python("print(21 * 2)").check()          # .check() raises on non-zero exit
print(out.stdout)                                     # "42"

sb.fs.write("/work/in.csv", b"a,b\n1,2\n")
data = sb.fs.read("/work/in.csv")

sb.stop()        # frees compute, keeps disk; blocks until stopped
sb.start()       # resumes on the same disk; blocks until running
sb.terminate()   # deletes the sandbox (stays fetchable by id as "deleted" briefly)
```

Every network method has an async twin prefixed with `a`:

```python
sb = await Sandbox.acreate(plan="small")
r = await sb.aexec("uname", "-a")
await sb.aterminate()
```

The zero-config async calls share one process-wide client whose connection
pool binds to the first event loop that uses it. If your program calls
`asyncio.run()` more than once, create a `DeepInfraClient` per loop and pass
it via `client=` (closing it with `await client.aclose()` before the loop
exits), instead of relying on the default client.

Useful patterns:

```python
# Auto-terminate with a context manager
with Sandbox.create(plan="small") as sb:
    sb.run_python("open('/work/out.txt', 'w').write('hi')")
    print(sb.fs.read("/work/out.txt"))

# Find existing sandboxes
sb = Sandbox.from_id("sb_...")
etl_boxes = Sandbox.list(tags={"job": "etl-42"})

# Large scripts: upload, then run
sb.fs.write("/work/script.py", open("script.py").read())
sb.exec("python3", "/work/script.py", timeout="30m")
```

Errors are typed: `AuthenticationError` (401), `NotFoundError` (404),
`ConflictError` (409, e.g. exec on a stopped sandbox), `RateLimitError`
(429; for sandboxes that's the per-account cap — `TooManySandboxesError` is
an alias), `CapacityError` (503), plus SDK-side `SandboxTimeoutError` /
`SandboxFailedError` / `CommandFailedError`. If `Sandbox.create(wait=True)`
fails while waiting, the raised error carries `.sandbox_id` so you can
inspect or terminate the sandbox it created.

Roadmap (API designed, lands in an upcoming release): `exec_stream` (live
output), `snapshot()` / `Sandbox.from_snapshot()`, `expose_port()`,
`fs.upload_dir()`.

## Inference

The inference wrappers predate the SDK's OpenAI-compatible endpoints and remain
supported:

### Automatic Speech Recognition

```python
from deepinfra import AutomaticSpeechRecognition

asr = AutomaticSpeechRecognition("openai/whisper-base")

body = {"audio": "path/to/audio/file"}  # or a URL, or raw bytes
transcription = asr.generate(body)
print(transcription.text)
```

### Text Generation

```python
from deepinfra import TextGeneration

llm = TextGeneration("mistralai/Mixtral-8x22B-Instruct-v0.1")
res = llm.generate({"input": "What is the capital of France?"})
print(res.results[0].generated_text)
```

`Embeddings` and `TextToImage` work the same way. For chat-style LLM usage you
can also point the official OpenAI client at
`https://api.deepinfra.com/v1/openai`.

## Development

```bash
pip install -e ".[dev]"
pytest tests          # unit tests (no network)
mypy && ruff check .  # types + lint
```
