import json
import os
from datetime import datetime
from typing import Optional

DATA_FILE = "videos.json"


class VideoManager:
    """
    Menyimpan dan mengelola daftar video dalam file JSON.
    Cocok untuk Railway/Render (tanpa database eksternal).
    
    Struktur data tiap video:
    {
        "id": 1,
        "title": "Judul Video",
        "file_id": "BAADAgAD...",   # Telegram file_id (prioritas utama)
        "url": "https://...",        # URL mp4 (alternatif jika tidak ada file_id)
        "uploaded_at": "06/05 14:00",
        "broadcasted": false          # sudah pernah di-broadcast ke channel?
    }
    """

    def __init__(self):
        self.data_file = DATA_FILE
        self._ensure_file()

    # ─────────────────────────────────────────────
    #  Internal helpers
    # ─────────────────────────────────────────────

    def _ensure_file(self):
        if not os.path.exists(self.data_file):
            self._save({"videos": [], "next_id": 1})

    def _load(self) -> dict:
        with open(self.data_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save(self, data: dict):
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    # ─────────────────────────────────────────────
    #  CRUD
    # ─────────────────────────────────────────────

    def add_video(
        self,
        title: str,
        file_id: Optional[str] = None,
        url: Optional[str] = None
    ) -> dict:
        """Tambah video baru. Harus ada file_id ATAU url."""
        if not file_id and not url:
            raise ValueError("Harus menyertakan file_id atau url.")

        data = self._load()
        video = {
            "id":          data["next_id"],
            "title":       title,
            "file_id":     file_id,
            "url":         url,
            "uploaded_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "broadcasted": False
        }
        data["videos"].append(video)
        data["next_id"] += 1
        self._save(data)
        return video

    def get_latest_video(self) -> Optional[dict]:
        """Ambil video paling baru (ID tertinggi)."""
        videos = self.get_all_videos()
        return videos[-1] if videos else None

    def get_next_scheduled_video(self) -> Optional[dict]:
        """
        Ambil video berikutnya yang belum di-broadcast.
        Kalau semua sudah di-broadcast, ambil yang paling baru.
        """
        videos = self.get_all_videos()
        not_yet = [v for v in videos if not v.get("broadcasted")]
        if not_yet:
            return not_yet[0]
        # fallback: video terbaru
        return videos[-1] if videos else None

    def get_video_by_id(self, video_id: int) -> Optional[dict]:
        data = self._load()
        for v in data["videos"]:
            if v["id"] == video_id:
                return v
        return None

    def get_all_videos(self) -> list:
        return self._load()["videos"]

    def count_videos(self) -> int:
        return len(self.get_all_videos())

    def mark_as_broadcasted(self, video_id: int):
        data = self._load()
        for v in data["videos"]:
            if v["id"] == video_id:
                v["broadcasted"] = True
                break
        self._save(data)

    def delete_video(self, video_id: int) -> bool:
        data = self._load()
        original_len = len(data["videos"])
        data["videos"] = [v for v in data["videos"] if v["id"] != video_id]
        if len(data["videos"]) < original_len:
            self._save(data)
            return True
        return False
