from fastapi.testclient import TestClient

from tts_service.main import create_app
from tts_service.worker import cli


class SequenceWorker:
    def __init__(self, results: list[bool]) -> None:
        self._results = list(results)
        self.calls = 0

    def process_next_job(self) -> bool:
        result = self._results[self.calls]
        self.calls += 1
        return result


def test_run_poll_loop_sleeps_when_queue_is_empty() -> None:
    worker = SequenceWorker([True, False])
    keep_running_states = iter([True, True, False])
    sleep_calls: list[float] = []

    cli.run_poll_loop(
        worker=worker,
        poll_interval=0.25,
        should_continue=lambda: next(keep_running_states),
        sleep=sleep_calls.append,
    )

    assert worker.calls == 2
    assert sleep_calls == [0.25]


def test_main_runs_worker_once_when_requested(tmp_path, monkeypatch) -> None:
    app = create_app(
        {
            "database_url": f"sqlite:///{tmp_path}/app.db",
            "storage_root": str(tmp_path / "storage"),
        }
    )
    client = TestClient(app)

    bootstrap = client.post("/debug/bootstrap-user", json={"name": "alice"})
    api_key = bootstrap.json()["api_key"]
    job = client.post(
        "/v1/jobs",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"text": "hello"},
    ).json()

    worker = cli.build_worker(app)
    monkeypatch.setattr(cli, "build_worker", lambda: worker)

    exit_code = cli.main(["--once"])

    assert exit_code == 0

    detail = client.get(f"/v1/jobs/{job['id']}", headers={"Authorization": f"Bearer {api_key}"})
    assert detail.status_code == 200
    assert detail.json()["status"] == "succeeded"


def test_main_polls_by_default(monkeypatch) -> None:
    sentinel_worker = object()
    captured: dict[str, object] = {}

    monkeypatch.setattr(cli, "build_worker", lambda: sentinel_worker)

    def fake_run_poll_loop(*, worker, poll_interval: float, should_continue=None, sleep=None) -> None:
        captured["worker"] = worker
        captured["poll_interval"] = poll_interval

    monkeypatch.setattr(cli, "run_poll_loop", fake_run_poll_loop)

    exit_code = cli.main(["--poll-interval", "0.25"])

    assert exit_code == 0
    assert captured == {"worker": sentinel_worker, "poll_interval": 0.25}
