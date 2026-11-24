from app.core.database import SessionLocal
from app.models.models import BackgroundJob
from scripts.worker import process_job


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
