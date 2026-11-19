"""Abilita RLS su tutte le tabelle del schema public

Supabase segnala come esposte le tabelle pubbliche senza Row Level Security:
con la anon key chiunque potrebbe leggerle. La migrazione chiude anche i grant
verso i ruoli `anon`/`authenticated` e rimuove i privilegi di default, così le
tabelle create in futuro non nascono accessibili alla Data API.

Il backend accede con una connessione diretta come owner e non è toccato da RLS:
non vengono create policy, di proposito.

Revision ID: a7c3f1e59b24
Revises: 9c1f2e3d4a5b
Create Date: 2026-11-19 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7c3f1e59b24'
down_revision: Union[str, Sequence[str], None] = '9c1f2e3d4a5b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_ENABLE_RLS_SQL = """
    DO $$
    DECLARE t record;
    BEGIN
        FOR t IN
            SELECT c.relname
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND c.relkind = 'r'
        LOOP
            EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t.relname);
        END LOOP;
    END $$;
"""


def upgrade() -> None:
    if op.get_context().dialect.name != 'postgresql':
        return

    conn = op.get_bind()
    roles = {row[0] for row in conn.execute(sa.text('SELECT rolname FROM pg_roles'))}

    conn.execute(sa.text(_ENABLE_RLS_SQL))

    if {'anon', 'authenticated'} <= roles:
        conn.execute(sa.text(
            'REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon, authenticated'
        ))
        conn.execute(sa.text(
            'REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM anon, authenticated'
        ))
        conn.execute(sa.text(
            'ALTER DEFAULT PRIVILEGES IN SCHEMA public '
            'REVOKE ALL ON TABLES FROM anon, authenticated'
        ))
        conn.execute(sa.text(
            'ALTER DEFAULT PRIVILEGES IN SCHEMA public '
            'REVOKE ALL ON SEQUENCES FROM anon, authenticated'
        ))


def downgrade() -> None:
    # Volutamente no-op: riaprire le tabelle alla Data API non è un downgrade
    # sicuro. Se servisse una policy, va aggiunta esplicitamente.
    pass
