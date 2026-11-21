"""Registration status so a cancelled chart keeps its number."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "patient" not in inspector.get_table_names():
        return
    columns = {item["name"] for item in inspector.get_columns("patient")}
    if "registration_status" not in columns:
        op.add_column(
            "patient",
            sa.Column("registration_status", sa.String(20), nullable=True, server_default="active"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "patient" not in inspector.get_table_names():
        return
    columns = {item["name"] for item in inspector.get_columns("patient")}
    if "registration_status" in columns:
        op.drop_column("patient", "registration_status")
