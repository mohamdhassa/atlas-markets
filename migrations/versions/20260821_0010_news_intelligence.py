"""news intelligence
Revision ID: 20260821_0010
Revises: 20260821_0009
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision="20260821_0010"
down_revision="20260821_0009"
branch_labels=None
depends_on=None

def upgrade():
    op.create_table("news_articles",
        sa.Column("id",postgresql.UUID(as_uuid=True),primary_key=True),
        sa.Column("source",sa.String(96),nullable=False),
        sa.Column("external_id",sa.String(512),nullable=False,unique=True),
        sa.Column("title",sa.String(512),nullable=False),
        sa.Column("url",sa.Text(),nullable=False),
        sa.Column("summary",sa.Text(),nullable=False,server_default=""),
        sa.Column("symbols_csv",sa.Text(),nullable=False,server_default=""),
        sa.Column("sentiment_score",sa.Float(),nullable=False,server_default="0"),
        sa.Column("relevance_score",sa.Float(),nullable=False,server_default="0"),
        sa.Column("published_at",sa.DateTime(timezone=True),nullable=True),
        sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now()),
    )
    op.create_index("ix_news_articles_source","news_articles",["source"])
    op.create_index("ix_news_articles_external_id","news_articles",["external_id"],unique=True)
    op.create_index("ix_news_articles_published_at","news_articles",["published_at"])
    op.create_index("ix_news_articles_created_at","news_articles",["created_at"])

def downgrade():
    op.drop_table("news_articles")
