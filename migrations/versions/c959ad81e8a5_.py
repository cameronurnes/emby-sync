"""empty message

Revision ID: c959ad81e8a5
Revises: 3b3070e17b44
Create Date: 2020-12-25 19:42:22.869893

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c959ad81e8a5'
down_revision = '3b3070e17b44'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('user',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('username', sa.String(length=128), nullable=True),
    sa.Column('access_key', sa.String(length=32), nullable=True),
    sa.Column('device_id', sa.String(length=24), nullable=True),
    sa.Column('emby_id', sa.String(length=32), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('device_id'),
    sa.UniqueConstraint('emby_id')
    )
    op.create_index(op.f('ix_user_username'), 'user', ['username'], unique=True)
    op.create_table('session',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('session_id', sa.String(length=32), nullable=True),
    sa.Column('timestamp', sa.DateTime(), nullable=True),
    sa.Column('user_id', sa.String(length=32), nullable=True),
    sa.Column('ticks', sa.BigInteger(), nullable=True),
    sa.Column('room', sa.String(length=128), nullable=True),
    sa.Column('syncing', sa.Boolean(), nullable=True),
    sa.Column('leader', sa.Boolean(), nullable=True),
    sa.Column('item_id', sa.Integer(), nullable=True),
    sa.Column('device_name', sa.String(length=128), nullable=True),
    sa.Column('client_name', sa.String(length=128), nullable=True),
    sa.Column('is_paused', sa.Boolean(), nullable=True),
    sa.Column('playing', sa.Boolean(), nullable=True),
    sa.Column('is_stale', sa.Boolean(), nullable=True),
    sa.Column('is_dead', sa.Boolean(), nullable=True),
    sa.Column('device_id', sa.String(length=32), nullable=True),
    sa.Column('ip_address', sa.String(length=32), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['user.emby_id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_session_session_id'), 'session', ['session_id'], unique=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_session_session_id'), table_name='session')
    op.drop_table('session')
    op.drop_index(op.f('ix_user_username'), table_name='user')
    op.drop_table('user')
    # ### end Alembic commands ###
