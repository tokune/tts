# TTS Worker Logging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add readable text logs so `tts-worker` shows startup state, queue polling, job progress, failures, and official VoxCPM model loading progress.

**Architecture:** Use Python's standard `logging` module with a single text formatter configured by the CLI. Emit logs from the CLI for lifecycle events, from `WorkerService` for per-job progress, and from the official provider for model loading so the operator can see useful progress without changing the API surface.

**Tech Stack:** Python `logging`, pytest, FastAPI test helpers

---

### Task 1: Add failing logging tests

**Files:**
- Modify: `tests/test_worker_cli.py`
- Modify: `tests/test_official_voxcpm_provider.py`

- [ ] **Step 1: Write the failing tests**
- [ ] **Step 2: Run the focused tests to verify they fail**
- [ ] **Step 3: Implement the minimal logging code**
- [ ] **Step 4: Run the focused tests to verify they pass**

### Task 2: Implement worker and provider logging

**Files:**
- Modify: `src/tts_service/worker/cli.py`
- Modify: `src/tts_service/services/worker.py`
- Modify: `src/tts_service/providers/official_voxcpm.py`

- [ ] **Step 1: Configure CLI text logging and startup/idle logs**
- [ ] **Step 2: Add per-job success and failure logs in `WorkerService`**
- [ ] **Step 3: Add official provider model-loading logs**
- [ ] **Step 4: Re-run focused tests**

### Task 3: Document the new operator feedback

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add worker log expectations and examples**
- [ ] **Step 2: Run regression tests**
