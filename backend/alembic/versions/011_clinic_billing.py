"""Financial-year billing columns for a single clinic."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add(table: str, name: str, column: sa.Column) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return
    if name in {item["name"] for item in inspector.get_columns(table)}:
        return
    op.add_column(table, column)


def upgrade() -> None:
    _add("bill", "place_of_supply", sa.Column("place_of_supply", sa.String(10)))
    _add("bill", "round_off", sa.Column("round_off", sa.Float(), server_default="0"))
    _add("bill", "advance_applied", sa.Column("advance_applied", sa.Float(), server_default="0"))
    _add("bill", "credit_note_number", sa.Column("credit_note_number", sa.String(30)))
    _add("bill", "debit_note_number", sa.Column("debit_note_number", sa.String(30)))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "bill" not in inspector.get_table_names():
        return
    columns = {item["name"] for item in inspector.get_columns("bill")}
    for name in ("debit_note_number", "credit_note_number", "advance_applied", "round_off", "place_of_supply"):
        if name in columns:
            op.drop_column("bill", name)
