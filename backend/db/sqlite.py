"""SQLite database operations for Finalyzer."""

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from uuid import UUID

from backend.config import settings
from backend.models import (
    Transaction,
    TransactionCategory,
    TransactionSource,
    UploadedFile,
)

# SQL schema
SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    source_file_hash TEXT NOT NULL,
    transaction_hash TEXT NOT NULL UNIQUE,
    date TEXT NOT NULL,
    description TEXT NOT NULL,
    amount REAL NOT NULL,
    category TEXT,
    raw_category TEXT,
    tags TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(date);
CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions(category);
CREATE INDEX IF NOT EXISTS idx_transactions_source ON transactions(source);
CREATE INDEX IF NOT EXISTS idx_transactions_hash ON transactions(transaction_hash);

CREATE TABLE IF NOT EXISTS uploaded_files (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    file_hash TEXT NOT NULL UNIQUE,
    source TEXT NOT NULL,
    transaction_count INTEGER NOT NULL,
    uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_uploaded_files_hash ON uploaded_files(file_hash);
"""


class Database:
    """SQLite database manager."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or settings.db_path
        settings.ensure_directories()
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the database schema."""
        with self._get_connection() as conn:
            conn.executescript(SCHEMA)
            # Migration: add tags column if it doesn't exist
            try:
                conn.execute("ALTER TABLE transactions ADD COLUMN tags TEXT")
                conn.commit()
            except sqlite3.OperationalError:
                # Column already exists
                pass
            conn.commit()

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get a database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def file_exists(self, file_hash: str) -> bool:
        """Check if a file with this hash has already been uploaded."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT 1 FROM uploaded_files WHERE file_hash = ?", (file_hash,))
            return cursor.fetchone() is not None

    def transaction_exists(self, transaction_hash: str) -> bool:
        """Check if a transaction with this hash already exists."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT 1 FROM transactions WHERE transaction_hash = ?", (transaction_hash,))
            return cursor.fetchone() is not None

    def add_uploaded_file(self, uploaded_file: UploadedFile) -> None:
        """Record an uploaded file."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO uploaded_files
                (id, filename, file_hash, source, transaction_count, uploaded_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uploaded_file.id),
                    uploaded_file.filename,
                    uploaded_file.file_hash,
                    uploaded_file.source.value,
                    uploaded_file.transaction_count,
                    uploaded_file.uploaded_at,
                ),
            )
            conn.commit()

    def add_transaction(self, transaction: Transaction) -> bool:
        """Add a transaction. Returns True if added, False if duplicate."""
        with self._get_connection() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO transactions (id, source, source_file_hash,
                    transaction_hash, date, description, amount, category,
                    raw_category, tags) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(transaction.id),
                        transaction.source.value,
                        transaction.source_file_hash,
                        transaction.transaction_hash,
                        transaction.date.isoformat(),
                        transaction.description,
                        transaction.amount,
                        transaction.category.value if transaction.category else None,
                        transaction.raw_category,
                        ",".join(transaction.tags) if transaction.tags else None,
                    ),
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                # Duplicate transaction_hash
                return False

    def add_transactions_batch(self, transactions: list[Transaction]) -> tuple[int, int]:
        """Add multiple transactions. Returns (added_count, skipped_count)."""
        added = 0
        skipped = 0
        for txn in transactions:
            if self.add_transaction(txn):
                added += 1
            else:
                skipped += 1
        return added, skipped

    def update_transaction_category(self, transaction_id: UUID, category: TransactionCategory) -> None:
        """Update a transaction's category."""
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE transactions SET category = ? WHERE id = ?",
                (category.value, str(transaction_id)),
            )
            conn.commit()

    def update_transaction_tags(self, transaction_id: UUID, tags: list[str]) -> None:
        """Update a transaction's tags."""
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE transactions SET tags = ? WHERE id = ?",
                (",".join(tags) if tags else None, str(transaction_id)),
            )
            conn.commit()

    def get_transactions_without_tags(self, limit: int = 100) -> list[Transaction]:
        """Get transactions that haven't been tagged yet."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, source, source_file_hash, transaction_hash, date,
                       description, amount, category, raw_category, tags
                FROM transactions
                WHERE tags IS NULL OR tags = ''
                LIMIT ?
                """,
                (limit,),
            )
            return [self._row_to_transaction(row) for row in cursor.fetchall()]

    def search_by_tags(self, tags: list[str], limit: int = 100) -> list[Transaction]:
        """Search transactions by tags."""
        if not tags:
            return []
        # Build OR conditions for each tag
        conditions = " OR ".join(["tags LIKE ?" for _ in tags])
        params = [f"%{tag}%" for tag in tags]
        params.append(limit)

        with self._get_connection() as conn:
            cursor = conn.execute(
                f"""
                SELECT id, source, source_file_hash, transaction_hash, date,
                       description, amount, category, raw_category, tags
                FROM transactions
                WHERE {conditions}
                ORDER BY date DESC
                LIMIT ?
                """,
                params,
            )
            return [self._row_to_transaction(row) for row in cursor.fetchall()]

    def get_transactions_without_category(self, limit: int = 100) -> list[Transaction]:
        """Get transactions that haven't been categorized yet."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, source, source_file_hash, transaction_hash, date,
                       description, amount, category, raw_category, tags
                FROM transactions
                WHERE category IS NULL
                LIMIT ?
                """,
                (limit,),
            )
            return [self._row_to_transaction(row) for row in cursor.fetchall()]

    def get_all_transactions(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        category: TransactionCategory | None = None,
        source: TransactionSource | None = None,
        limit: int = 1000,
    ) -> list[Transaction]:
        """Get transactions with optional filters."""
        query = """
            SELECT id, source, source_file_hash, transaction_hash, date,
                   description, amount, category, raw_category, tags
            FROM transactions WHERE 1=1
        """
        params: list = []

        if start_date:
            query += " AND date >= ?"
            params.append(start_date.isoformat())
        if end_date:
            query += " AND date <= ?"
            params.append(end_date.isoformat())
        if category:
            query += " AND category = ?"
            params.append(category.value)
        if source:
            query += " AND source = ?"
            params.append(source.value)

        query += " ORDER BY date DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            return [self._row_to_transaction(row) for row in cursor.fetchall()]

    def search_transactions(self, search_term: str, limit: int = 100) -> list[Transaction]:
        """Search transactions by description or tags."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, source, source_file_hash, transaction_hash, date,
                       description, amount, category, raw_category, tags
                FROM transactions
                WHERE description LIKE ? OR tags LIKE ?
                ORDER BY date DESC
                LIMIT ?
                """,
                (f"%{search_term}%", f"%{search_term}%", limit),
            )
            return [self._row_to_transaction(row) for row in cursor.fetchall()]

    def get_transaction_by_id(self, transaction_id: UUID) -> Transaction | None:
        """Get a single transaction by ID."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, source, source_file_hash, transaction_hash, date,
                       description, amount, category, raw_category, tags
                FROM transactions WHERE id = ?
                """,
                (str(transaction_id),),
            )
            row = cursor.fetchone()
            return self._row_to_transaction(row) if row else None

    def get_transactions_by_ids(self, transaction_ids: list[str]) -> list[Transaction]:
        """Get multiple transactions by their IDs."""
        if not transaction_ids:
            return []
        placeholders = ",".join("?" * len(transaction_ids))
        with self._get_connection() as conn:
            cursor = conn.execute(
                f"""
                SELECT id, source, source_file_hash, transaction_hash, date,
                       description, amount, category, raw_category, tags
                FROM transactions WHERE id IN ({placeholders})
                ORDER BY date DESC
                """,
                transaction_ids,
            )
            return [self._row_to_transaction(row) for row in cursor.fetchall()]

    def get_spending_summary(self, start_date: date | None = None, end_date: date | None = None) -> dict[str, float]:
        """Get spending totals by category."""
        query = """
            SELECT category, SUM(amount) as total
            FROM transactions
            WHERE amount < 0
        """
        params: list = []

        if start_date:
            query += " AND date >= ?"
            params.append(start_date.isoformat())
        if end_date:
            query += " AND date <= ?"
            params.append(end_date.isoformat())

        query += " GROUP BY category"

        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            return {row["category"] or "Uncategorized": abs(row["total"]) for row in cursor.fetchall()}

    def get_uploaded_files(self) -> list[UploadedFile]:
        """Get all uploaded files."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, filename, file_hash, source, transaction_count, uploaded_at
                FROM uploaded_files ORDER BY uploaded_at DESC
                """
            )
            return [
                UploadedFile(
                    id=UUID(row["id"]),
                    filename=row["filename"],
                    file_hash=row["file_hash"],
                    source=TransactionSource(row["source"]),
                    transaction_count=row["transaction_count"],
                    uploaded_at=row["uploaded_at"],
                )
                for row in cursor.fetchall()
            ]

    def get_transaction_count(self) -> int:
        """Get total number of transactions."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) as count FROM transactions")
            return cursor.fetchone()["count"]

    def _row_to_transaction(self, row: sqlite3.Row) -> Transaction:
        """Convert a database row to a Transaction model."""
        tags_str = row["tags"] if "tags" in row.keys() else None
        return Transaction(
            id=UUID(row["id"]),
            source=TransactionSource(row["source"]),
            source_file_hash=row["source_file_hash"],
            transaction_hash=row["transaction_hash"],
            date=date.fromisoformat(row["date"]),
            description=row["description"],
            amount=row["amount"],
            category=TransactionCategory(row["category"]) if row["category"] else None,
            raw_category=row["raw_category"],
            tags=tags_str.split(",") if tags_str else [],
        )


# Global database instance
db = Database()
