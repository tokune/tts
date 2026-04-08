# VoxCPM HTTP Service Design

## Goal

Build a multi-user HTTP service for asynchronous TTS generation with voice cloning, backed by SQLite for metadata and local disk for file storage. The API process must not load models in local development. Production inference runs on the server with VoxCPM.

## Scope

This design covers:

- HTTP API for users, voices, jobs, and output download
- API key based multi-user isolation
- Async job processing
- Reusable user voice profiles
- Platform-provided system voices
- SQLite schema and local file storage layout
- A pluggable inference provider boundary for VoxCPM

This design does not cover:

- Browser UI
- Billing and quotas
- Object storage
- Multi-machine orchestration
- Fine-tuning custom voices

## External Constraints

- Runtime target is a single Linux server with a single NVIDIA GPU.
- Local development must not require downloading or loading VoxCPM models.
- The implementation should align with VoxCPM's supported voice cloning modes.
- SQLite is the only database.
- Generated audio and reference audio are stored on local disk, while SQLite stores metadata and paths.

## External Dependencies and Rationale

- `OpenBMB/VoxCPM` provides baseline TTS, streaming generation, and prompt-audio based voice cloning.
- `nano-vllm-voxcpm` is the preferred inference backend for production because it explicitly supports concurrent requests and an async API suitable for wrapping with an HTTP service.

References:

- https://github.com/OpenBMB/VoxCPM
- https://pypi.org/project/nano-vllm-voxcpm/

## Architecture

The system is split into two logical processes on the same server:

1. `api-server`
   - Handles HTTP requests
   - Authenticates users via API key
   - Validates uploads and input payloads
   - Stores metadata in SQLite
   - Writes uploaded files to local disk
   - Creates and queries async jobs
   - Serves generated audio files

2. `inference-worker`
   - Loads and owns the VoxCPM inference provider on the server
   - Polls SQLite for queued jobs
   - Runs synthesis on the GPU
   - Writes outputs to disk
   - Updates job status and events

The API process never performs inference directly. HTTP requests return quickly with a `job_id`, and job completion is observed via polling or server-sent events later if added.

## Core Flows

### 1. Create a reusable user voice profile

1. Client sends `POST /v1/voices` with API key, audio file, name, clone mode, and optional transcript.
2. API validates ownership, file format, duration, and transcript requirements.
3. API writes the reference audio to disk and inserts a `voice_profiles` row.
4. API returns the stored voice profile metadata.

### 2. Submit a TTS job using a saved voice

1. Client sends `POST /v1/jobs` with text and `voice_profile_id`.
2. API verifies the voice belongs to the same user or is a system voice.
3. API inserts a queued job and any expanded input metadata.
4. Worker picks the job, performs inference, writes output audio, and marks the job complete or failed.

### 3. Submit a one-off clone job

1. Client sends `POST /v1/jobs` with text plus a temporary reference audio file and optional transcript.
2. API stores the temporary reference input under the job directory, without creating a reusable voice.
3. Worker consumes the job exactly once using that temporary input.

### 4. Download output

1. Client requests `GET /v1/jobs/{job_id}/audio`.
2. API checks ownership and job completion.
3. API streams the output file from disk.

## Voice Cloning Modes

The system supports three request patterns:

1. Base TTS
   - `text` plus a system voice or default voice style

2. Clone with reusable voice profile
   - `text` plus `voice_profile_id`
   - Voice profile contains reference audio and optional transcript

3. One-off clone
   - `text` plus uploaded reference audio and optional transcript
   - Used only for the current job

`clone_mode` values:

- `clone`
- `ultimate_clone`

Rule:

- `ultimate_clone` requires `reference_text`

Voice profiles represent reusable reference assets. They do not represent fine-tuned custom models.

## SQLite Schema

### `users`

- `id`
- `name`
- `api_key_hash`
- `is_active`
- `created_at`
- `last_used_at`

### `voice_profiles`

- `id`
- `user_id` nullable for system voices
- `scope` enum: `system`, `user`
- `name`
- `description`
- `clone_mode`
- `reference_audio_path`
- `reference_text`
- `sample_rate`
- `duration_ms`
- `status` enum: `ready`, `disabled`
- `created_at`

### `tts_jobs`

- `id`
- `user_id`
- `voice_profile_id` nullable
- `status` enum: `queued`, `running`, `succeeded`, `failed`, `cancelled`
- `request_mode` enum: `base_tts`, `clone`, `ultimate_clone`
- `input_text`
- `output_audio_path`
- `output_format`
- `error_code`
- `error_message`
- `queue_position_snapshot`
- `created_at`
- `started_at`
- `finished_at`

### `job_inputs`

- `job_id`
- `temp_reference_audio_path`
- `temp_reference_text`
- `generation_config_json`

### `job_events`

- `id`
- `job_id`
- `status`
- `message`
- `created_at`

## API Surface

### Authentication

- `POST /v1/auth/keys/verify`

Uses `Authorization: Bearer <api_key>` and returns whether the key is valid.

### Voices

- `GET /v1/voices`
- `POST /v1/voices`
- `GET /v1/voices/{voice_id}`
- `DELETE /v1/voices/{voice_id}`

Behavior:

- List returns system voices plus the current user's voices.
- Create accepts a reference audio upload and creates a reusable voice profile.
- Delete only applies to the current user's voices.

### Jobs

- `POST /v1/jobs`
- `GET /v1/jobs`
- `GET /v1/jobs/{job_id}`
- `POST /v1/jobs/{job_id}/cancel`
- `GET /v1/jobs/{job_id}/audio`

`POST /v1/jobs` accepts:

- `text` plus `system_voice_id`
- `text` plus `voice_profile_id`
- `text` plus uploaded `reference_audio` and optional `reference_text`

### Response Model Requirements

All responses must omit sensitive data such as API keys and full internal file paths when not needed. Job responses should expose stable public metadata:

- `id`
- `status`
- `request_mode`
- `created_at`
- `started_at`
- `finished_at`
- `error_code`
- `error_message`
- `audio_url` when complete

## Authorization Rules

- API key always resolves to `user_id` on the server.
- Clients never provide `user_id` directly.
- A voice profile can be used only if:
  - it belongs to the current user, or
  - it is a system voice
- A job can be viewed, cancelled, or downloaded only by its owner.
- System voices are readable by all users and writable by no API user.

## Validation Rules

- Reject empty text.
- Enforce upload size limits.
- Enforce audio duration limits.
- Allow only expected audio formats at the API boundary.
- Require transcript for `ultimate_clone`.
- Reject disabled voices.
- Reject cancellation of jobs already terminal.

## Job State Machine

- `queued`: accepted and awaiting worker pickup
- `running`: currently being synthesized
- `succeeded`: output audio successfully written
- `failed`: terminal failure with error metadata
- `cancelled`: terminal cancellation

State transitions:

- `queued -> running`
- `queued -> cancelled`
- `running -> succeeded`
- `running -> failed`
- `running -> cancelled` only as a logical cancellation marker if future implementation supports interruption

In the initial implementation, cancelling a running GPU inference is not guaranteed. To preserve runtime stability, cancellation is only guaranteed before inference starts.

## Worker Design

Initial deployment uses a single worker process attached to one GPU.

Worker behavior:

- Poll queued jobs ordered by `created_at`
- Atomically claim one job inside a SQLite transaction
- Emit `job_events` during lifecycle changes
- Run inference through a provider abstraction
- Write output audio to the job output directory
- Finalize status and timestamps

Initial concurrency defaults to `1` generation at a time for safety and predictability. A configuration knob may raise concurrency later after GPU validation.

## Provider Abstraction

Define a narrow interface to isolate inference runtime details from the API and worker:

- `healthcheck()`
- `synthesize(job_spec) -> synthesis_result`
- `prepare_voice_prompt(voice_profile) -> provider_voice_spec`

Initial implementation:

- `NanoVllmVoxCpmProvider`

Local development and CI use a fake provider that returns deterministic placeholder audio without loading a real model.

## Storage Layout

```text
storage/
  app.db
  uploads/
    voices/
      system/
      users/{user_id}/{voice_id}/reference.wav
    jobs/
      {job_id}/input_reference.wav
  outputs/
    jobs/{job_id}/audio.wav
```

Rules:

- SQLite stores metadata and paths, not file blobs.
- Voice profile reference files are independent from job output files.
- Deleting a voice profile does not invalidate historical job outputs.

## Error Handling

Examples of `error_code` values:

- `invalid_input`
- `unauthorized`
- `voice_not_found`
- `voice_not_usable`
- `job_not_found`
- `provider_unavailable`
- `synthesis_failed`
- `storage_error`

Worker failures must always write both:

- terminal job status
- a human-readable `job_events` entry

## Recovery Strategy

On startup, the worker scans stale `running` jobs.

Initial rule:

- if a job is `running` and no worker heartbeat or lease is valid, mark it `failed` with a restart-related error code

This is intentionally conservative. Explicit retries are simpler and safer than ambiguous partial output recovery in the first version.

## Security and Governance

- Store only API key hashes.
- Never log raw API keys.
- Avoid logging full text payloads unless debug mode is explicitly enabled.
- Record `consent_statement` and `source_label` for uploaded voice references.
- Mark outputs as AI-generated in metadata responses.

This service exposes voice cloning and therefore must include governance hooks even if the first version keeps enforcement light.

## Testing Strategy

### Unit Tests

- API key hashing and verification
- User and voice authorization checks
- SQLite repositories
- Job state transitions
- File path generation and storage layout
- Request validation rules

### Integration Tests

- Create user and verify key
- Create reusable voice profile
- Submit jobs with saved voice and one-off voice
- Worker picks queued jobs and completes them
- Download completed audio with ownership checks

### Provider Tests

- Fake provider for deterministic local and CI verification
- Real GPU provider kept out of default CI

## Deployment Model

The intended production deployment is a single Linux server with:

- one FastAPI API process
- one worker process
- one local SQLite database file
- one local storage directory
- one local model directory mounted or downloaded on the server

Required runtime configuration includes:

- `APP_ENV`
- `DATABASE_URL` or SQLite path
- `STORAGE_ROOT`
- `VOXCPM_PROVIDER`
- `VOXCPM_MODEL_PATH`
- `VOXCPM_DEVICE_IDS`
- API upload and generation limits

## File and Module Boundaries

Recommended module layout:

- `src/tts_service/api/`
- `src/tts_service/auth/`
- `src/tts_service/config.py`
- `src/tts_service/db/`
- `src/tts_service/models/`
- `src/tts_service/providers/`
- `src/tts_service/services/`
- `src/tts_service/storage/`
- `src/tts_service/worker/`
- `tests/`

The provider boundary should remain the only place that knows concrete VoxCPM runtime details.

## Open Decisions Resolved

- Authentication: API key only
- Voice assets: user-owned reusable profiles plus platform system voices
- Persistence: SQLite metadata plus local filesystem blobs
- Deployment: single server, single GPU
- API behavior: async jobs, polling-first
- Local development: fake provider, no local model loading

## Implementation Direction

Implement the service as a new Python project using FastAPI, SQLAlchemy, and a provider abstraction with a fake local provider and a Nano-vLLM VoxCPM production provider.
