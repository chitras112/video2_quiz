"""Add persistent exam attempts and question response snapshots.

This revision follows 0002_question_quiz_version because attempts pin that
column's quiz version. All foreign-key columns use signed SQL INTEGER to
match the existing videos.id and questions.id columns.
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_exam_attempts_responses"
down_revision = "0002_question_quiz_version"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "exam_attempts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("video_id", sa.Integer(), nullable=False),
        sa.Column("quiz_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("total_questions", sa.Integer(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("percentage", sa.Integer(), nullable=True),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_exam_attempts_idempotency_key"),
    )
    op.create_index("ix_exam_attempts_id", "exam_attempts", ["id"], unique=False)
    op.create_index("ix_exam_attempts_video_id", "exam_attempts", ["video_id"], unique=False)
    op.create_index("ix_exam_attempts_status", "exam_attempts", ["status"], unique=False)
    op.create_index(
        "ix_exam_attempts_video_quiz_version",
        "exam_attempts",
        ["video_id", "quiz_version"],
        unique=False,
    )

    op.create_table(
        "exam_responses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("attempt_id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("selected_answer", sa.String(length=500), nullable=True),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("answered_at", sa.DateTime(), nullable=True),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("options_json", sa.Text(), nullable=False),
        sa.Column("correct_answer", sa.String(length=500), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["attempt_id"], ["exam_attempts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "attempt_id", "question_id", name="uq_exam_responses_attempt_question"
        ),
    )
    op.create_index("ix_exam_responses_id", "exam_responses", ["id"], unique=False)
    op.create_index(
        "ix_exam_responses_attempt_id", "exam_responses", ["attempt_id"], unique=False
    )
    op.create_index(
        "ix_exam_responses_question_id", "exam_responses", ["question_id"], unique=False
    )


def downgrade() -> None:
    # These are new tables only; drop dependents first. No existing table is touched.
    op.drop_table("exam_responses")
    op.drop_table("exam_attempts")
