# VoxCPM HTTP Service

Async multi-user TTS service with SQLite, local file storage, reusable voice profiles, and server-side VoxCPM inference.

## Features

- API key based multi-user isolation
- Asynchronous job queue with polling-friendly job states
- Reusable user voice profiles
- Platform system voices supported by the data model and listing logic
- One-off reference-audio cloning jobs
- Local development with a fake provider and no model loading
- Production provider support for official `voxcpm`

## Project Layout

```text
src/tts_service/
  api/
  auth/
  db/
  providers/
  services/
  storage/
  worker/
tests/
```

## Local Development

Create a virtualenv and install dependencies:

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

Run the API with the fake provider:

```bash
TTS_SERVICE_PROVIDER=fake .venv/bin/uvicorn tts_service.main:create_app --factory --reload
```

Run the worker in a loop from a small wrapper script or process manager that repeatedly calls:

```python
import time

from tts_service.main import create_app
from tts_service.services.worker import WorkerService

app = create_app()
worker = WorkerService(
    session_factory=app.state.session_factory,
    file_storage=app.state.file_storage,
    provider=app.state.provider,
    job_service=app.state.job_service,
)

while True:
    processed = worker.process_next_job()
    if not processed:
        time.sleep(1.0)
```

## Production Server Setup

Install the service plus the inference runtime on the GPU server, not on the local development machine.

For the official VoxCPM runtime:

```bash
pip install voxcpm
```

Set:

```bash
export TTS_SERVICE_PROVIDER=voxcpm
export TTS_SERVICE_VOXCPM_MODEL_PATH=/srv/models/VoxCPM2-3B
export TTS_SERVICE_DATABASE_URL=sqlite:////srv/tts/storage/app.db
export TTS_SERVICE_STORAGE_ROOT=/srv/tts/storage
```

Then run:

```bash
uvicorn tts_service.main:create_app --factory --host 0.0.0.0 --port 8000
```

Start a separate worker process using the same environment.

## API Overview

### Auth

- `POST /debug/bootstrap-user`
- `POST /v1/auth/keys/verify`

### Voices

- `POST /v1/voices`
- `GET /v1/voices`

### Jobs

- `POST /v1/jobs`
- `GET /v1/jobs`
- `GET /v1/jobs/{job_id}`
- `POST /v1/jobs/{job_id}/cancel`
- `GET /v1/jobs/{job_id}/audio`

## Example Flow

Bootstrap a user:

```bash
curl -X POST http://127.0.0.1:8000/debug/bootstrap-user \
  -H 'Content-Type: application/json' \
  -d '{"name":"alice"}'
```

Create a reusable voice profile:

```bash
curl -X POST http://127.0.0.1:8000/v1/voices \
  -H "Authorization: Bearer ${API_KEY}" \
  -F "name=alice-voice" \
  -F "clone_mode=clone" \
  -F "consent_statement=owned by user" \
  -F "reference_audio=@reference.wav"
```

Create a queued job from a saved voice:

```bash
curl -X POST http://127.0.0.1:8000/v1/jobs \
  -H "Authorization: Bearer ${API_KEY}" \
  -H 'Content-Type: application/json' \
  -d '{"text":"hello world","voice_profile_id":"VOICE_ID"}'
```

Create a one-off clone job:

```bash
curl -X POST http://127.0.0.1:8000/v1/jobs \
  -H "Authorization: Bearer ${API_KEY}" \
  -F "text=hello world" \
  -F "clone_mode=ultimate_clone" \
  -F "reference_text=hello reference" \
  -F "reference_audio=@prompt.wav"
```

Check a job:

```bash
curl http://127.0.0.1:8000/v1/jobs/JOB_ID \
  -H "Authorization: Bearer ${API_KEY}"
```

Download output:

```bash
curl http://127.0.0.1:8000/v1/jobs/JOB_ID/audio \
  -H "Authorization: Bearer ${API_KEY}" \
  -o output.wav
```

## Notes

- The fake provider is the default and is intended for local API development and tests only.
- The official `voxcpm` provider lazily loads the model at first synthesis call, so app startup does not force local model loading.
- `nanovllm_voxcpm` is wired as an alternate provider slot, but its runtime integration should be completed and validated on the target server before production use.
