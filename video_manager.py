import os
import psycopg2
import psycopg2.extras
from datetime import datetime
import pytz

WIB = pytz.timezone('Asia/Jakarta')
DATABASE_URL = os.getenv("DATABASE_URL")


class VideoManager:
    def __init__(self):
        self._init_db()

    def _connect(self):
        return psycopg2.connect(DATABASE_URL, sslmode='require')

    def _init_db(self):
        with self._connect() as conn:
            with conn.cursor() as cur:
                # Tabel video individual
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS videos (
                        id SERIAL PRIMARY KEY,
                        title TEXT NOT NULL,
                        file_id TEXT,
                        url TEXT,
                        thumbnail_id TEXT,
                        uploaded_at TEXT NOT NULL,
                        broadcasted BOOLEAN DEFAULT FALSE
                    )
                """)
                # Tabel batch — kelompok video
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS batches (
                        id SERIAL PRIMARY KEY,
                        title TEXT NOT NULL,
                        thumbnail_id TEXT,
                        created_at TEXT NOT NULL,
                        broadcasted BOOLEAN DEFAULT FALSE
                    )
                """)
                # Tabel relasi batch <-> video
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS batch_videos (
                        batch_id INTEGER REFERENCES batches(id) ON DELETE CASCADE,
                        video_id INTEGER REFERENCES videos(id) ON DELETE CASCADE,
                        sort_order INTEGER DEFAULT 0,
                        PRIMARY KEY (batch_id, video_id)
                    )
                """)
                # Tabel pending videos (video yang belum dibatch)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS pending_videos (
                        id SERIAL PRIMARY KEY,
                        file_id TEXT,
                        url TEXT,
                        received_at TEXT NOT NULL
                    )
                """)
            conn.commit()

    # ─── PENDING VIDEOS ───────────────────────────────────────

    def add_pending_video(self, file_id=None, url=None) -> dict:
        """Simpan video yang baru dikirim ke pending, belum masuk batch."""
        received_at = datetime.now(WIB).strftime("%d/%m/%Y %H:%M")
        with self._connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "INSERT INTO pending_videos (file_id, url, received_at) VALUES (%s, %s, %s) RETURNING *",
                    (file_id, url, received_at)
                )
                row = dict(cur.fetchone())
            conn.commit()
        return row

    def get_pending_videos(self) -> list:
        """Ambil semua video pending yang belum dibatch."""
        with self._connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM pending_videos ORDER BY id ASC")
                rows = cur.fetchall()
        return [dict(r) for r in rows]

    def clear_pending_videos(self):
        """Hapus semua pending videos setelah dibatch."""
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM pending_videos")
            conn.commit()

    def count_pending_videos(self) -> int:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM pending_videos")
                count = cur.fetchone()[0]
        return count

    # ─── BATCH ────────────────────────────────────────────────

    def create_batch(self, title: str, thumbnail_id=None) -> dict:
        """Buat batch dari semua pending videos."""
        pending = self.get_pending_videos()
        if not pending:
            raise ValueError("Tidak ada video pending.")

        created_at = datetime.now(WIB).strftime("%d/%m/%Y %H:%M")
        with self._connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Buat batch
                cur.execute(
                    "INSERT INTO batches (title, thumbnail_id, created_at, broadcasted) VALUES (%s, %s, %s, FALSE) RETURNING *",
                    (title, thumbnail_id, created_at)
                )
                batch = dict(cur.fetchone())
                batch_id = batch["id"]

                # Pindahkan pending ke videos dan hubungkan ke batch
                for i, p in enumerate(pending):
                    cur.execute(
                        "INSERT INTO videos (title, file_id, url, uploaded_at, broadcasted) VALUES (%s, %s, %s, %s, FALSE) RETURNING id",
                        (f"{title} #{i+1}", p["file_id"], p["url"], created_at)
                    )
                    video_id = cur.fetchone()["id"]
                    cur.execute(
                        "INSERT INTO batch_videos (batch_id, video_id, sort_order) VALUES (%s, %s, %s)",
                        (batch_id, video_id, i)
                    )

                # Hapus pending
                cur.execute("DELETE FROM pending_videos")
            conn.commit()
        return batch

    def set_batch_thumbnail(self, batch_id: int, thumbnail_id: str) -> bool:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE batches SET thumbnail_id = %s WHERE id = %s", (thumbnail_id, batch_id))
                updated = cur.rowcount
            conn.commit()
        return updated > 0

    def get_next_scheduled_batches(self, count: int = 1) -> list:
        """Ambil batch yang belum dibroadcast."""
        count = max(1, min(count, 10))
        with self._connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM batches WHERE broadcasted = FALSE ORDER BY id ASC LIMIT %s",
                    (count,)
                )
                batches = [dict(r) for r in cur.fetchall()]
        return batches

    def get_batch_videos(self, batch_id: int) -> list:
        """Ambil semua video dalam sebuah batch."""
        with self._connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    SELECT v.* FROM videos v
                    JOIN batch_videos bv ON v.id = bv.video_id
                    WHERE bv.batch_id = %s
                    ORDER BY bv.sort_order ASC
                """, (batch_id,))
                rows = cur.fetchall()
        return [dict(r) for r in rows]

    def get_all_batches(self) -> list:
        with self._connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM batches ORDER BY id DESC")
                rows = cur.fetchall()
        return [dict(r) for r in rows]

    def mark_batch_broadcasted(self, batch_id: int):
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE batches SET broadcasted = TRUE WHERE id = %s", (batch_id,))
            conn.commit()

    def delete_batch(self, batch_id: int) -> bool:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM batches WHERE id = %s", (batch_id,))
                deleted = cur.rowcount
            conn.commit()
        return deleted > 0

    def get_batch_by_id(self, batch_id: int):
        with self._connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM batches WHERE id = %s", (batch_id,))
                row = cur.fetchone()
        return dict(row) if row else None

    # ─── VIDEO INDIVIDUAL (untuk backward compat) ─────────────

    def get_video_by_id(self, video_id: int):
        with self._connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM videos WHERE id = %s", (video_id,))
                row = cur.fetchone()
        return dict(row) if row else None

    def get_all_videos(self) -> list:
        with self._connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM videos ORDER BY id ASC")
                rows = cur.fetchall()
        return [dict(r) for r in rows]

    def count_videos(self) -> int:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM videos")
                count = cur.fetchone()[0]
        return count

    # legacy support
    def get_latest_video(self):
        with self._connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM videos ORDER BY id DESC LIMIT 1")
                row = cur.fetchone()
        return dict(row) if row else None

    def get_next_scheduled_videos(self, count: int = 3) -> list:
        count = max(1, min(count, 10))
        with self._connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM videos WHERE broadcasted = FALSE ORDER BY id ASC LIMIT %s",
                    (count,)
                )
                rows = cur.fetchall()
        return [dict(r) for r in rows]

    def mark_as_broadcasted(self, video_id: int):
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE videos SET broadcasted = TRUE WHERE id = %s", (video_id,))
            conn.commit()

    def delete_video(self, video_id: int) -> bool:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM videos WHERE id = %s", (video_id,))
                deleted = cur.rowcount
            conn.commit()
        return deleted > 0
