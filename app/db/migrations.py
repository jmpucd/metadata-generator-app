"""
app/db/migrations.py
Lightweight migration helpers — no Alembic required for an MVP.
Run via: python -m app.cli db-check
"""
from __future__ import annotations

from sqlalchemy import inspect, text

from app.db.schema import Base, get_engine


def check_and_migrate(verbose: bool = True) -> list[str]:
    """
    Inspect the live DB and add any missing columns that exist in the ORM models.
    Returns a list of actions taken.
    """
    engine = get_engine()
    inspector = inspect(engine)
    actions: list[str] = []

    for table in Base.metadata.sorted_tables:
        table_name = table.name
        if not inspector.has_table(table_name):
            if verbose:
                print(f"  ✚ Creating missing table: {table_name}")
            table.create(engine)
            actions.append(f"created_table:{table_name}")
            continue

        existing_cols = {c["name"] for c in inspector.get_columns(table_name)}
        for col in table.columns:
            if col.name not in existing_cols:
                # Build a simple ALTER TABLE statement
                col_type = col.type.compile(engine.dialect)
                nullable = "" if col.nullable else " NOT NULL"
                default = ""
                if col.default is not None and col.default.is_scalar:
                    val = col.default.arg
                    if isinstance(val, str):
                        val = f"'{val}'"
                    default = f" DEFAULT {val}"
                stmt = f"ALTER TABLE {table_name} ADD COLUMN {col.name} {col_type}{default}{nullable}"
                with engine.connect() as conn:
                    conn.execute(text(stmt))
                    conn.commit()
                msg = f"added_column:{table_name}.{col.name}"
                actions.append(msg)
                if verbose:
                    print(f"  ✚ {msg}")

    if not actions and verbose:
        print("  ✔ Schema is up to date — no changes needed.")

    return actions
