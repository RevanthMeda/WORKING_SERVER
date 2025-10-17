"""Expand system architecture support with templates and version history

Revision ID: f4c62df9092b
Revises: c515dfe9b65b
Create Date: 2025-10-17 08:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f4c62df9092b'
down_revision = 'c515dfe9b65b'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'system_architecture_templates',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=160), nullable=False),
        sa.Column('slug', sa.String(length=180), nullable=False, unique=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(length=80), nullable=True),
        sa.Column('thumbnail_path', sa.String(length=500), nullable=True),
        sa.Column('layout_json', sa.Text(), nullable=False),
        sa.Column('is_shared', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_by', sa.String(length=120), nullable=True),
        sa.Column('updated_by', sa.String(length=120), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )

    op.create_index(
        'idx_system_architecture_templates_category',
        'system_architecture_templates',
        ['category'],
        unique=False,
    )

    op.create_table(
        'system_architecture_versions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('report_id', sa.String(length=36), sa.ForeignKey('reports.id'), nullable=False),
        sa.Column('version_label', sa.String(length=40), nullable=True),
        sa.Column('note', sa.String(length=255), nullable=True),
        sa.Column('checksum', sa.String(length=64), nullable=True),
        sa.Column('layout_json', sa.Text(), nullable=False),
        sa.Column('created_by', sa.String(length=120), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )

    op.create_index(
        'idx_system_architecture_versions_report',
        'system_architecture_versions',
        ['report_id', 'created_at'],
        unique=False,
    )


def downgrade():
    op.drop_index('idx_system_architecture_versions_report', table_name='system_architecture_versions')
    op.drop_table('system_architecture_versions')
    op.drop_index('idx_system_architecture_templates_category', table_name='system_architecture_templates')
    op.drop_table('system_architecture_templates')

