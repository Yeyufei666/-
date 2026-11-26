"""CampusEvent 数据访问层（SQLite）。

负责领域对象的持久化，封装所有 SQL 操作，业务层（services.py）不直接接触 SQL。
每个操作返回领域对象（dataclass）或基本类型。
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Optional

from .models import (
    Activity,
    EmailRecord,
    Message,
    PolicyType,
    Registration,
    RegistrationStatus,
    Student,
)


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


class Database:
    """SQLite 数据访问封装。"""

    def __init__(self, db_path: str = "campus_event.db"):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        cur = self._conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS student (
                student_id TEXT PRIMARY KEY,
                name       TEXT NOT NULL,
                grade      INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS activity (
                activity_id INTEGER PRIMARY KEY AUTOINCREMENT,
                title       TEXT NOT NULL,
                category    TEXT NOT NULL,
                start_at    TEXT NOT NULL,
                location    TEXT NOT NULL,
                capacity    INTEGER NOT NULL,
                policy_type TEXT NOT NULL,
                deleted     INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS registration (
                registration_id INTEGER PRIMARY KEY AUTOINCREMENT,
                activity_id     INTEGER NOT NULL,
                student_id      TEXT NOT NULL,
                status          TEXT NOT NULL,
                created_at      TEXT NOT NULL,
                updated_at      TEXT NOT NULL,
                FOREIGN KEY (activity_id) REFERENCES activity(activity_id),
                FOREIGN KEY (student_id) REFERENCES student(student_id)
            );
            CREATE TABLE IF NOT EXISTS message (
                message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                activity_id INTEGER NOT NULL,
                content    TEXT NOT NULL,
                created_at TEXT NOT NULL,
                is_read    INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (student_id) REFERENCES student(student_id)
            );
            CREATE TABLE IF NOT EXISTS email_record (
                email_id   INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                subject    TEXT NOT NULL,
                content    TEXT NOT NULL,
                status     TEXT NOT NULL,
                error      TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY (student_id) REFERENCES student(student_id)
            );
            """
        )
        self._conn.commit()
        self._migrate()

    def _migrate(self) -> None:
        """轻量 schema 迁移：为旧库补充新增列。"""
        cur = self._conn.cursor()
        cols = [r["name"] for r in cur.execute("PRAGMA table_info(student)").fetchall()]
        if "grade" not in cols:
            cur.execute("ALTER TABLE student ADD COLUMN grade INTEGER NOT NULL DEFAULT 1")
            self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # ---------- Student ----------
    def add_student(self, student_id: str, name: str, grade: int = 1) -> Student:
        self._conn.execute(
            "INSERT OR REPLACE INTO student (student_id, name, grade) VALUES (?, ?, ?)",
            (student_id, name, grade),
        )
        self._conn.commit()
        return Student(student_id=student_id, name=name, grade=grade)

    def get_student(self, student_id: str) -> Optional[Student]:
        row = self._conn.execute(
            "SELECT student_id, name, grade FROM student WHERE student_id = ?",
            (student_id,),
        ).fetchone()
        return (
            Student(student_id=row["student_id"], name=row["name"], grade=row["grade"])
            if row
            else None
        )

    # ---------- Activity ----------
    def add_activity(self, a: Activity) -> Activity:
        cur = self._conn.execute(
            "INSERT INTO activity (title, category, start_at, location, capacity, policy_type) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (a.title, a.category, a.start_at.isoformat(), a.location, a.capacity, a.policy_type.value),
        )
        self._conn.commit()
        a.activity_id = cur.lastrowid
        return a

    def get_activity(self, activity_id: int) -> Optional[Activity]:
        row = self._conn.execute(
            "SELECT * FROM activity WHERE activity_id = ? AND deleted = 0",
            (activity_id,),
        ).fetchone()
        return self._row_to_activity(row) if row else None

    def list_activities(self, title_filter: str = "") -> list[Activity]:
        if title_filter:
            rows = self._conn.execute(
                "SELECT * FROM activity WHERE deleted = 0 AND title LIKE ? ORDER BY activity_id",
                (f"%{title_filter}%",),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM activity WHERE deleted = 0 ORDER BY activity_id"
            ).fetchall()
        return [self._row_to_activity(r) for r in rows]

    def update_activity(self, a: Activity) -> None:
        self._conn.execute(
            "UPDATE activity SET title=?, category=?, start_at=?, location=?, capacity=?, policy_type=? "
            "WHERE activity_id=?",
            (a.title, a.category, a.start_at.isoformat(), a.location, a.capacity,
             a.policy_type.value, a.activity_id),
        )
        self._conn.commit()

    def soft_delete_activity(self, activity_id: int) -> None:
        # 采用软删除，保留报名历史记录（B.2 规则7 的可选方案之一）
        self._conn.execute(
            "UPDATE activity SET deleted = 1 WHERE activity_id = ?", (activity_id,)
        )
        self._conn.commit()

    @staticmethod
    def _row_to_activity(row: sqlite3.Row) -> Activity:
        return Activity(
            activity_id=row["activity_id"],
            title=row["title"],
            category=row["category"],
            start_at=_parse_dt(row["start_at"]),
            location=row["location"],
            capacity=row["capacity"],
            policy_type=PolicyType(row["policy_type"]),
        )

    # ---------- Registration ----------
    def add_registration(self, r: Registration) -> Registration:
        cur = self._conn.execute(
            "INSERT INTO registration (activity_id, student_id, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (r.activity_id, r.student_id, r.status.value, r.created_at.isoformat(), r.updated_at.isoformat()),
        )
        self._conn.commit()
        r.registration_id = cur.lastrowid
        return r

    def get_registration(self, registration_id: int) -> Optional[Registration]:
        row = self._conn.execute(
            "SELECT * FROM registration WHERE registration_id = ?", (registration_id,)
        ).fetchone()
        return self._row_to_registration(row) if row else None

    def update_registration_status(self, registration_id: int, status: RegistrationStatus) -> None:
        self._conn.execute(
            "UPDATE registration SET status = ?, updated_at = ? WHERE registration_id = ?",
            (status.value, datetime.now().isoformat(), registration_id),
        )
        self._conn.commit()

    def find_active_registration(self, activity_id: int, student_id: str) -> Optional[Registration]:
        """查找该学生在该活动下的有效报名（待审核/已通过）。"""
        row = self._conn.execute(
            "SELECT * FROM registration WHERE activity_id = ? AND student_id = ? "
            "AND status IN ('pending', 'approved')",
            (activity_id, student_id),
        ).fetchone()
        return self._row_to_registration(row) if row else None

    def list_registrations(self, activity_id: int) -> list[Registration]:
        rows = self._conn.execute(
            "SELECT * FROM registration WHERE activity_id = ? ORDER BY registration_id",
            (activity_id,),
        ).fetchall()
        return [self._row_to_registration(r) for r in rows]

    def count_status(self, activity_id: int, status: RegistrationStatus) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) AS c FROM registration WHERE activity_id = ? AND status = ?",
            (activity_id, status.value),
        ).fetchone()
        return row["c"]

    @staticmethod
    def _row_to_registration(row: sqlite3.Row) -> Registration:
        return Registration(
            registration_id=row["registration_id"],
            activity_id=row["activity_id"],
            student_id=row["student_id"],
            status=RegistrationStatus(row["status"]),
            created_at=_parse_dt(row["created_at"]),
            updated_at=_parse_dt(row["updated_at"]),
        )

    # ---------- Message ----------
    def add_message(self, m: Message) -> Message:
        cur = self._conn.execute(
            "INSERT INTO message (student_id, activity_id, content, created_at, is_read) "
            "VALUES (?, ?, ?, ?, ?)",
            (m.student_id, m.activity_id, m.content, m.created_at.isoformat(), int(m.is_read)),
        )
        self._conn.commit()
        m.message_id = cur.lastrowid
        return m

    def list_messages(self, student_id: str) -> list[Message]:
        rows = self._conn.execute(
            "SELECT * FROM message WHERE student_id = ? ORDER BY message_id", (student_id,)
        ).fetchall()
        return [self._row_to_message(r) for r in rows]

    @staticmethod
    def _row_to_message(row: sqlite3.Row) -> Message:
        return Message(
            message_id=row["message_id"],
            student_id=row["student_id"],
            activity_id=row["activity_id"],
            content=row["content"],
            created_at=_parse_dt(row["created_at"]),
            is_read=bool(row["is_read"]),
        )

    # ---------- EmailRecord (CR-02) ----------
    def add_email_record(self, e: EmailRecord) -> EmailRecord:
        cur = self._conn.execute(
            "INSERT INTO email_record (student_id, subject, content, status, error, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (e.student_id, e.subject, e.content, e.status, e.error, e.created_at.isoformat()),
        )
        self._conn.commit()
        e.email_id = cur.lastrowid
        return e

    def list_email_records(self, student_id: str) -> list[EmailRecord]:
        rows = self._conn.execute(
            "SELECT * FROM email_record WHERE student_id = ? ORDER BY email_id", (student_id,)
        ).fetchall()
        return [self._row_to_email_record(r) for r in rows]

    @staticmethod
    def _row_to_email_record(row: sqlite3.Row) -> EmailRecord:
        return EmailRecord(
            email_id=row["email_id"],
            student_id=row["student_id"],
            subject=row["subject"],
            content=row["content"],
            status=row["status"],
            error=row["error"],
            created_at=_parse_dt(row["created_at"]),
        )
