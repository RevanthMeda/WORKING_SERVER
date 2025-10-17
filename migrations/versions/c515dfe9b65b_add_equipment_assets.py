"""Add equipment_assets table and architecture storage

Revision ID: c515dfe9b65b
Revises: b4443b0fc8eb
Create Date: 2025-10-15 12:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c515dfe9b65b'
down_revision = 'b4443b0fc8eb'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('fds_reports', sa.Column('system_architecture_json', sa.Text(), nullable=True))

    op.create_table(
        'equipment_assets',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('model_key', sa.String(length=200), nullable=False, unique=True),
        sa.Column('display_name', sa.String(length=200), nullable=True),
        sa.Column('manufacturer', sa.String(length=120), nullable=True),
        sa.Column('image_url', sa.String(length=500), nullable=True),
        sa.Column('thumbnail_url', sa.String(length=500), nullable=True),
        sa.Column('local_path', sa.String(length=500), nullable=True),
        sa.Column('asset_source', sa.String(length=120), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('metadata_json', sa.Text(), nullable=True),
        sa.Column('fetched_at', sa.DateTime(), nullable=True),
        sa.Column('is_user_override', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    op.create_index(
        'idx_equipment_assets_model_key',
        'equipment_assets',
        ['model_key'],
        unique=False
    )


def downgrade():
    op.drop_index('idx_equipment_assets_model_key', table_name='equipment_assets')
    op.drop_table('equipment_assets')
    op.drop_column('fds_reports', 'system_architecture_json')

