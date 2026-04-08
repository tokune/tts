# Repository Guidelines

This document provides essential information for contributors to the VoxCPM HTTP Service repository.

## Project Structure & Module Organization

The project follows a modular Python structure:

- `src/tts_service/`: Main application source code.
    - `api/`: FastAPI route definitions (auth, jobs, voices).
    - `auth/`: Authentication and security logic.
    - `db/`: Database models, session management, and base classes.
    - `providers/`: TTS engine implementations (e.g., `fake`, `voxcpm`).
    - `services/`: Core business logic (job processing, voice management).
    - `storage/`: File system and media storage handling.
    - `worker/`: Background job processing logic.
- `tests/`: Suite of pytest-based integration and unit tests.
- `docs/`: Project documentation and design specifications.

## Build, Test, and Development Commands

### Environment Setup
```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

### Running the Application
**Development Mode (with Fake Provider):**
```bash
TTS_SERVICE_PROVIDER=fake .venv/bin/uvicorn tts_service.main:create_app --factory --reload
```

**Production Mode (Official VoxCPM):**
Create and activate the server runtime first:

```bash
conda create -n voxcpm_env python=3.11
conda activate voxcpm_env
cd /srv/tts
pip install -e .
pip install voxcpm
```

Then set environment variables like `TTS_SERVICE_PROVIDER=voxcpm` and `TTS_SERVICE_VOXCPM_MODEL_PATH` before running via `uvicorn`.

### Testing
Run the full test suite using `pytest`:
```bash
.venv/bin/pytest
```

## Coding Style & Naming Conventions

- **Style**: Follow PEP 8 standards.
- **Formatting**: Use standard Python formatting.
- **Naming**:
    - Modules and packages: `snake_case`.
    - Classes: `PascalCase`.
    - Functions and variables: `cal_case`.
    - Constants: `UPPER_SNAKE_CASE`.

## Testing Guidelines

- **Framework**: `pytest` is the primary testing framework.
- **Test Location**: All tests must reside in the `tests/` directory.
- **Naming**: Test files should start with `test_` (e.g., `test_jobs_api.py`).
- **Coverage**: Ensure new features include corresponding integration tests in the `tests/` folder.

## Commit & Pull Request Guidelines

- **Commits**: Use clear, descriptive commit messages that summarize the change.
- **Pull Requests**:
    - Provide a clear description of the changes.
    - Link to any relevant issues or design docs in `docs/superpowers/`.
    - Ensure all tests pass before requesting a review.
