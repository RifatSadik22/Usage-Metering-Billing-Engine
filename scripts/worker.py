import logging
import time
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.models import BackgroundJob, Tenant, UsageEvent

log = logging.getLogger("billing.worker")


def enqueue_daily_summaries(db: Session, day: datetime | None = None) -> int:
    day = day or datetime.now(UTC)
    period = day.date()
    tenants = db.scalars(select(Tenant)).all()
    count = 0
    for tenant in tenants:
        key = f"usage-summary:{tenant.id}:{period.isoformat()}"
        existing = db.scalar(select(BackgroundJob).where(BackgroundJob.logical_key == key))
        if existing is None:
            db.add(
                BackgroundJob(
                    logical_key=key,
                    job_type="daily_usage_summary",
                    status="pending",
                    max_attempts=get_settings().worker_max_attempts,
                )
            )
            count += 1
    db.commit()
    return count


def claim_job(db: Session):
    now = datetime.now(UTC)
    job = db.scalar(
        select(BackgroundJob)
        .where(
            BackgroundJob.status.in_(("pending", "retrying")), BackgroundJob.next_retry_at <= now
        )
        .order_by(BackgroundJob.created_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if job:
        job.status = "running"
        db.commit()
    return job


def process_job(db: Session, job: BackgroundJob) -> dict:
    parts = job.logical_key.split(":")
    tenant_id = uuid.UUID(parts[1])
    day = parts[2]
    period = datetime.strptime(day, "%Y-%m-%d").date().replace(day=1)
    result = db.execute(
        select(
            func.coalesce(func.sum(UsageEvent.api_call_quantity), 0),
            func.coalesce(func.sum(UsageEvent.total_quota_counted_tokens), 0),
            func.coalesce(func.sum(UsageEvent.cost_micro_usd), 0),
        ).where(
            UsageEvent.tenant_id == tenant_id,
            UsageEvent.usage_period == period,
        )
    ).one()
    summary = {
        "tenant_id": tenant_id,
        "day": day,
        "api_calls": int(result[0]),
        "tokens": int(result[1]),
        "micro_usd": int(result[2]),
    }
    log.info("usage_summary %s", summary)
    return summary


def run_once() -> None:
    with SessionLocal.begin() as db:
        enqueue_daily_summaries(db)
    with SessionLocal.begin() as db:
        job = claim_job(db)
    if not job:
        return
    try:
        with SessionLocal.begin() as db:
            process_job(db, job)
            job = db.get(BackgroundJob, job.id)
            job.status = "completed"
            job.last_error = None
    except Exception as exc:
        with SessionLocal.begin() as db:
            job = db.get(BackgroundJob, job.id)
            job.attempt_count += 1
            job.last_error = str(exc)[:2000]
            if job.attempt_count >= job.max_attempts:
                job.status = "failed"
                log.error(
                    '{"alert":"background_job_exhausted","job_id":"%s","error":"%s"}',
                    job.id,
                    job.last_error,
                )
            else:
                job.status = "retrying"
                job.next_retry_at = datetime.now(UTC) + timedelta(seconds=2**job.attempt_count)


def main() -> None:
    settings = get_settings()
    log.info("starting durable usage reconciliation worker")
    while True:
        run_once()
        time.sleep(settings.worker_poll_seconds)


if __name__ == "__main__":
    logging.basicConfig(level=getattr(logging, get_settings().log_level.upper(), logging.INFO))
    main()
