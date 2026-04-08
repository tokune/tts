# Root Dotenv Loading Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically load the repository root `.env` file for service settings without changing the existing override precedence.

**Architecture:** Keep all dotenv behavior inside `build_settings()` in `src/tts_service/config.py`. Use a repository-root-relative path instead of `env_file=".env"` so loading does not depend on the current working directory. Validate behavior with focused configuration tests and a short README update.

**Tech Stack:** Python, pydantic-settings, pytest

---

### Task 1: Add failing configuration tests

**Files:**
- Create: `tests/test_config.py`

- [ ] **Step 1: Write the failing test for root `.env` loading**
- [ ] **Step 2: Run `pytest tests/test_config.py::test_build_settings_loads_values_from_root_dotenv -v` and confirm it fails before implementation**
- [ ] **Step 3: Add the failing precedence tests for process environment and explicit overrides**
- [ ] **Step 4: Run `pytest tests/test_config.py -v` and confirm the new expectations still fail before implementation**

### Task 2: Implement root `.env` loading

**Files:**
- Modify: `src/tts_service/config.py`

- [ ] **Step 1: Add a repository-root `.env` path constant or helper**
- [ ] **Step 2: Pass `_env_file=<root .env path>` from `build_settings()` while preserving explicit overrides**
- [ ] **Step 3: Run `pytest tests/test_config.py -v` and confirm all config tests pass**

### Task 3: Document the supported configuration flow

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Document that `.env.example` can be copied to `.env` in the repository root for automatic loading**
- [ ] **Step 2: Run `pytest tests/test_config.py tests/test_provider_selection.py -v` to confirm the config change does not break provider selection**
