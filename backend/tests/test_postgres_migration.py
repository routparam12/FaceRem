"""PostgreSQL migration test.

Gated by POSTGRES_TEST_URL environment variable.
Seeds legacy database with ORG_ADMIN, EMPLOYEE, and scanner users at 4f1d9c27f6a2,
executes upgrade to head (Phase 2), verifies data migration, downgrades to 4f1d9c27f6a2,
and re-upgrades to head without errors.
"""

import os
from pathlib import Path
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from sqlalchemy import create_engine, text

from alembic import command
from alembic.config import Config

POSTGRES_TEST_URL = os.environ.get("POSTGRES_TEST_URL")
if POSTGRES_TEST_URL:
    os.environ["DATABASE_URL"] = POSTGRES_TEST_URL
pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(
        not POSTGRES_TEST_URL,
        reason="POSTGRES_TEST_URL environment variable is not set; skipping live PostgreSQL migration test",
    ),
]


def test_postgresql_legacy_roles_migration_lifecycle():
    engine = create_engine(POSTGRES_TEST_URL, isolation_level="AUTOCOMMIT")

    alembic_cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
    alembic_cfg.set_main_option("sqlalchemy.url", POSTGRES_TEST_URL)

    # 1. Downgrade to 4f1d9c27f6a2 (legacy schema before Phase 2)
    command.downgrade(alembic_cfg, "4f1d9c27f6a2")

    org_id = str(uuid.uuid4())
    admin_id = str(uuid.uuid4())
    emp_user_id = str(uuid.uuid4())
    scanner_id = str(uuid.uuid4())

    with engine.connect() as conn:
        # Seed test organization
        conn.execute(
            text("""
                INSERT INTO organizations (id, name, slug, plan, is_active, created_at)
                VALUES (:id, 'Postgres Migration Org', 'pg-mig-org', 'trial', true, now())
                ON CONFLICT (slug) DO NOTHING
            """),
            {"id": org_id},
        )
        row = conn.execute(text("SELECT id FROM organizations WHERE slug = 'pg-mig-org'")).first()
        org_id = row[0]

        # Clean existing test records if any
        conn.execute(text("DELETE FROM refresh_tokens WHERE user_id IN (SELECT id FROM users WHERE email IN ('pg_admin@mig.demo', 'pg_emp@mig.demo', 'pg_scanner@mig.demo'))"))
        conn.execute(text("DELETE FROM users WHERE email IN ('pg_admin@mig.demo', 'pg_emp@mig.demo', 'pg_scanner@mig.demo')"))

        # Seed ORG_ADMIN, EMPLOYEE, and ATTENDANCE_DEVICE
        conn.execute(
            text("""
                INSERT INTO users (id, organization_id, email, password_hash, full_name, role, is_active, created_at)
                VALUES
                    (:admin_id, :org_id, 'pg_admin@mig.demo', 'hash1', 'PG Admin', 'ORG_ADMIN', true, now()),
                    (:emp_id, :org_id, 'pg_emp@mig.demo', 'hash2', 'PG Employee User', 'EMPLOYEE', true, now()),
                    (:scanner_id, :org_id, 'pg_scanner@mig.demo', 'hash3', 'PG Scanner Kiosk', 'ATTENDANCE_DEVICE', true, now())
            """),
            {"admin_id": admin_id, "emp_id": emp_user_id, "scanner_id": scanner_id, "org_id": org_id},
        )

    # 2. Upgrade to head
    command.upgrade(alembic_cfg, "head")

    with engine.connect() as conn:
        # Verify ORG_ADMIN was migrated to ORGANIZATION_ADMIN
        admin_row = conn.execute(text("SELECT role FROM users WHERE email = 'pg_admin@mig.demo'")).first()
        assert admin_row is not None
        assert admin_row[0] == "ORGANIZATION_ADMIN"

        # Verify legacy EMPLOYEE user was cleaned up from users table
        emp_row = conn.execute(text("SELECT id FROM users WHERE email = 'pg_emp@mig.demo'")).first()
        assert emp_row is None

        # Verify ATTENDANCE_DEVICE user was converted into attendance_devices row
        device_row = conn.execute(text("SELECT id, name, status, mode FROM attendance_devices WHERE id = :id"), {"id": scanner_id}).first()
        assert device_row is not None
        assert device_row[1] == "PG Scanner Kiosk"
        assert device_row[2] == "ACTIVE"
        assert device_row[3] == "AUTO"

    # 3. Downgrade back to 4f1d9c27f6a2
    command.downgrade(alembic_cfg, "4f1d9c27f6a2")

    with engine.connect() as conn:
        # Verify ORGANIZATION_ADMIN reverted to ORG_ADMIN
        admin_row = conn.execute(text("SELECT role FROM users WHERE email = 'pg_admin@mig.demo'")).first()
        assert admin_row is not None
        assert admin_row[0] == "ORG_ADMIN"

    # 4. Re-upgrade to head
    command.upgrade(alembic_cfg, "head")

    with engine.connect() as conn:
        admin_row = conn.execute(text("SELECT role FROM users WHERE email = 'pg_admin@mig.demo'")).first()
        assert admin_row is not None
        assert admin_row[0] == "ORGANIZATION_ADMIN"

