# VoxCPM HTTP Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a FastAPI-based, multi-user, asynchronous TTS service with reusable voice profiles, SQLite persistence, local file storage, and a production-ready VoxCPM provider boundary that does not require local model loading during development.

**Architecture:** Split the system into an HTTP control plane and a polling worker. The API writes validated requests and metadata to SQLite, while the worker claims queued jobs and delegates synthesis to a provider abstraction. Local development uses a fake provider; production uses a Nano-vLLM VoxCPM provider configured on the server.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy, Pydantic, pytest, SQLite, local filesystem storage

---

### Task 1: Bootstrap the Python service and configuration

**Files:**
- Create: `pyproject.toml`
- Create: `src/tts_service/__init__.py`
- Create: `src/tts_service/config.py`
- Create: `src/tts_service/logging.py`
- Create: `src/tts_service/main.py`
- Create: `tests/test_health.py`

- [ ] **Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient

from tts_service.main import create_app


def test_healthcheck_returns_ok() -> None:
    client = TestClient(create_app())

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_health.py -v`
Expected: FAIL because `tts_service.main` and `create_app` do not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="VoxCPM HTTP Service")

    @app.get("/healthz")
    def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    return app
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_health.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/tts_service tests/test_health.py
git commit -m "feat: bootstrap service skeleton"
```

### Task 2: Add database models and API key authentication

**Files:**
- Create: `src/tts_service/db/base.py`
- Create: `src/tts_service/db/session.py`
- Create: `src/tts_service/db/models.py`
- Create: `src/tts_service/auth/security.py`
- Create: `src/tts_service/auth/deps.py`
- Create: `src/tts_service/api/auth.py`
- Modify: `src/tts_service/main.py`
- Create: `tests/test_auth_api.py`

- [ ] **Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient

from tts_service.main import create_app


def test_verify_api_key_returns_user_identity(tmp_path) -> None:
    app = create_app({"database_url": f"sqlite:///{tmp_path}/app.db"})
    client = TestClient(app)

    bootstrap = client.post("/debug/bootstrap-user", json={"name": "alice"})
    api_key = bootstrap.json()["api_key"]

    response = client.post(
        "/v1/auth/keys/verify",
        headers={"Authorization": f"Bearer {api_key}"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "alice"
    assert response.json()["valid"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_auth_api.py -v`
Expected: FAIL because auth routes, models, and bootstrap helper do not exist.

- [ ] **Step 3: Write minimal implementation**

```python
class User(Base):
    __tablename__ = "users"
    id = mapped_column(String, primary_key=True)
    name = mapped_column(String, nullable=False)
    api_key_hash = mapped_column(String, nullable=False, unique=True)
    is_active = mapped_column(Boolean, default=True, nullable=False)


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


@router.post("/v1/auth/keys/verify")
def verify_api_key(current_user: AuthenticatedUser = Depends(require_api_key)) -> dict:
    return {"valid": True, "user_id": current_user.user_id, "name": current_user.name}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_auth_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/tts_service/db src/tts_service/auth src/tts_service/api/auth.py tests/test_auth_api.py
git commit -m "feat: add sqlite users and api key auth"
```

### Task 3: Implement storage services and reusable voice profile APIs

**Files:**
- Create: `src/tts_service/storage/files.py`
- Create: `src/tts_service/services/voices.py`
- Create: `src/tts_service/api/voices.py`
- Modify: `src/tts_service/db/models.py`
- Modify: `src/tts_service/main.py`
- Create: `tests/test_voice_profiles_api.py`

- [ ] **Step 1: Write the failing test**

```python
from io import BytesIO

from fastapi.testclient import TestClient

from tts_service.main import create_app


def test_create_and_list_user_voice_profile(tmp_path) -> None:
    app = create_app({"database_url": f"sqlite:///{tmp_path}/app.db", "storage_root": str(tmp_path / "storage")})
    client = TestClient(app)

    bootstrap = client.post("/debug/bootstrap-user", json={"name": "alice"})
    api_key = bootstrap.json()["api_key"]

    response = client.post(
        "/v1/voices",
        headers={"Authorization": f"Bearer {api_key}"},
        files={"reference_audio": ("reference.wav", BytesIO(b"RIFFdemo"), "audio/wav")},
        data={"name": "alice-voice", "clone_mode": "clone", "consent_statement": "owned by user"},
    )

    assert response.status_code == 201

    listing = client.get("/v1/voices", headers={"Authorization": f"Bearer {api_key}"})
    assert listing.status_code == 200
    assert listing.json()["items"][0]["name"] == "alice-voice"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_voice_profiles_api.py -v`
Expected: FAIL because voice models, file storage, and routes do not exist.

- [ ] **Step 3: Write minimal implementation**

```python
class VoiceProfile(Base):
    __tablename__ = "voice_profiles"
    id = mapped_column(String, primary_key=True)
    user_id = mapped_column(String, ForeignKey("users.id"), nullable=True)
    scope = mapped_column(String, nullable=False)
    name = mapped_column(String, nullable=False)
    clone_mode = mapped_column(String, nullable=False)
    reference_audio_path = mapped_column(String, nullable=False)
    reference_text = mapped_column(Text, nullable=True)
    consent_statement = mapped_column(Text, nullable=False)
    source_label = mapped_column(String, nullable=True)
    status = mapped_column(String, nullable=False, default="ready")
```

```python
@router.post("/v1/voices", status_code=201)
def create_voice_profile(...) -> VoiceProfileResponse:
    stored_path = file_storage.save_voice_reference(...)
    voice = voice_service.create_voice_profile(...)
    return VoiceProfileResponse.model_validate(voice)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_voice_profiles_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/tts_service/storage src/tts_service/services/voices.py src/tts_service/api/voices.py tests/test_voice_profiles_api.py
git commit -m "feat: add reusable voice profile storage and api"
```

### Task 4: Add queued job APIs and ownership checks

**Files:**
- Create: `src/tts_service/services/jobs.py`
- Create: `src/tts_service/api/jobs.py`
- Modify: `src/tts_service/db/models.py`
- Modify: `src/tts_service/storage/files.py`
- Modify: `src/tts_service/main.py`
- Create: `tests/test_jobs_api.py`

- [ ] **Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient

from tts_service.main import create_app


def test_submit_job_with_saved_voice_enters_queue(tmp_path) -> None:
    app = create_app({"database_url": f"sqlite:///{tmp_path}/app.db", "storage_root": str(tmp_path / "storage")})
    client = TestClient(app)

    bootstrap = client.post("/debug/bootstrap-user", json={"name": "alice"})
    api_key = bootstrap.json()["api_key"]
    voice = client.post(
        "/v1/voices",
        headers={"Authorization": f"Bearer {api_key}"},
        files={"reference_audio": ("reference.wav", b"RIFFdemo", "audio/wav")},
        data={"name": "alice-voice", "clone_mode": "clone", "consent_statement": "owned by user"},
    ).json()

    response = client.post(
        "/v1/jobs",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"text": "hello world", "voice_profile_id": voice["id"]},
    )

    assert response.status_code == 202
    assert response.json()["status"] == "queued"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_jobs_api.py -v`
Expected: FAIL because queued jobs are not implemented.

- [ ] **Step 3: Write minimal implementation**

```python
class TTSJob(Base):
    __tablename__ = "tts_jobs"
    id = mapped_column(String, primary_key=True)
    user_id = mapped_column(String, ForeignKey("users.id"), nullable=False)
    voice_profile_id = mapped_column(String, ForeignKey("voice_profiles.id"), nullable=True)
    status = mapped_column(String, nullable=False, default="queued")
    request_mode = mapped_column(String, nullable=False)
    input_text = mapped_column(Text, nullable=False)
    output_audio_path = mapped_column(String, nullable=True)
    error_code = mapped_column(String, nullable=True)
    error_message = mapped_column(Text, nullable=True)
```

```python
@router.post("/v1/jobs", status_code=202)
def create_job(payload: CreateJobRequest, current_user: AuthenticatedUser = Depends(require_api_key)) -> JobResponse:
    job = job_service.create_job(current_user.user_id, payload)
    return JobResponse.model_validate(job)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_jobs_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/tts_service/services/jobs.py src/tts_service/api/jobs.py src/tts_service/db/models.py tests/test_jobs_api.py
git commit -m "feat: add async job queue api"
```

### Task 5: Implement worker polling and fake synthesis provider

**Files:**
- Create: `src/tts_service/providers/base.py`
- Create: `src/tts_service/providers/fake.py`
- Create: `src/tts_service/services/worker.py`
- Create: `src/tts_service/worker/cli.py`
- Modify: `src/tts_service/services/jobs.py`
- Modify: `src/tts_service/storage/files.py`
- Create: `tests/test_worker_flow.py`

- [ ] **Step 1: Write the failing test**

```python
from tts_service.main import create_app
from tts_service.services.worker import WorkerService


def test_worker_claims_and_completes_queued_job(tmp_path) -> None:
    app = create_app({"database_url": f"sqlite:///{tmp_path}/app.db", "storage_root": str(tmp_path / "storage")})
    bootstrap_user = app.state.debug.bootstrap_user
    user = bootstrap_user("alice")
    voice = app.state.voice_service.create_system_voice_for_test()
    job = app.state.job_service.create_job(user.id, {"text": "hello", "voice_profile_id": voice.id})

    worker = WorkerService(
        session_factory=app.state.session_factory,
        file_storage=app.state.file_storage,
        provider=app.state.provider,
    )
    processed = worker.process_next_job()

    assert processed is True
    refreshed = app.state.job_service.get_job_for_user(user.id, job.id)
    assert refreshed.status == "succeeded"
    assert refreshed.output_audio_path is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_worker_flow.py -v`
Expected: FAIL because provider and worker do not exist.

- [ ] **Step 3: Write minimal implementation**

```python
class FakeTTSProvider(TTSProvider):
    def synthesize(self, job_spec: SynthesisRequest) -> SynthesisResult:
        return SynthesisResult(audio_bytes=b"RIFFfake-wave", sample_rate=24000, format="wav")
```

```python
def process_next_job(self) -> bool:
    job = self.job_service.claim_next_job()
    if job is None:
        return False
    result = self.provider.synthesize(...)
    output_path = self.file_storage.save_job_output(job.id, result.audio_bytes, "wav")
    self.job_service.mark_job_succeeded(job.id, output_path)
    return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_worker_flow.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/tts_service/providers src/tts_service/services/worker.py src/tts_service/worker/cli.py tests/test_worker_flow.py
git commit -m "feat: add worker polling and fake synthesis provider"
```

### Task 6: Add production Nano-vLLM VoxCPM provider and server configuration

**Files:**
- Create: `src/tts_service/providers/nanovllm_voxcpm.py`
- Modify: `src/tts_service/config.py`
- Modify: `src/tts_service/main.py`
- Create: `tests/test_provider_selection.py`
- Create: `.env.example`
- Create: `README.md`

- [ ] **Step 1: Write the failing test**

```python
from tts_service.main import create_app


def test_app_uses_fake_provider_by_default(tmp_path) -> None:
    app = create_app({"database_url": f"sqlite:///{tmp_path}/app.db", "storage_root": str(tmp_path / "storage")})

    assert app.state.provider.__class__.__name__ == "FakeTTSProvider"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_provider_selection.py -v`
Expected: FAIL because provider selection is not configurable.

- [ ] **Step 3: Write minimal implementation**

```python
def build_provider(settings: Settings) -> TTSProvider:
    if settings.provider == "fake":
        return FakeTTSProvider()
    if settings.provider == "nanovllm_voxcpm":
        return NanoVllmVoxCpmProvider(
            model_path=settings.voxcpm_model_path,
            device_ids=settings.voxcpm_device_ids,
        )
    raise ValueError(f"unsupported provider: {settings.provider}")
```

```python
class NanoVllmVoxCpmProvider(TTSProvider):
    def synthesize(self, job_spec: SynthesisRequest) -> SynthesisResult:
        raise NotImplementedError("Production inference is only available on the server runtime")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_provider_selection.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/tts_service/providers/nanovllm_voxcpm.py src/tts_service/config.py README.md .env.example tests/test_provider_selection.py
git commit -m "feat: add production voxcpm provider wiring"
```

### Task 7: Add cancellation, events, and result download integration tests

**Files:**
- Modify: `src/tts_service/db/models.py`
- Modify: `src/tts_service/services/jobs.py`
- Modify: `src/tts_service/api/jobs.py`
- Create: `tests/test_job_lifecycle_api.py`

- [ ] **Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient

from tts_service.main import create_app


def test_cancel_queued_job_and_download_completed_audio(tmp_path) -> None:
    app = create_app({"database_url": f"sqlite:///{tmp_path}/app.db", "storage_root": str(tmp_path / "storage")})
    client = TestClient(app)

    bootstrap = client.post("/debug/bootstrap-user", json={"name": "alice"})
    api_key = bootstrap.json()["api_key"]
    voice = client.post(
        "/v1/voices",
        headers={"Authorization": f"Bearer {api_key}"},
        files={"reference_audio": ("reference.wav", b"RIFFdemo", "audio/wav")},
        data={"name": "alice-voice", "clone_mode": "clone", "consent_statement": "owned by user"},
    ).json()

    job = client.post(
        "/v1/jobs",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"text": "hello world", "voice_profile_id": voice["id"]},
    ).json()

    cancel = client.post(f"/v1/jobs/{job['id']}/cancel", headers={"Authorization": f"Bearer {api_key}"})
    assert cancel.status_code == 200
    assert cancel.json()["status"] == "cancelled"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_job_lifecycle_api.py -v`
Expected: FAIL because cancellation and lifecycle details are not complete.

- [ ] **Step 3: Write minimal implementation**

```python
class JobEvent(Base):
    __tablename__ = "job_events"
    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id = mapped_column(String, ForeignKey("tts_jobs.id"), nullable=False)
    status = mapped_column(String, nullable=False)
    message = mapped_column(Text, nullable=False)
```

```python
@router.post("/v1/jobs/{job_id}/cancel")
def cancel_job(job_id: str, current_user: AuthenticatedUser = Depends(require_api_key)) -> JobResponse:
    job = job_service.cancel_job(current_user.user_id, job_id)
    return JobResponse.model_validate(job)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_job_lifecycle_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/tts_service/api/jobs.py src/tts_service/services/jobs.py src/tts_service/db/models.py tests/test_job_lifecycle_api.py
git commit -m "feat: finalize job lifecycle and download api"
```
