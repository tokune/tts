# Root Dotenv Loading Design

## Summary

Teach the service configuration layer to automatically read the repository root `.env` file while preserving the existing precedence order: explicit overrides first, process environment second, `.env` third, defaults last.

## Goals

- Automatically load `TTS_SERVICE_*` settings from the repository root `.env`.
- Keep `build_settings()` as the single configuration entrypoint for the app and worker.
- Preserve stable precedence:
  1. explicit `overrides`
  2. process environment variables
  3. repository root `.env`
  4. field defaults
- Document the new behavior without changing the public API.

## Non-Goals

- Support arbitrary `.env` file locations.
- Add a new dependency such as `python-dotenv`.
- Change the `TTS_SERVICE_` prefix or setting names.

## Current State

`Settings` uses `pydantic-settings`, but the model config only declares an environment variable prefix. The application creates settings through `build_settings()`, which currently calls `Settings(**data)` with no `_env_file` and no explicit dotenv loading. As a result, `.env.example` exists only as a template and a copied `.env` is ignored unless the shell loads it first.

## Proposed Behavior

- Compute the repository root from `src/tts_service/config.py`.
- Resolve the root `.env` path once in the configuration module.
- Pass that path to `Settings(..., _env_file=...)` inside `build_settings()`.
- Continue to accept `overrides` exactly as today.

This keeps the behavior centralized and avoids relying on the current working directory, which would make `env_file=".env"` fragile when the service is launched from another directory.

## Architecture Changes

### Configuration layer

Add a module-level helper or constant in `src/tts_service/config.py` that points to the repository root `.env`. `build_settings()` will pass that path through `_env_file`, leaving the rest of the app unchanged.

### Documentation

Update `README.md` to mention that operators and developers can either export variables in the shell or place them in a root `.env` file copied from `.env.example`.

## Error Handling

- Missing `.env` should remain a non-error and fall back to process environment/defaults.
- Invalid values in `.env` should continue to surface as settings validation errors.

## Testing Strategy

Add focused tests around `build_settings()`:

- load a value from a repository root `.env`
- confirm a real environment variable overrides `.env`
- confirm explicit overrides override both

Use temporary replacement of the module-level dotenv path so tests do not depend on the developer's real workspace `.env`.
