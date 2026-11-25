"""Add version number to each generated question.

The nullable add, backfill, and not-null alteration are separate operations
because MySQL DDL may commit implicitly. Inspect database state manually if
this migration fails partway through before retrying or downgrading.
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_question_quiz_version"
down_revision = "0001_existing_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("questions", sa.Column("quiz_version", sa.Integer(), nullable=True))
    op.execute("UPDATE questions SET quiz_version = 1 WHERE quiz_version IS NULL")
    op.alter_column(
        "questions",
        "quiz_version",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.create_index(
        "ix_questions_video_id_quiz_version",
        "questions",
        ["video_id", "quiz_version"],
        unique=False,
    )


def downgrade() -> None:
    # This removes version metadata only; it preserves question rows and IDs.
    op.drop_index("ix_questions_video_id_quiz_version", table_name="questions")
    op.drop_column("questions", "quiz_version")
