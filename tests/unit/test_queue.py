def test_task_importable():
    from core.queue.tasks import run_research_job
    assert callable(run_research_job)


def test_worker_settings_importable():
    from core.queue.worker import WorkerSettings
    assert "run_research_job" in [f.__name__ for f in WorkerSettings.functions]
