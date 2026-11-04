"""phase 2 auth and identity

Revision ID: b4a1c8f309d2
Revises: 4f1d9c27f6a2
Create Date: 2026-11-02 16:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b4a1c8f309d2'
down_revision: Union[str, Sequence[str], None] = '4f1d9c27f6a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Update users table with scoping and 2FA columns
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('branch_id', sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column('department_id', sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column('totp_secret', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('is_totp_enabled', sa.Boolean(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('recovery_codes', sa.JSON(), nullable=True))
        batch_op.create_foreign_key('fk_user_branch', 'branches', ['branch_id'], ['id'])
        batch_op.create_foreign_key('fk_user_department', 'departments', ['department_id'], ['id'])

    # 2. Create attendance_devices table
    op.create_table(
        'attendance_devices',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=96), nullable=False),
        sa.Column('branch_id', sa.String(length=36), nullable=True),
        sa.Column('mode', sa.Enum('AUTO', 'IN_ONLY', 'OUT_ONLY', name='devicemode'), nullable=False, server_default='AUTO'),
        sa.Column('status', sa.Enum('ACTIVE', 'REVOKED', name='devicestatus'), nullable=False, server_default='ACTIVE'),
        sa.Column('registered_by', sa.String(length=36), nullable=True),
        sa.Column('last_seen_at', sa.DateTime(), nullable=True),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['registered_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('attendance_devices', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_attendance_devices_organization_id'), ['organization_id'], unique=False)

    # 3. Create device_enrollment_codes table
    op.create_table(
        'device_enrollment_codes',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('code_hash', sa.String(length=64), nullable=False),
        sa.Column('created_by_user_id', sa.String(length=36), nullable=False),
        sa.Column('device_name', sa.String(length=96), nullable=False),
        sa.Column('branch_id', sa.String(length=36), nullable=True),
        sa.Column('mode', sa.Enum('AUTO', 'IN_ONLY', 'OUT_ONLY', name='devicemode'), nullable=False, server_default='AUTO'),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('used_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id']),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('device_enrollment_codes', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_device_enrollment_codes_code_hash'), ['code_hash'], unique=True)
        batch_op.create_index(batch_op.f('ix_device_enrollment_codes_organization_id'), ['organization_id'], unique=False)

    # 4. Update employees table with PIN columns
    with op.batch_alter_table('employees', schema=None) as batch_op:
        batch_op.add_column(sa.Column('pin_hash', sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column('failed_pin_attempts', sa.Integer(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('pin_locked_until', sa.DateTime(), nullable=True))

    # 5. Data migration:
    # First convert PostgreSQL enum column to VARCHAR(32) so text updates/deletes succeed safely
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE users ALTER COLUMN role TYPE VARCHAR(32)")

    # Handle existing users with role 'EMPLOYEE' or other obsolete roles.
    # In the kiosk-first model, employees have NO login user accounts (they exist only in the employees table).
    # Delete unreferenced employee user records and their refresh tokens.
    op.execute("""
        DELETE FROM refresh_tokens
        WHERE user_id IN (
            SELECT id FROM users
            WHERE role = 'EMPLOYEE' OR role NOT IN ('SUPER_ADMIN', 'ORG_ADMIN', 'ORGANIZATION_ADMIN', 'HR_ADMIN', 'MANAGER', 'ATTENDANCE_DEVICE')
        )
    """)
    op.execute("""
        DELETE FROM users
        WHERE role = 'EMPLOYEE' OR role NOT IN ('SUPER_ADMIN', 'ORG_ADMIN', 'ORGANIZATION_ADMIN', 'HR_ADMIN', 'MANAGER', 'ATTENDANCE_DEVICE')
    """)

    # ORG_ADMIN -> ORGANIZATION_ADMIN (with PostgreSQL enum type migration)
    op.execute("UPDATE users SET role = 'ORGANIZATION_ADMIN' WHERE role = 'ORG_ADMIN'")

    if bind.dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS role")
        op.execute("CREATE TYPE role AS ENUM ('SUPER_ADMIN', 'ORGANIZATION_ADMIN', 'HR_ADMIN', 'MANAGER', 'ATTENDANCE_DEVICE')")
        op.execute("ALTER TABLE users ALTER COLUMN role TYPE role USING (role::role)")

    # 6. Data migration: convert existing scanner-role users into attendance_devices rows
    op.execute("""
        INSERT INTO attendance_devices (id, organization_id, name, branch_id, mode, status, registered_by, created_at)
        SELECT u.id, u.organization_id, u.full_name, u.branch_id, 'AUTO', 'ACTIVE', u.id, u.created_at
        FROM users u
        WHERE u.role = 'ATTENDANCE_DEVICE'
        AND NOT EXISTS (SELECT 1 FROM attendance_devices ad WHERE ad.id = u.id)
    """)


def downgrade() -> None:
    bind = op.get_bind()

    # 1. Clean up migrated attendance_devices
    op.execute("DELETE FROM attendance_devices WHERE id IN (SELECT id FROM users WHERE role = 'ATTENDANCE_DEVICE')")

    # 2. Data migration rollback (revert role enum in PostgreSQL or SQLite)
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE users ALTER COLUMN role TYPE VARCHAR(32)")
        op.execute("UPDATE users SET role = 'ORG_ADMIN' WHERE role = 'ORGANIZATION_ADMIN'")
        op.execute("DROP TYPE IF EXISTS role")
        op.execute("CREATE TYPE role AS ENUM ('SUPER_ADMIN', 'ORG_ADMIN', 'HR_ADMIN', 'MANAGER', 'EMPLOYEE', 'ATTENDANCE_DEVICE')")
        op.execute("ALTER TABLE users ALTER COLUMN role TYPE role USING (role::role)")
    else:
        op.execute("UPDATE users SET role = 'ORG_ADMIN' WHERE role = 'ORGANIZATION_ADMIN'")

    # 3. Revert employees table
    with op.batch_alter_table('employees', schema=None) as batch_op:
        batch_op.drop_column('pin_locked_until')
        batch_op.drop_column('failed_pin_attempts')
        batch_op.drop_column('pin_hash')

    # 4. Drop device_enrollment_codes
    with op.batch_alter_table('device_enrollment_codes', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_device_enrollment_codes_organization_id'))
        batch_op.drop_index(batch_op.f('ix_device_enrollment_codes_code_hash'))
    op.drop_table('device_enrollment_codes')

    # 5. Drop attendance_devices
    with op.batch_alter_table('attendance_devices', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_attendance_devices_organization_id'))
    op.drop_table('attendance_devices')

    # 6. Revert users table
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_constraint('fk_user_department', type_='foreignkey')
        batch_op.drop_constraint('fk_user_branch', type_='foreignkey')
        batch_op.drop_column('recovery_codes')
        batch_op.drop_column('is_totp_enabled')
        batch_op.drop_column('totp_secret')
        batch_op.drop_column('department_id')
        batch_op.drop_column('branch_id')

    # 7. Drop enums on PostgreSQL if present
    if bind.dialect.name == "postgresql":
        sa.Enum(name='devicemode').drop(bind, checkfirst=True)
        sa.Enum(name='devicestatus').drop(bind, checkfirst=True)
