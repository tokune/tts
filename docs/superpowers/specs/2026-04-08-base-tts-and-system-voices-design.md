# Base TTS And System Voices Design

## Summary

Add a first-class "direct text-to-speech" path that does not require cloning audio, and make preset system voices selectable through the existing `voice_profile_id` field.

This change also fixes an existing gap in the job execution path: saved voice profiles and system voices are persisted in the database, but the worker does not currently resolve their stored reference audio before calling the provider.

## Goals

- Allow `POST /v1/jobs` to accept plain text with no `voice_profile_id` and no uploaded reference audio.
- Keep `voice_profile_id` as the single selector for reusable user voices and preset system voices.
- Make system voices configurable on the server so `GET /v1/voices` can return a real preset voice list.
- Ensure worker execution passes the correct reference audio and optional reference text to the provider for saved and system voices.

## Non-Goals

- Add a new public admin API for managing system voices.
- Bundle sample preset voice audio files in this repository.
- Redesign the jobs or voices response schemas.

## Current State

The service already supports three conceptual request modes in the higher-level design:

1. Base TTS
2. Reusable cloned voice via `voice_profile_id`
3. One-off clone via uploaded reference audio

The implementation only partially exposes those modes:

- JSON job creation requires `text`, but only uses `voice_profile_id` when present.
- Multipart job creation requires `reference_audio` unless `voice_profile_id` is provided.
- The worker only forwards one-off uploaded reference audio from `job_inputs`.
- When a job references a saved voice profile, the worker does not load that voice profile's stored reference audio path or reference text before calling the provider.

That last point means reusable voices and system voices are not fully wired for real providers even though the database model and voice listing logic already exist.

## Proposed Behavior

### Job submission modes

`POST /v1/jobs` will support the following combinations:

1. Base TTS
   - JSON: `{"text":"..."}`
   - Multipart: `text=...`
   - Result: create a queued job with `request_mode="base_tts"` and no `voice_profile_id`

2. Reusable voice or preset system voice
   - JSON: `{"text":"...","voice_profile_id":"..."}`
   - Multipart: `text=...` plus `voice_profile_id=...`
   - Result: create a queued job tied to that stored voice profile

3. One-off clone
   - Multipart only
   - `text=...` plus `reference_audio=@...`
   - Optional `clone_mode=clone`
   - Optional `reference_text=...`
   - If `clone_mode=ultimate_clone`, `reference_text` remains required

Priority rules for multipart requests:

- If `voice_profile_id` is provided, use the stored voice and ignore clone upload fields.
- Else if `reference_audio` is provided, create a one-off clone job.
- Else create a base TTS job.

### System voice configuration

Add an optional server-side manifest setting for preset system voices.

Manifest responsibilities:

- Define the system voices that should be visible to all users.
- Point each voice to a server-local reference audio file.
- Optionally include `reference_text`, `description`, and `source_label`.

Startup behavior:

- On app startup, if a manifest path is configured, load it.
- For each manifest entry, create a missing system voice record.
- Use `source_label` when present, otherwise `name`, as the stable identity used to avoid duplicate inserts.
- Existing matching system voices are left unchanged during startup.

This keeps the first implementation simple and safe:

- Operators can pre-provision preset voices on the GPU server.
- Users can discover them through `GET /v1/voices`.
- The app does not need a new admin API or migration-heavy synchronization logic.

## Architecture Changes

### API layer

Update job request parsing so both JSON and multipart requests can create base TTS jobs with only `text`.

No new endpoint is required. The existing `voice_profile_id` parameter remains the selector for reusable and preset voices.

### Voice service

Add a manifest-loading helper to `VoiceService` that:

- reads the configured manifest file
- validates required entry fields
- resolves server-local audio file paths
- inserts missing `scope="system"` voice records

The existing `create_system_voice` helper remains the low-level persistence method.

### Worker path

Update worker execution so it resolves synthesis inputs in this order:

1. One-off clone input from `job_inputs`
2. Stored voice profile reference audio and reference text from `voice_profiles`
3. No reference audio at all for base TTS

This is the key fix that makes saved user voices and preset system voices actually usable with real providers.

## Error Handling

- `text` remains required for all job requests.
- `voice_profile_id` still returns `404` if the voice does not exist and `403` if it is not accessible.
- `ultimate_clone` still returns `422` when `reference_text` is missing.
- Invalid system voice manifest entries should fail application startup with a clear exception, because partial preset voice loading would be hard to reason about operationally.

## Testing Strategy

Add focused tests for:

- JSON base TTS job creation with only `text`
- Multipart base TTS job creation with only `text`
- Worker completion for a base TTS job
- Worker synthesis for a saved voice profile, asserting that stored reference audio and optional reference text are passed to the provider
- Worker synthesis for a system voice, asserting the same data flow
- Startup manifest loading and voice listing behavior for preset system voices

Use a small recording provider in tests where necessary so assertions cover the exact synthesis request delivered to the provider instead of only the final HTTP status code.

## Rollout Notes

- Local development remains unchanged when using the fake provider.
- Production operators can enable preset voices by supplying the manifest file and referenced audio assets on the server.
- Clients that already send `voice_profile_id` continue to work, with the additional benefit that stored/system voice references now reach the provider correctly.
