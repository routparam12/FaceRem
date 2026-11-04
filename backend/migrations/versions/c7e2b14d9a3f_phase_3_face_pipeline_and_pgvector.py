"""Phase 3 face pipeline and pgvector storage.

Revision ID: c7e2b14d9a3f
Revises: b4a1c8f309d2
Create Date: 2026-11-03

Required privileges on PostgreSQL:
- Superuser or database owner privileges are required to run 'CREATE EXTENSION IF NOT EXISTS vector'.
- If the vector extension is not pre-installed on the host OS, the migration logs a warning and
  falls back safely to JSON storage for the vector column.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'c7e2b14d9a3f'
down_revision: Union[str, None] = 'b4a1c8f309d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    import os
    bind = op.get_bind()
    has_vector_extension = False
    app_env = os.getenv("APP_ENV", "development").lower()

    # 1. Enable pgvector extension on PostgreSQL if available
    if bind.dialect.name == "postgresql":
        avail = bind.execute(sa.text("SELECT 1 FROM pg_available_extensions WHERE name = 'vector'")).first()
        if avail is not None:
            op.execute("CREATE EXTENSION IF NOT EXISTS vector")
            has_vector_extension = True
        else:
            if app_env == "production":
                raise RuntimeError(
                    "CRITICAL: pgvector extension is missing on PostgreSQL in production environment (APP_ENV=production). "
                    "The 'vector' extension is required for production face search indexing and similarity operations. "
                    "Install pgvector on the PostgreSQL instance before running migrations."
                )
            has_vector_extension = False

    # 2. Add columns to face_profiles
    with op.batch_alter_table('face_profiles', schema=None) as batch_op:
        batch_op.add_column(sa.Column('pose', sa.String(length=16), server_default='FRONT', nullable=False))
        batch_op.add_column(sa.Column('enrollment_id', sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column('consented_by_user_id', sa.String(length=36), nullable=True))
        batch_op.create_foreign_key('fk_face_profile_consented_by', 'users', ['consented_by_user_id'], ['id'])
        batch_op.create_index(batch_op.f('ix_face_profiles_enrollment_id'), ['enrollment_id'], unique=False)

    # 3. Add embedding_vec column
    if bind.dialect.name == "postgresql" and has_vector_extension:
        op.execute("ALTER TABLE face_profiles ADD COLUMN embedding_vec vector(512)")
    elif bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE face_profiles ADD COLUMN embedding_vec JSON")
    else:
        with op.batch_alter_table('face_profiles', schema=None) as batch_op:
            batch_op.add_column(sa.Column('embedding_vec', sa.JSON(), nullable=True))

    # 4. Data migration:
    # Delete stub-engine profiles (different dimension, non-ArcFace).
    # Those employees must re-enroll with the real InsightFace engine.
    op.execute("""
        DELETE FROM face_profiles
        WHERE model_name != 'buffalo_l'
    """)

    # Backfill embedding_vec from embedding for active ArcFace 512-d profiles
    if bind.dialect.name == "postgresql" and has_vector_extension:
        op.execute("""
            UPDATE face_profiles
            SET embedding_vec = embedding::text::vector
            WHERE model_name = 'buffalo_l' AND embedding_vec IS NULL
        """)
    else:
        op.execute("""
            UPDATE face_profiles
            SET embedding_vec = embedding
            WHERE model_name = 'buffalo_l' AND embedding_vec IS NULL
        """)


def downgrade() -> None:
    bind = op.get_bind()

    # Drop added columns from face_profiles
    with op.batch_alter_table('face_profiles', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_face_profiles_enrollment_id'))
        batch_op.drop_constraint('fk_face_profile_consented_by', type_='foreignkey')
        batch_op.drop_column('embedding_vec')
        batch_op.drop_column('consented_by_user_id')
        batch_op.drop_column('enrollment_id')
        batch_op.drop_column('pose')
