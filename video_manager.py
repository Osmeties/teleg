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
        """Buat tabel jika belum ada."""
        with self._connect() as conn:
            with conn.cursor() as cur:
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
            conn.commit()

    def add_video(self, title: str, file_id=None, url=None) -> dict:
        if not file_id and not url:
            raise ValueError("Harus menyertakan file_id atau url.")
        uploaded_at = datetime.now(WIB).strftime("%d/%m/%Y %H:%M")
        with self._connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """INSERT INTO videos (title, file_id, url, thumbnail_id, uploaded_at, broadcasted)
                       VALUES (%s, %s, %s, NULL, %s, FALSE) RETURNING *""",
                    (title, file_id, url, uploaded_at)
                )
                video = dict(cur.fetchone())
            conn.commit()
        return video

    def set_thumbnail(self, video_id: int, thumbnail_id: str) -> bool:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE videos SET thumbnail_id = %s WHERE id = %s",
                    (thumbnail_id, video_id)
                )
                updated = cur.rowcount
            conn.commit()
        return updated > 0

    def get_latest_video(self):
        with self._connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM videos ORDER BY id DESC LIMIT 1")
                row = cur.fetchone()
        return dict(row) if row else None

    def get_next_scheduled_video(self):
        with self._connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM videos WHERE broadcasted = FALSE ORDER BY id ASC LIMIT 1")
                row = cur.fetchone()
                if not row:
                    cur.execute("SELECT * FROM videos ORDER BY id DESC LIMIT 1")
                    row = cur.fetchone()
        return dict(row) if row else None

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
