from __future__ import annotations

import argparse
import time
from collections.abc import Callable, Sequence

from fastapi import FastAPI

from tts_service.main import create_app
from tts_service.services.worker import WorkerService


def build_worker(app: FastAPI | None = None) -> WorkerService:
    app = app or create_app()
    return WorkerService(
        session_factory=app.state.session_factory,
        file_storage=app.state.file_storage,
        provider=app.state.provider,
        job_service=app.state.job_service,
    )


def run_once(worker: WorkerService | None = None) -> bool:
    active_worker = worker or build_worker()
    return active_worker.process_next_job()


def run_poll_loop(
    worker: WorkerService | None = None,
    poll_interval: float = 1.0,
    should_continue: Callable[[], bool] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    active_worker = worker or build_worker()
    keep_running = should_continue or (lambda: True)

    while keep_running():
        processed = active_worker.process_next_job()
        if not processed:
            sleep(poll_interval)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Process queued TTS jobs.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true", help="Process a single queued job and exit.")
    mode.add_argument("--poll", action="store_true", help="Continuously poll for queued jobs.")
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=1.0,
        help="Seconds to sleep when no queued jobs are available.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    worker = build_worker()

    if args.once:
        run_once(worker=worker)
        return 0

    run_poll_loop(worker=worker, poll_interval=args.poll_interval)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
