"""Phase 4 camera-independent attendance and timezone.

Revision ID: d8f3a5b12c01
Revises: c7e2b14d9a3f
Create Date: 2026-11-03
"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8f3a5b12c01'
down_revision: Union[str, None] = 'c7e2b14d9a3f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Add timezone column to organizations
    with op.batch_alter_table('organizations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('timezone', sa.String(length=64), server_default='UTC', nullable=False))

    # 2. Create cameras table
    op.create_table(
        'cameras',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('source_type', sa.Enum('ANDROID_KIOSK', 'EDGE_AGENT', name='camerasourcetype'), nullable=False, server_default='ANDROID_KIOSK'),
        sa.Column('device_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=96), nullable=False),
        sa.Column('branch_id', sa.String(length=36), nullable=True),
        sa.Column('direction', sa.Enum('IN_ONLY', 'OUT_ONLY', 'AUTO', name='cameradirection'), nullable=False, server_default='AUTO'),
        sa.Column('assurance', sa.Enum('HIGH', 'STANDARD', name='cameraassurance'), nullable=False, server_default='HIGH'),
        sa.Column('enabled', sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], name='fk_camera_branch'),
        sa.ForeignKeyConstraint(['device_id'], ['attendance_devices.id'], name='fk_camera_device'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name='fk_camera_org'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('cameras', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_cameras_organization_id'), ['organization_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_cameras_device_id'), ['device_id'], unique=False)

    # 3. Data migration: existing kiosk devices get one camera row
    devices = bind.execute(
        sa.text("SELECT id, organization_id, name, branch_id, mode, status, created_at FROM attendance_devices")
    ).fetchall()
    for dev in devices:
        cam_id = str(uuid.uuid4())
        cam_name = f"{dev[2]} Camera"
        direction = str(dev[4]) if dev[4] in ('AUTO', 'IN_ONLY', 'OUT_ONLY') else 'AUTO'
        enabled = (str(dev[5]) == 'ACTIVE')
        bind.execute(
            sa.text("""
                INSERT INTO cameras (id, organization_id, source_type, device_id, name, branch_id, direction, assurance, enabled, created_at)
                VALUES (:id, :org_id, 'ANDROID_KIOSK', :dev_id, :name, :branch_id, :direction, 'HIGH', :enabled, :created_at)
            """),
            {
                "id": cam_id,
                "org_id": dev[1],
                "dev_id": dev[0],
                "name": cam_name,
                "branch_id": dev[3],
                "direction": direction,
                "enabled": enabled,
                "created_at": dev[6],
            }
        )

    # 4. Create attendance_events table
    op.create_table(
        'attendance_events',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('employee_id', sa.String(length=36), nullable=False),
        sa.Column('device_id', sa.String(length=36), nullable=False),
        sa.Column('camera_id', sa.String(length=36), nullable=True),
        sa.Column('source_type', sa.Enum('ANDROID_KIOSK', 'EDGE_AGENT', name='camerasourcetype'), nullable=False, server_default='ANDROID_KIOSK'),
        sa.Column('type', sa.Enum('CHECK_IN', 'CHECK_OUT', name='attendanceeventtype'), nullable=False),
        sa.Column('occurred_at', sa.DateTime(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('method', sa.Enum('FACE', 'PIN', name='attendancemethod'), nullable=False, server_default='FACE'),
        sa.Column('idempotency_key', sa.String(length=64), nullable=True),
        sa.Column('provisional', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('voided_at', sa.DateTime(), nullable=True),
        sa.Column('void_reason', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['camera_id'], ['cameras.id'], name='fk_event_camera'),
        sa.ForeignKeyConstraint(['device_id'], ['attendance_devices.id'], name='fk_event_device'),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], name='fk_event_employee'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name='fk_event_org'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'idempotency_key', name='uq_attendance_events_idempotency'),
    )
    with op.batch_alter_table('attendance_events', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_attendance_events_organization_id'), ['organization_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_attendance_events_employee_id'), ['employee_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_attendance_events_device_id'), ['device_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_attendance_events_camera_id'), ['camera_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_attendance_events_occurred_at'), ['occurred_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_attendance_events_idempotency_key'), ['idempotency_key'], unique=False)


def downgrade() -> None:
    bind = op.get_bind()

    # 1. Drop attendance_events table
    op.drop_table('attendance_events')

    # 2. Drop cameras table
    op.drop_table('cameras')

    # 3. Drop timezone from organizations
    with op.batch_alter_table('organizations', schema=None) as batch_op:
        batch_op.drop_column('timezone')

    # 4. Clean up enum types on PostgreSQL
    if bind.dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS attendancemethod")
        op.execute("DROP TYPE IF EXISTS attendanceeventtype")
        op.execute("DROP TYPE IF EXISTS cameraassurance")
        op.execute("DROP TYPE IF EXISTS cameradirection")
        op.execute("DROP TYPE IF EXISTS camerasourcetype")

