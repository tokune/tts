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

If you prefer file-based local configuration, copy `.env.example` to `.env` in the repository root. The service now loads that file automatically. Explicit `overrides` and exported shell variables still take precedence over `.env`.

Run the API with the fake provider:

```bash
TTS_SERVICE_PROVIDER=fake .venv/bin/uvicorn tts_service.main:create_app --factory --reload
```

Run the worker as a separate process:

```bash
TTS_SERVICE_PROVIDER=fake .venv/bin/tts-worker --poll
```

Process a single queued job and exit:

```bash
TTS_SERVICE_PROVIDER=fake .venv/bin/tts-worker --once
```

## Production Server Setup

Install the service plus the inference runtime on the GPU server, not on the local development machine.

Create and activate a dedicated Conda environment before starting `uvicorn`. This repository uses a `src/` layout, so launching a system-wide `uvicorn` without first installing the package will fail with `ModuleNotFoundError: No module named 'tts_service'`.

```bash
conda create -n voxcpm_env python=3.11
conda activate voxcpm_env
cd /srv/tts
pip install -e .
```

If you pull new code that adds or changes console scripts such as `tts-worker`, run `pip install -e .` again in the same environment so the entrypoint script is refreshed.

For the official VoxCPM runtime:

```bash
pip install voxcpm
```

Set:

```bash
export TTS_SERVICE_PROVIDER=voxcpm
# Use either a real local model directory or a Hugging Face repo id such as openbmb/VoxCPM2
export TTS_SERVICE_VOXCPM_MODEL_PATH=openbmb/VoxCPM2
export TTS_SERVICE_DATABASE_URL=sqlite:////root/tts/storage/app.db
export TTS_SERVICE_STORAGE_ROOT=/srv/tts/storage
export TTS_SERVICE_SYSTEM_VOICES_MANIFEST_PATH=/root/tts/system_voices.json
```

Then run:

```bash
uvicorn tts_service.main:create_app --factory --host 0.0.0.0 --port 8000
```

Start a separate worker process using the same environment:

```bash
tts-worker --poll
```

The worker now emits text logs for startup, idle polling, job progress, failures, and official VoxCPM model loading. Example:

```text
2026-04-08 17:20:01,234 INFO tts_service.worker.cli starting worker mode=poll poll_interval=1.00s provider=OfficialVoxCPMProvider model_path=openbmb/VoxCPM2
2026-04-08 17:20:05,912 INFO tts_service.providers.official_voxcpm loading VoxCPM model model_path=openbmb/VoxCPM2
2026-04-08 17:22:41,101 INFO tts_service.providers.official_voxcpm loaded VoxCPM model model_path=openbmb/VoxCPM2
2026-04-08 17:22:41,104 INFO tts_service.services.worker processing job job_id=123 request_mode=base_tts voice_profile_id=None
2026-04-08 17:22:44,887 INFO tts_service.services.worker job succeeded job_id=123 output_audio_path=/srv/tts/storage/jobs/123/output.wav
```

For one-shot processing or debugging:

```bash
tts-worker --once
```

If `tts-worker: command not found` appears, either the environment is not activated or the package has not been reinstalled since the script was added. In that case, re-run `pip install -e .` in the active environment, or start the worker through that interpreter directly:

```bash
python -m tts_service.worker.cli --poll
```

Activate `voxcpm_env` in every shell that starts the API or worker process.
Do not mix interpreters, for example by installing the project into `voxcpm_env` and then starting `uvicorn` from a different Python environment.

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

Create a queued job with the provider default voice:

```bash
curl -X POST http://127.0.0.1:8000/v1/jobs \
  -H "Authorization: Bearer ${API_KEY}" \
  -H 'Content-Type: application/json' \
  -d '{"text":"hello world"}'
```

List voices to find a preset system voice:

```bash
curl http://127.0.0.1:8000/v1/voices \
  -H "Authorization: Bearer ${API_KEY}"
```

Create a queued job with a preset system voice:

```bash
curl -X POST http://127.0.0.1:8000/v1/jobs \
  -H "Authorization: Bearer ${API_KEY}" \
  -H 'Content-Type: application/json' \
  -d '{"text":"hello narrator","voice_profile_id":"SYSTEM_VOICE_ID"}'
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
- Set `TTS_SERVICE_SYSTEM_VOICES_MANIFEST_PATH` to a JSON file on the server if you want users to see preset system voices in `GET /v1/voices`.
- `nanovllm_voxcpm` is wired as an alternate provider slot, but its runtime integration should be completed and validated on the target server before production use.
