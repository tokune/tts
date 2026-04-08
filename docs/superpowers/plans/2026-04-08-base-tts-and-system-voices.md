# Base TTS And System Voices Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add direct text-to-speech job submission without cloning audio, support selectable preset system voices through `voice_profile_id`, and fix worker synthesis so saved/system voice references actually reach the provider.

**Architecture:** Keep the existing jobs and voices APIs, but broaden job request parsing to allow base TTS with only `text`. Resolve synthesis inputs in the worker by preferring one-off clone data, then stored voice profile references, then provider defaults. Load optional preset system voices from a server-side JSON manifest during app startup.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy, Pydantic, pytest, SQLite, local filesystem storage

---

### Task 1: Allow base TTS job submission with text only

**Files:**
- Modify: `src/tts_service/api/jobs.py`
- Test: `tests/test_jobs_api.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_submit_json_job_without_voice_profile_uses_base_tts(tmp_path) -> None:
    app = create_app(
        {
            "database_url": f"sqlite:///{tmp_path}/app.db",
            "storage_root": str(tmp_path / "storage"),
        }
    )
    client = TestClient(app)

    bootstrap = client.post("/debug/bootstrap-user", json={"name": "alice"})
    api_key = bootstrap.json()["api_key"]

    response = client.post(
        "/v1/jobs",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"text": "hello world"},
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    assert body["request_mode"] == "base_tts"
    assert body["voice_profile_id"] is None


def test_submit_multipart_job_without_voice_or_reference_audio_uses_base_tts(tmp_path) -> None:
    app = create_app(
        {
            "database_url": f"sqlite:///{tmp_path}/app.db",
            "storage_root": str(tmp_path / "storage"),
        }
    )
    client = TestClient(app)

    bootstrap = client.post("/debug/bootstrap-user", json={"name": "alice"})
    api_key = bootstrap.json()["api_key"]

    response = client.post(
        "/v1/jobs",
        headers={"Authorization": f"Bearer {api_key}"},
        data={"text": "hello multipart"},
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    assert body["request_mode"] == "base_tts"
    assert body["voice_profile_id"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_jobs_api.py -v`
Expected: FAIL because multipart parsing still requires `reference_audio` and base TTS coverage is missing.

- [ ] **Step 3: Write the minimal implementation**

```python
async def parse_job_request(request: Request, content_type: str, file_storage: FileStorage) -> CreateJobInput:
    if content_type.startswith("application/json"):
        payload = CreateJobRequest.model_validate(await request.json())
        return CreateJobInput(text=payload.text, voice_profile_id=payload.voice_profile_id)

    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        text = str(form.get("text", "")).strip()
        if not text:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="text is required")

        voice_profile_id = form.get("voice_profile_id")
        if voice_profile_id is not None:
            return CreateJobInput(text=text, voice_profile_id=str(voice_profile_id))

        reference_audio = form.get("reference_audio")
        if reference_audio is None:
            return CreateJobInput(text=text)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_jobs_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/tts_service/api/jobs.py tests/test_jobs_api.py
git commit -m "feat: allow base tts job submission"
```

### Task 2: Resolve stored voice references during worker synthesis

**Files:**
- Modify: `src/tts_service/services/jobs.py`
- Modify: `src/tts_service/services/worker.py`
- Test: `tests/test_worker_flow.py`

- [ ] **Step 1: Write the failing tests**

```python
from tts_service.providers.base import SynthesisRequest, SynthesisResult, TTSProvider


class RecordingProvider(TTSProvider):
    def __init__(self) -> None:
        self.requests: list[SynthesisRequest] = []

    def synthesize(self, request: SynthesisRequest) -> SynthesisResult:
        self.requests.append(request)
        return SynthesisResult(audio_bytes=b"RIFFrecorded", sample_rate=24000, format="wav")


def test_worker_uses_default_voice_when_job_has_only_text(tmp_path) -> None:
    app = create_app(
        {
            "database_url": f"sqlite:///{tmp_path}/app.db",
            "storage_root": str(tmp_path / "storage"),
        }
    )
    app.state.provider = RecordingProvider()
    client = TestClient(app)

    bootstrap = client.post("/debug/bootstrap-user", json={"name": "alice"})
    api_key = bootstrap.json()["api_key"]
    job = client.post(
        "/v1/jobs",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"text": "hello"},
    ).json()

    worker = WorkerService(
        session_factory=app.state.session_factory,
        file_storage=app.state.file_storage,
        provider=app.state.provider,
        job_service=app.state.job_service,
    )
    worker.process_next_job()

    request = app.state.provider.requests[0]
    assert request.job_id == job["id"]
    assert request.reference_audio_path is None
    assert request.reference_text is None


def test_worker_uses_saved_voice_reference_audio_and_text(tmp_path) -> None:
    app = create_app(
        {
            "database_url": f"sqlite:///{tmp_path}/app.db",
            "storage_root": str(tmp_path / "storage"),
        }
    )
    app.state.provider = RecordingProvider()
    client = TestClient(app)

    bootstrap = client.post("/debug/bootstrap-user", json={"name": "alice"})
    api_key = bootstrap.json()["api_key"]
    voice = client.post(
        "/v1/voices",
        headers={"Authorization": f"Bearer {api_key}"},
        files={"reference_audio": ("reference.wav", BytesIO(b"RIFFdemo"), "audio/wav")},
        data={
            "name": "alice-voice",
            "clone_mode": "ultimate_clone",
            "consent_statement": "owned by user",
            "reference_text": "hello reference",
        },
    ).json()
    client.post(
        "/v1/jobs",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"text": "hello world", "voice_profile_id": voice["id"]},
    )

    worker = WorkerService(
        session_factory=app.state.session_factory,
        file_storage=app.state.file_storage,
        provider=app.state.provider,
        job_service=app.state.job_service,
    )
    worker.process_next_job()

    request = app.state.provider.requests[0]
    assert request.reference_audio_path is not None
    assert request.reference_audio_path.endswith("reference.wav")
    assert request.reference_text == "hello reference"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_worker_flow.py -v`
Expected: FAIL because the worker only forwards one-off job input data and ignores stored voice profile references.

- [ ] **Step 3: Write the minimal implementation**

```python
@dataclass(slots=True)
class ResolvedSynthesisInput:
    reference_audio_path: str | None
    reference_text: str | None


class JobService:
    def resolve_synthesis_input(self, session: Session, job: TTSJob) -> ResolvedSynthesisInput:
        job_input = self.get_job_input(session, job.id)
        if job_input and (job_input.temp_reference_audio_path or job_input.temp_reference_text):
            return ResolvedSynthesisInput(
                reference_audio_path=job_input.temp_reference_audio_path,
                reference_text=job_input.temp_reference_text,
            )

        if job.voice_profile_id is None:
            return ResolvedSynthesisInput(reference_audio_path=None, reference_text=None)

        voice = session.scalar(select(VoiceProfile).where(VoiceProfile.id == job.voice_profile_id))
        if voice is None:
            return ResolvedSynthesisInput(reference_audio_path=None, reference_text=None)

        return ResolvedSynthesisInput(
            reference_audio_path=voice.reference_audio_path,
            reference_text=voice.reference_text,
        )
```

```python
resolved_input = self.job_service.resolve_synthesis_input(session, job)
result = self.provider.synthesize(
    SynthesisRequest(
        job_id=job.id,
        text=job.input_text,
        voice_profile_id=job.voice_profile_id,
        reference_audio_path=resolved_input.reference_audio_path,
        reference_text=resolved_input.reference_text,
    )
)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_worker_flow.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/tts_service/services/jobs.py src/tts_service/services/worker.py tests/test_worker_flow.py
git commit -m "fix: resolve stored voice references in worker"
```

### Task 3: Load preset system voices from a startup manifest

**Files:**
- Modify: `src/tts_service/config.py`
- Modify: `src/tts_service/services/voices.py`
- Modify: `src/tts_service/main.py`
- Create: `tests/test_system_voice_manifest.py`

- [ ] **Step 1: Write the failing tests**

```python
import json

from fastapi.testclient import TestClient

from tts_service.main import create_app


def test_app_loads_system_voices_from_manifest(tmp_path) -> None:
    manifest_path = tmp_path / "system_voices.json"
    reference_path = tmp_path / "narrator.wav"
    reference_path.write_bytes(b"RIFFsystem")
    manifest_path.write_text(
        json.dumps(
            [
                {
                    "name": "narrator",
                    "clone_mode": "clone",
                    "audio_path": str(reference_path),
                    "source_label": "builtin:narrator",
                }
            ]
        ),
        encoding="utf-8",
    )

    app = create_app(
        {
            "database_url": f"sqlite:///{tmp_path}/app.db",
            "storage_root": str(tmp_path / "storage"),
            "system_voices_manifest_path": str(manifest_path),
        }
    )
    client = TestClient(app)

    bootstrap = client.post("/debug/bootstrap-user", json={"name": "alice"})
    api_key = bootstrap.json()["api_key"]
    listing = client.get("/v1/voices", headers={"Authorization": f"Bearer {api_key}"})

    assert listing.status_code == 200
    assert {item["name"] for item in listing.json()["items"]} == {"narrator"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_system_voice_manifest.py -v`
Expected: FAIL because settings do not accept a manifest path and startup does not load preset voices.

- [ ] **Step 3: Write the minimal implementation**

```python
class Settings(BaseSettings):
    system_voices_manifest_path: str | None = None
```

```python
def load_system_voices_from_manifest(self, session: Session, manifest_path: str) -> None:
    entries = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    for entry in entries:
        source_label = str(entry.get("source_label") or entry["name"])
        existing = session.scalar(
            select(VoiceProfile).where(
                VoiceProfile.scope == "system",
                VoiceProfile.source_label == source_label,
            )
        )
        if existing is not None:
            continue
        reference_path = Path(entry["audio_path"])
        self.create_system_voice(
            session=session,
            name=str(entry["name"]),
            clone_mode=str(entry.get("clone_mode", "clone")),
            reference_audio_filename=reference_path.name,
            reference_audio_content=reference_path.read_bytes(),
            reference_text=str(entry["reference_text"]) if entry.get("reference_text") else None,
            description=str(entry["description"]) if entry.get("description") else None,
            source_label=source_label,
        )
```

```python
with session_factory() as session:
    if settings.system_voices_manifest_path:
        app.state.voice_service.load_system_voices_from_manifest(
            session=session,
            manifest_path=settings.system_voices_manifest_path,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_system_voice_manifest.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/tts_service/config.py src/tts_service/services/voices.py src/tts_service/main.py tests/test_system_voice_manifest.py
git commit -m "feat: load preset system voices from manifest"
```

### Task 4: Update documentation and run focused verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Write the documentation updates**

```markdown
Create a base TTS job with the provider default voice:

```bash
curl -X POST http://127.0.0.1:8000/v1/jobs \
  -H "Authorization: Bearer ${API_KEY}" \
  -H 'Content-Type: application/json' \
  -d '{"text":"hello world"}'
```

Create a job with a preset system voice:

```bash
curl -X POST http://127.0.0.1:8000/v1/jobs \
  -H "Authorization: Bearer ${API_KEY}" \
  -H 'Content-Type: application/json' \
  -d '{"text":"hello world","voice_profile_id":"SYSTEM_VOICE_ID"}'
```
```

- [ ] **Step 2: Run focused verification**

Run: `.venv/bin/pytest tests/test_jobs_api.py tests/test_worker_flow.py tests/test_system_voice_manifest.py -v`
Expected: PASS

- [ ] **Step 3: Run the broader suite**

Run: `.venv/bin/pytest -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add README.md tests/test_jobs_api.py tests/test_worker_flow.py tests/test_system_voice_manifest.py src/tts_service/api/jobs.py src/tts_service/services/jobs.py src/tts_service/services/worker.py src/tts_service/config.py src/tts_service/services/voices.py src/tts_service/main.py
git commit -m "feat: add base tts and preset system voice support"
```
