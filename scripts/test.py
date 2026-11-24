import os
import subprocess
import sys

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from app.core.config import get_settings

TEST_DATABASE = "billing_capstone_test"


def main() -> None:
    configured_url = make_url(get_settings().database_url)
    if configured_url.database == TEST_DATABASE:
        raise RuntimeError(
            "DATABASE_URL already targets the disposable test database; "
            "configure the regular application database URL instead."
        )

    admin_engine = create_engine(
        configured_url.set(database="postgres"),
        isolation_level="AUTOCOMMIT",
    )
    try:
        with admin_engine.connect() as connection:
            connection.exec_driver_sql(f"DROP DATABASE IF EXISTS {TEST_DATABASE} WITH (FORCE)")
            connection.exec_driver_sql(f"CREATE DATABASE {TEST_DATABASE}")
    finally:
        admin_engine.dispose()

    test_environment = os.environ.copy()
    test_environment["DATABASE_URL"] = configured_url.set(database=TEST_DATABASE).render_as_string(
        hide_password=False
    )
    for command in (
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        [sys.executable, "-m", "scripts.seed"],
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "--cov=app",
            "--cov-report=term-missing",
        ],
    ):
        subprocess.run(command, env=test_environment, check=True)


if __name__ == "__main__":
    main()
