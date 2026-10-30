"""notify live clients when products are deleted

Fires on any DELETE/TRUNCATE (API, psql, admin tools), so open catalog pages drop
removed products without a reload.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-30
"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

# NOTIFY payload is limited to 8000 bytes: big deletes ask clients to reload the list instead.
MAX_IDS_IN_EVENT = 500


def upgrade() -> None:
    op.execute(
        f"""
        CREATE FUNCTION notify_products_deleted() RETURNS trigger AS $$
        DECLARE
            ids bigint[];
        BEGIN
            SELECT array_agg(id) INTO ids FROM deleted_rows;
            IF ids IS NULL THEN
                RETURN NULL;
            END IF;
            IF array_length(ids, 1) > {MAX_IDS_IN_EVENT} THEN
                PERFORM pg_notify('products', '{{"type":"resync"}}');
            ELSE
                PERFORM pg_notify('products', json_build_object('type', 'deleted', 'ids', ids)::text);
            END IF;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER products_deleted
            AFTER DELETE ON products
            REFERENCING OLD TABLE AS deleted_rows
            FOR EACH STATEMENT EXECUTE FUNCTION notify_products_deleted()
        """
    )
    op.execute(
        """
        CREATE FUNCTION notify_products_truncated() RETURNS trigger AS $$
        BEGIN
            PERFORM pg_notify('products', '{"type":"resync"}');
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER products_truncated
            AFTER TRUNCATE ON products
            FOR EACH STATEMENT EXECUTE FUNCTION notify_products_truncated()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER products_truncated ON products")
    op.execute("DROP FUNCTION notify_products_truncated()")
    op.execute("DROP TRIGGER products_deleted ON products")
    op.execute("DROP FUNCTION notify_products_deleted()")
