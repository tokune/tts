# API Reference - VoxCPM HTTP Service

Welcome to the official API documentation for the VoxCPM HTTP Service. This service provides an asynchronous interface for high-quality text-to-speech synthesis and voice cloning.

## Base Information

- **Base URL**: `/v1` (Primary API) / `/` (Debug/System)
- **Authentication**: All business endpoints require a `Bearer` token (API Key) in the `Authorization` header.
- **Content-Type**: 
  - For JSON requests: `application/json`
  - For file uploads (cloning): `multipart/form-data`

---

## 1. Authentication

### Verify API Key
`POST /auth/keys/verify`

Verify if the provided API key is valid and active.

**Request Body:**
```json
{
  "api_key": "string"
}
```

**Responses:**
- `200 OK`: Key is valid.
- `401 Unauthorized`: Key is invalid or expired.

---

## 2. Voice Profiles

Manage reusable voice identities.

### Create Voice Profile
`POST /v1/voices`

Creates a reusable voice profile from a reference audio sample.

**Request Body (multipart/form-data):**
| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `name` | string | Yes | A unique name for this voice profile. |
| `clone_mode` | string | No | e.g., `clone`. |
| `consent_statement` | string | No | Legal/usage consent text. |
| `reference_audio` | file | Yes | The source audio file for cloning. |

**Responses:**
- `201 Created`: Profile created successfully. Returns the profile ID.
- `400 Bad Request`: Invalid parameters or unsupported audio format.

### List Voice Profiles
`GET /v1/voices`

Retrieve all voice profiles associated with the authenticated user.

**Responses:**
- `200 OK`: Returns an array of voice profile objects.

---

## 3. Speech Synthesis Jobs

The core workflow for generating speech.

### Submit Synthesis Job
`POST /v1/jobs`

Submit a request to generate audio. This is an **asynchronous** operation.

**Request Body (multipart/form-data):**
| Field | Type | Required | Description |
| :---| :--- | :--- | :--- |
| `text` | string | Yes | The text to be synthesized. |
| `voice_profile_id` | string | No | ID of an existing profile. |
| `clone_mode` | string | No | e.g., `ultimate_clone` for one-off jobs. |
| `reference_audio` | file | No | Required if `clone_mode` is used without a profile. |
  
**Responses:**
- `202 Accepted`: Job queued. Returns `job_id`.

### Check Job Status
`GET /v1/jobs/{job_id}`

Check the progress of a specific synthesis task.

**Responses:**
- `200 OK`: Returns status (`pending`, `processing`, `completed`, `failed`) and metadata.
- `404 Not Found`: Job ID does not exist.

### Download Audio
`GET /v1/jobs/{job_id}/audio`

Download the resulting `.wav` file.

**Responses:**
- `200 OK`: Returns the binary audio stream.
- `404 Not Found`: Job not found or audio not yet generated.

### Cancel Job
`DELETE /v1/jobs/{job_id}`

Cancel a pending or processing job.

**Responses:**
- `204 No Content`: Job cancelled successfully.

---

## 4. System & Debugging

*Note: These endpoints are typically only available in development environments.*

### Bootstrap User
`POST /debug/bootstrap-user`

Quickly creates a test user and generates an API key.

**Request Body:**
```json
{
  `name`: "tester"
}
```

### Health Check
`GET /healthz`

Simple endpoint to check if the service is running.

**Responses:**
- `200 OK`: `{"status": "ok"}`
