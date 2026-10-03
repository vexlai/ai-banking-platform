"""SQLite unit of work: case + audit + idempotency + handoff commit atomically."""

import hashlib
import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from contracts.disputes import Case


class Rejected(ValueError):
    """Stable domain rejection; the adapter must not expose underlying records."""


class Conflict(Rejected):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def fingerprint(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


class CaseStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
        except FileExistsError:
            pass  # Existing store permissions belong to its operator.
        else:
            os.close(descriptor)
        with self.transaction() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS schema_version(version INTEGER NOT NULL);
                INSERT INTO schema_version SELECT 1 WHERE NOT EXISTS(SELECT 1 FROM schema_version);
                CREATE TABLE IF NOT EXISTS cases(
                    case_id TEXT PRIMARY KEY, customer_id TEXT NOT NULL,
                    version INTEGER NOT NULL, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS commands(
                    subject TEXT NOT NULL, customer_id TEXT NOT NULL, key TEXT NOT NULL,
                    fingerprint TEXT NOT NULL, result TEXT NOT NULL,
                    PRIMARY KEY(subject,customer_id,key));
                CREATE TABLE IF NOT EXISTS audit(
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_id TEXT NOT NULL REFERENCES cases(case_id),
                    version INTEGER NOT NULL, action TEXT NOT NULL, actor TEXT NOT NULL,
                    provider TEXT NOT NULL, from_state TEXT, to_state TEXT NOT NULL,
                    recorded_at TEXT NOT NULL, command_hash TEXT NOT NULL,
                    result_hash TEXT NOT NULL, UNIQUE(case_id,version));
                CREATE TABLE IF NOT EXISTS handoffs(
                    handoff_id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL UNIQUE REFERENCES cases(case_id),
                    body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS rejections(
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    operation TEXT NOT NULL, reason TEXT NOT NULL, recorded_at TEXT NOT NULL);
                CREATE TRIGGER IF NOT EXISTS rejection_no_update BEFORE UPDATE ON rejections
                    BEGIN SELECT RAISE(ABORT,'Rejections are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS rejection_no_delete BEFORE DELETE ON rejections
                    BEGIN SELECT RAISE(ABORT,'Rejections are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit
                    BEGIN SELECT RAISE(ABORT,'Audit is append-only'); END;
                CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit
                    BEGIN SELECT RAISE(ABORT,'Audit is append-only'); END;
            """)
            if db.execute("SELECT version FROM schema_version").fetchall() != [(1,)]:
                raise RuntimeError("Unsupported case store schema")

    @contextmanager
    def transaction(self):
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA synchronous=FULL")
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def load(db, case_id, customer_id):
        row = db.execute(
            "SELECT body FROM cases WHERE case_id=? AND customer_id=?",
            (case_id, customer_id),
        ).fetchone()
        if row is None:
            raise Rejected("CASE_NOT_ACCESSIBLE")
        return Case.model_validate_json(row[0])

    def record_rejection(self, operation, reason, now):
        # Separate transaction after a rejected command has rolled back. No credentials,
        # utterances, attacker-supplied IDs, or exception internals enter this log.
        with self.transaction() as db:
            db.execute(
                "INSERT INTO rejections(operation,reason,recorded_at) VALUES(?,?,?)",
                (operation, reason, now.isoformat()),
            )

    @staticmethod
    def replay(db, principal, key, digest):
        row = db.execute(
            "SELECT fingerprint,result FROM commands WHERE subject=? AND customer_id=? AND key=?",
            (
                canonical([principal.provider, principal.subject]),
                principal.customer_id,
                key,
            ),
        ).fetchone()
        if row:
            if row[0] != digest:
                raise Conflict("IDEMPOTENCY_KEY_REUSED")
            return Case.model_validate_json(row[1])
        return None

    @staticmethod
    def persist(db, previous, case, principal, action, key, digest, now, handoff=None):
        body = case.model_dump_json()
        if previous is None:
            db.execute(
                "INSERT INTO cases VALUES(?,?,?,?)",
                (case.case_id, case.customer_id, case.version, body),
            )
        else:
            changed = db.execute(
                "UPDATE cases SET version=?,body=? WHERE case_id=? AND version=?",
                (case.version, body, case.case_id, previous.version),
            ).rowcount
            if changed != 1:
                raise Conflict("STALE_VERSION")
        if handoff is not None:
            db.execute(
                "INSERT INTO handoffs VALUES(?,?,?)",
                (handoff.handoff_id, case.case_id, handoff.model_dump_json()),
            )
        db.execute(
            """INSERT INTO audit(case_id,version,action,actor,provider,from_state,to_state,
               recorded_at,command_hash,result_hash) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (
                case.case_id,
                case.version,
                action,
                principal.subject,
                principal.provider,
                previous.state.value if previous else None,
                case.state.value,
                now.isoformat(),
                digest,
                fingerprint(case.model_dump(mode="json")),
            ),
        )
        db.execute(
            "INSERT INTO commands VALUES(?,?,?,?,?)",
            (
                canonical([principal.provider, principal.subject]),
                principal.customer_id,
                key,
                digest,
                body,
            ),
        )
