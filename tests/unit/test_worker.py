from app.core.database import SessionLocal
from app.models.models import BackgroundJob
from scripts.worker import process_job, run_once


def test_worker_success_result(seeded_database) -> None:
    with SessionLocal() as db:
        job = BackgroundJob(
            logical_key="usage-summary:00000000-0000-0000-0000-000000000000:2026-11-24",
            job_type="daily_usage_summary",
            status="running",
            max_attempts=5,
        )
        result = process_job(db, job)
    assert result["tenant_id"] == "00000000-0000-0000-0000-000000000000"
    assert "micro_usd" in result


def test_worker_temporary_failure_retries(seeded_database, monkeypatch) -> None:
    import scripts.worker as worker_module

    with SessionLocal.begin() as db:
        job = BackgroundJob(
            logical_key="usage-summary:test-temporary:2026-11-24",
            job_type="daily_usage_summary",
            status="pending",
            attempt_count=0,
            max_attempts=3,
        )
        db.add(job)

    def fail(*args, **kwargs):
        raise RuntimeError("temporary database failure")

    monkeypatch.setattr(worker_module, "process_job", fail)
    run_once()

    with SessionLocal() as db:
        stored = (
            db.query(BackgroundJob)
            .filter(BackgroundJob.logical_key == "usage-summary:test-temporary:2026-11-24")
            .one()
        )
        assert stored.status == "retrying"
        assert stored.attempt_count == 1
        assert "temporary database failure" in stored.last_error


def test_worker_permanent_failure_alerts(seeded_database, monkeypatch, caplog) -> None:
    import scripts.worker as worker_module

    with SessionLocal.begin() as db:
        job = BackgroundJob(
            logical_key="usage-summary:test-permanent:2026-11-24",
            job_type="daily_usage_summary",
            status="pending",
            attempt_count=0,
            max_attempts=1,
        )
        db.add(job)

    def fail(*args, **kwargs):
        raise RuntimeError("permanent database failure")

    monkeypatch.setattr(worker_module, "process_job", fail)
    with caplog.at_level("ERROR", logger="billing.worker"):
        run_once()

    with SessionLocal() as db:
        stored = (
            db.query(BackgroundJob)
            .filter(BackgroundJob.logical_key == "usage-summary:test-permanent:2026-11-24")
            .one()
        )
        assert stored.status == "failed"
        assert stored.attempt_count == 1
    assert "background_job_exhausted" in caplog.text
