"""Initial schema: users, games, game_moves."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE TYPE opponent_type AS ENUM ('machine', 'human')")
    op.execute("CREATE TYPE game_status AS ENUM ('waiting', 'in_progress', 'completed', 'abandoned')")
    op.execute("CREATE TYPE game_result AS ENUM ('white_wins', 'black_wins', 'draw', 'ongoing')")
    op.execute("CREATE TYPE player_side AS ENUM ('white', 'black')")

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_phone", "users", ["phone"], unique=True)

    opponent_type = postgresql.ENUM("machine", "human", name="opponent_type", create_type=False)
    game_status = postgresql.ENUM("waiting", "in_progress", "completed", "abandoned", name="game_status", create_type=False)
    game_result = postgresql.ENUM("white_wins", "black_wins", "draw", "ongoing", name="game_result", create_type=False)
    player_side = postgresql.ENUM("white", "black", name="player_side", create_type=False)

    op.create_table(
        "games",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("opponent_type", opponent_type, nullable=False, server_default="machine"),
        sa.Column("status", game_status, nullable=False, server_default="in_progress"),
        sa.Column("result", game_result, nullable=False, server_default="ongoing"),
        sa.Column("user_color", player_side, nullable=False, server_default="white"),
        sa.Column(
            "current_fen",
            sa.Text(),
            nullable=False,
            server_default="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        ),
        sa.Column("pgn", sa.Text(), nullable=True),
        sa.Column("move_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_games_user_id", "games", ["user_id"])

    op.create_table(
        "game_moves",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("game_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("games.id", ondelete="CASCADE"), nullable=False),
        sa.Column("move_number", sa.Integer(), nullable=False),
        sa.Column("move_san", sa.String(16), nullable=False),
        sa.Column("move_uci", sa.String(8), nullable=False),
        sa.Column("fen_after", sa.Text(), nullable=False),
        sa.Column("played_by", player_side, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_game_moves_game_id", "game_moves", ["game_id"])


def downgrade() -> None:
    op.drop_index("ix_game_moves_game_id", table_name="game_moves")
    op.drop_table("game_moves")
    op.drop_index("ix_games_user_id", table_name="games")
    op.drop_table("games")
    op.drop_index("ix_users_phone", table_name="users")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS player_side")
    op.execute("DROP TYPE IF EXISTS game_result")
    op.execute("DROP TYPE IF EXISTS game_status")
    op.execute("DROP TYPE IF EXISTS opponent_type")
