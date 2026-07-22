"""Add game session timing and chess clock columns."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002_game_session_clock"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "games",
        sa.Column("time_limit_seconds", sa.Integer(), nullable=False, server_default="600"),
    )
    op.add_column(
        "games",
        sa.Column("user_time_remaining_ms", sa.BigInteger(), nullable=False, server_default="600000"),
    )
    op.add_column(
        "games",
        sa.Column(
            "opponent_time_remaining_ms",
            sa.BigInteger(),
            nullable=False,
            server_default="600000",
        ),
    )
    op.add_column(
        "games",
        sa.Column("clock_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "games",
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "games",
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "games",
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Existing rows were created as in_progress; mark idle ones as waiting when never started.
    op.execute(
        """
        UPDATE games
        SET status = 'waiting',
            last_activity_at = created_at
        WHERE status = 'in_progress'
          AND move_count = 0
          AND started_at IS NULL
        """
    )


def downgrade() -> None:
    op.drop_column("games", "last_activity_at")
    op.drop_column("games", "ended_at")
    op.drop_column("games", "started_at")
    op.drop_column("games", "clock_started_at")
    op.drop_column("games", "opponent_time_remaining_ms")
    op.drop_column("games", "user_time_remaining_ms")
    op.drop_column("games", "time_limit_seconds")
