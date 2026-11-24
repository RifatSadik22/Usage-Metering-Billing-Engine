"""initial billing schema

Revision ID: 001initial
Revises:
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "001initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "plans",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("monthly_api_call_limit", sa.Integer(), nullable=False),
        sa.Column("monthly_ai_token_limit", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("monthly_api_call_limit >= 0", name="ck_plan_api_limit"),
        sa.CheckConstraint("monthly_ai_token_limit >= 0", name="ck_plan_token_limit"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("api_key_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("api_key_hash"),
    )
    op.create_table(
        "subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("stripe_customer_id", sa.String(length=255)),
        sa.Column("stripe_subscription_id", sa.String(length=255)),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("billing_period_start", sa.DateTime()),
        sa.Column("billing_period_end", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", name="uq_subscription_tenant"),
        sa.UniqueConstraint("stripe_subscription_id", name="uq_subscription_stripe_id"),
    )
    op.create_table(
        "usage_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("usage_type", sa.String(length=50), nullable=False),
        sa.Column("api_call_quantity", sa.Integer(), nullable=False),
        sa.Column("fresh_input_tokens", sa.Integer(), nullable=False),
        sa.Column("cached_input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("reasoning_tokens", sa.Integer(), nullable=False),
        sa.Column("total_quota_counted_tokens", sa.Integer(), nullable=False),
        sa.Column("cost_micro_usd", sa.Integer(), nullable=False),
        sa.Column("pricing_version", sa.String(length=50), nullable=False),
        sa.Column("usage_period", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("api_call_quantity >= 0", name="ck_usage_api"),
        sa.CheckConstraint("fresh_input_tokens >= 0", name="ck_usage_fresh"),
        sa.CheckConstraint("cached_input_tokens >= 0", name="ck_usage_cached"),
        sa.CheckConstraint("output_tokens >= 0", name="ck_usage_output"),
        sa.CheckConstraint("reasoning_tokens >= 0", name="ck_usage_reasoning"),
        sa.CheckConstraint("total_quota_counted_tokens >= 0", name="ck_usage_total"),
        sa.CheckConstraint("cost_micro_usd >= 0", name="ck_usage_cost"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_usage_tenant_key"),
    )
    op.create_index("ix_usage_tenant_period", "usage_events", ["tenant_id", "usage_period"])
    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("original_status", sa.Integer(), nullable=False),
        sa.Column("original_body", postgresql.JSONB(), nullable=False),
        sa.Column("usage_event_id", postgresql.UUID(as_uuid=True)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["usage_event_id"], ["usage_events.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_idempotency_tenant_key"),
    )
    op.create_table(
        "processed_stripe_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("stripe_event_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("processing_metadata", postgresql.JSONB(), nullable=False),
        sa.Column("processed_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stripe_event_id"),
    )
    op.create_table(
        "background_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("logical_key", sa.String(length=255), nullable=False),
        sa.Column("job_type", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("next_retry_at", sa.DateTime(), nullable=False),
        sa.Column("last_error", sa.String(length=2000)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("attempt_count >= 0", name="ck_job_attempt"),
        sa.CheckConstraint("max_attempts >= 1", name="ck_job_max_attempt"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("logical_key", name="uq_background_job_key"),
    )
    op.create_index("ix_background_jobs_claim", "background_jobs", ["status", "next_retry_at"])


def downgrade() -> None:
    op.drop_table("background_jobs")
    op.drop_table("processed_stripe_events")
    op.drop_table("idempotency_records")
    op.drop_index("ix_usage_tenant_period", "usage_events")
    op.drop_table("usage_events")
    op.drop_table("subscriptions")
    op.drop_table("tenants")
    op.drop_table("plans")
