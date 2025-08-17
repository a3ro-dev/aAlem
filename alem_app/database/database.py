
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from PyQt6.QtCore import QStandardPaths

from alem_app.utils.logging import logger


class Note:
    """Simple Note class"""

    def __init__(self, id=None, title="", content="", tags="", created_at=None, updated_at=None,
                 locked: bool = False, content_format: str = "html"):
        self.id = id
        self.title = title
        self.content = content
        self.tags = tags
        self.created_at = created_at or datetime.now().isoformat()
        self.updated_at = updated_at or datetime.now().isoformat()
        self.locked = locked
        self.content_format = content_format  # 'html' or 'markdown'

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'tags': self.tags,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'locked': self.locked,
            'content_format': self.content_format
        }

    @classmethod
    def from_dict(cls, data):
        return cls(**data)


class Database:
    """Enhanced SQLite database for notes with better error handling and features"""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            # Store database in user data directory
            data_dir = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation))
            data_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = data_dir / "alem_notes.db"
        else:
            self.db_path = Path(db_path)

        logger.info(f"Database location: {self.db_path}")
        self.init_db()

    def init_db(self):
        """Initialize database with proper error handling"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tags TEXT DEFAULT '',
                    created_at TEXT,
                    updated_at TEXT,
                    version INTEGER DEFAULT 1,
                    locked INTEGER DEFAULT 0,
                    content_format TEXT DEFAULT 'html'
                )
            """)

            # Add version column if it doesn't exist (for migration)
            cursor.execute("PRAGMA table_info(notes)")
            columns = [column[1] for column in cursor.fetchall()]
            if 'version' not in columns:
                cursor.execute("ALTER TABLE notes ADD COLUMN version INTEGER DEFAULT 1")
            if 'locked' not in columns:
                cursor.execute("ALTER TABLE notes ADD COLUMN locked INTEGER DEFAULT 0")
            if 'content_format' not in columns:
                cursor.execute("ALTER TABLE notes ADD COLUMN content_format TEXT DEFAULT 'html'")

            conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Database initialization error: {e}")
            raise
        finally:
            conn.close()

    def get_all_note_headers(self) -> List[Note]:
        """Get all note headers (without content) for list display"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT id, title, tags, created_at, updated_at FROM notes ORDER BY updated_at DESC")
            rows = cursor.fetchall()

            notes = []
            for row in rows:
                notes.append(Note(
                    id=row[0], title=row[1], content="", tags=row[2],
                    created_at=row[3], updated_at=row[4]
                ))
            return notes
        except sqlite3.Error as e:
            logger.error(f"Error fetching note headers: {e}")
            return []
        finally:
            conn.close()

    def get_note(self, note_id: int) -> Optional[Note]:
        """Fetch the full content for ONE note when needed"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM notes WHERE id = ?", (note_id,))
            row = cursor.fetchone()

            if row:
                # columns: id, title, content, tags, created_at, updated_at, version, locked, content_format
                return Note(
                    id=row[0], title=row[1], content=row[2], tags=row[3],
                    created_at=row[4], updated_at=row[5],
                    locked=bool(row[7]) if len(row) > 7 else False,
                    content_format=row[8] if len(row) > 8 else 'html'
                )
            return None
        except sqlite3.Error as e:
            logger.error(f"Error fetching note {note_id}: {e}")
            return None
        finally:
            conn.close()

    def save_note(self, note: Note) -> int:
        """Save note with proper error handling"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            if note.id:
                cursor.execute("""
                    UPDATE notes SET title = ?, content = ?, tags = ?, updated_at = ?, locked = ?, content_format = ?
                    WHERE id = ?
                """, (note.title, note.content, note.tags, datetime.now().isoformat(), int(note.locked),
                      note.content_format, note.id))
            else:
                cursor.execute("""
                    INSERT INTO notes (title, content, tags, created_at, updated_at, locked, content_format)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (note.title, note.content, note.tags, note.created_at, note.updated_at, int(note.locked),
                      note.content_format))
                note.id = cursor.lastrowid

            conn.commit()
            return note.id
        except sqlite3.Error as e:
            logger.error(f"Error saving note: {e}")
            raise
        finally:
            conn.close()

    def delete_note(self, note_id: int) -> bool:
        """Delete note with error handling"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM notes WHERE id = ?", (note_id,))
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"Error deleting note {note_id}: {e}")
            return False
        finally:
            conn.close()

    def search_note_headers(self, query: str) -> List[Note]:
        """Search returns only headers to keep memory low during search"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, title, tags, created_at, updated_at FROM notes 
                WHERE title LIKE ? OR content LIKE ? OR tags LIKE ?
                ORDER BY updated_at DESC
            """, (f'%{query}%', f'%{query}%', f'%{query}%'))
            rows = cursor.fetchall()

            notes = []
            for row in rows:
                notes.append(Note(
                    id=row[0], title=row[1], content="", tags=row[2],
                    created_at=row[3], updated_at=row[4]
                ))
            return notes
        except sqlite3.Error as e:
            logger.error(f"Error searching notes: {e}")
            return []
        finally:
            conn.close()

    def get_stats(self) -> Dict[str, int]:
        """Get database statistics"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM notes")
            total_notes = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(DISTINCT tags) FROM notes WHERE tags != ''")
            unique_tags = cursor.fetchone()[0]

            return {
                "total_notes": total_notes,
                "unique_tags": unique_tags,
                "db_size_kb": round(self.db_path.stat().st_size / 1024, 1) if self.db_path.exists() else 0
            }
        except (sqlite3.Error, OSError) as e:
            logger.error(f"Error getting stats: {e}")
            return {"total_notes": 0, "unique_tags": 0, "db_size_kb": 0}
        finally:
            if conn:
                conn.close()
