from tts_service.main import create_app
from tts_service.services.worker import WorkerService


def run_once() -> bool:
    app = create_app()
    worker = WorkerService(
        session_factory=app.state.session_factory,
        file_storage=app.state.file_storage,
        provider=app.state.provider,
        job_service=app.state.job_service,
    )
    return worker.process_next_job()
