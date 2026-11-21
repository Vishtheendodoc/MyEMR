"""Appointment arrival channel for the doctor's day list."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "appointment" not in inspector.get_table_names():
        return
    columns = {item["name"] for item in inspector.get_columns("appointment")}
    if "channel" not in columns:
        op.add_column("appointment", sa.Column("channel", sa.String(20), nullable=True, server_default="in_clinic"))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "appointment" not in inspector.get_table_names():
        return
    columns = {item["name"] for item in inspector.get_columns("appointment")}
    if "channel" in columns:
        op.drop_column("appointment", "channel")
