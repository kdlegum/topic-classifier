"""
Migration: add new columns to specification table and create userspecselection table.
Safe to run multiple times (uses try/except for each ALTER).
Works with both SQLite and PostgreSQL via SQLAlchemy.

Run from Backend/ directory:  python migrate_add_spec_fields.py
"""

from sqlalchemy import text
from database import engine


def migrate():
    with engine.connect() as conn:
        # Add new columns to specification
        alterations = [
            "ALTER TABLE specification ADD COLUMN creator_id VARCHAR",
            "ALTER TABLE specification ADD COLUMN creator_is_guest BOOLEAN DEFAULT FALSE",
            "ALTER TABLE specification ADD COLUMN is_reviewed BOOLEAN DEFAULT FALSE",
            "ALTER TABLE specification ADD COLUMN description VARCHAR",
            "ALTER TABLE specification ADD COLUMN created_at TIMESTAMP",
        ]

        for sql in alterations:
            try:
                conn.execute(text(sql))
                conn.commit()
                print(f"OK: {sql}")
            except Exception as e:
                conn.rollback()
                print(f"SKIP: {sql}  ({e})")

        # Mark existing seeded specs as reviewed
        result = conn.execute(text(
            "UPDATE specification SET is_reviewed = TRUE WHERE creator_id IS NULL"
        ))
        conn.commit()
        print(f"Marked {result.rowcount} seeded specs as is_reviewed=TRUE")

        # Create UserSpecSelection table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS userspecselection (
                id SERIAL PRIMARY KEY,
                user_id VARCHAR NOT NULL,
                is_guest BOOLEAN DEFAULT TRUE,
                spec_code VARCHAR NOT NULL,
                added_at TIMESTAMP
            )
        """))
        conn.commit()
        print("Ensured userspecselection table exists")

        # Add indexes if not present
        for idx_sql in [
            "CREATE INDEX IF NOT EXISTS ix_userspecselection_user_id ON userspecselection(user_id)",
            "CREATE INDEX IF NOT EXISTS ix_userspecselection_spec_code ON userspecselection(spec_code)",
        ]:
            try:
                conn.execute(text(idx_sql))
                conn.commit()
            except Exception:
                conn.rollback()

    print("Migration complete.")


if __name__ == "__main__":
    migrate()
