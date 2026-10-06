"""init_schema must enable RLS on every table (Supabase PostgREST exposure)."""

from unittest.mock import MagicMock, patch

import pytest

from services.api import db
from services.api.rag import store


@pytest.mark.parametrize("module", [db, store])
def test_init_schema_enables_rls_on_every_table(module: object) -> None:
    engine = MagicMock()
    conn = engine.begin.return_value.__enter__.return_value
    with (
        patch.object(module, "get_engine", return_value=engine),
        patch.object(module.Base.metadata, "create_all"),  # type: ignore[attr-defined]
    ):
        module.init_schema()  # type: ignore[attr-defined]
    sql = [str(c.args[0]) for c in conn.execute.call_args_list]
    for table in module.Base.metadata.sorted_tables:  # type: ignore[attr-defined]
        assert f'ALTER TABLE "{table.name}" ENABLE ROW LEVEL SECURITY' in sql
