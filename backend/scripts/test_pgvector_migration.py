"""
Test migration upgrade, downgrade, and re-upgrade on real PostgreSQL with seeded stub profiles.
Reports exact counts of pruned stub profiles, re-enrollment requirements, and pgvector extension availability.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import psycopg
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

PG_URL = os.environ.get("POSTGRES_TEST_URL", "postgresql+psycopg://postgres:postgres@localhost:5433/faceattend_test")
os.environ["DATABASE_URL"] = PG_URL


def run_pg_migration_verification():
    print("=" * 70)
    print("POSTGRESQL MIGRATION & PGVECTOR VERIFICATION")
    print("=" * 70)
    print(f"Connecting to: {PG_URL}")

    engine = create_engine(PG_URL)

    # 1. Check pgvector extension availability in PostgreSQL
    with engine.connect() as conn:
        res = conn.execute(text("SELECT name, default_version, installed_version, comment FROM pg_available_extensions WHERE name = 'vector';")).fetchall()
        print(f"\n1. pgvector Extension Check in pg_available_extensions:")
        if res:
            for row in res:
                print(f"   Name: {row[0]}, Default: {row[1]}, Installed: {row[2]}, Comment: {row[3]}")
        else:
            print("   Extension 'vector' is NOT listed in pg_available_extensions on this PostgreSQL instance.")

        # Check PostgreSQL version
        pg_ver = conn.execute(text("SELECT version();")).scalar()
        print(f"   PostgreSQL Version: {pg_ver}")

    # 2. Setup Alembic config
    alembic_cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", PG_URL)

    # Reset clean schema in PostgreSQL
    print("\n2. Resetting PostgreSQL public schema to clean state...")
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))

    # Upgrade to Phase 2 head: b4a1c8f309d2 (prior to vector migration 0f8538efce30)
    print("   Upgrading to b4a1c8f309d2 (Phase 2 schema)...")
    command.upgrade(alembic_cfg, "b4a1c8f309d2")

    # 3. Seed test data containing both stub profiles and real profiles
    print("\n3. Seeding test employees and face profiles prior to vector migration...")
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO organizations (id, name, slug, plan, is_active, created_at)
            VALUES ('org-vec-test', 'Vector Test Org', 'vec-test', 'ENTERPRISE', true, now())
            ON CONFLICT DO NOTHING;
        """))
        # 5 employees with stub profiles
        for i in range(1, 6):
            conn.execute(text(f"""
                INSERT INTO employees (id, organization_id, employee_code, full_name, email, phone, job_title, is_active, created_at)
                VALUES ('emp-stub-{i}', 'org-vec-test', 'STUB{i:03d}', 'Stub User {i}', 'stub{i}@test.com', '', '', true, now());
            """))
            conn.execute(text(f"""
                INSERT INTO face_profiles (id, organization_id, employee_id, model_name, model_version, embedding, quality_score, consent_at, created_at)
                VALUES ('fp-stub-{i}', 'org-vec-test', 'emp-stub-{i}', 'stub', '1', '[0.1, 0.2, 0.3]', 0.9, now(), now());
            """))

        # 2 employees with real ArcFace profiles
        for i in range(1, 3):
            conn.execute(text(f"""
                INSERT INTO employees (id, organization_id, employee_code, full_name, email, phone, job_title, is_active, created_at)
                VALUES ('emp-arc-{i}', 'org-vec-test', 'ARC{i:03d}', 'Arc User {i}', 'arc{i}@test.com', '', '', true, now());
            """))
            conn.execute(text(f"""
                INSERT INTO face_profiles (id, organization_id, employee_id, model_name, model_version, embedding, quality_score, consent_at, created_at)
                VALUES ('fp-arc-{i}', 'org-vec-test', 'emp-arc-{i}', 'buffalo_l', '1', '[0.05, 0.15, 0.25]', 0.95, now(), now());
            """))

        count_stub = conn.execute(text("SELECT count(*) FROM face_profiles WHERE model_name = 'stub'")).scalar()
        count_arc = conn.execute(text("SELECT count(*) FROM face_profiles WHERE model_name = 'buffalo_l'")).scalar()
        print(f"   Seeded face profiles: {count_stub} stub profiles, {count_arc} buffalo_l profiles.")

    # 4. Upgrade to head (0f8538efce30)
    print("\n4. Upgrading to head (0f8538efce30: Vector storage & stub profile pruning)...")
    command.upgrade(alembic_cfg, "head")

    with engine.connect() as conn:
        remaining_stub = conn.execute(text("SELECT count(*) FROM face_profiles WHERE model_name = 'stub'")).scalar()
        remaining_arc = conn.execute(text("SELECT count(*) FROM face_profiles WHERE model_name = 'buffalo_l'")).scalar()
        all_profiles = conn.execute(text("SELECT count(*) FROM face_profiles")).scalar()
        
        # Check employees needing re-enrollment (no active face profiles)
        employees_without_profile = conn.execute(text("""
            SELECT e.id, e.employee_code, e.full_name
            FROM employees e
            LEFT JOIN face_profiles fp ON fp.employee_id = e.id AND fp.revoked_at IS NULL
            WHERE fp.id IS NULL AND e.organization_id = 'org-vec-test';
        """)).fetchall()

        print(f"\n   Post-Migration Profile Counts:")
        print(f"   - Stub profiles remaining: {remaining_stub} (Deleted: {count_stub - remaining_stub})")
        print(f"   - buffalo_l profiles remaining: {remaining_arc}")
        print(f"   - Total profiles in database: {all_profiles}")
        print(f"   - Employees requiring re-enrollment: {len(employees_without_profile)}")
        for emp in employees_without_profile:
            print(f"     * {emp[1]} ({emp[2]}, id={emp[0]})")

    # 5. Test Downgrade and Re-upgrade
    print("\n5. Testing Downgrade back to b4a1c8f309d2...")
    command.downgrade(alembic_cfg, "b4a1c8f309d2")
    print("   Downgrade succeeded.")

    print("\n6. Testing Re-upgrade back to head...")
    command.upgrade(alembic_cfg, "head")
    print("   Re-upgrade succeeded.")

    print("\n" + "=" * 70)
    print("POSTGRESQL MIGRATION VERIFICATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    run_pg_migration_verification()
