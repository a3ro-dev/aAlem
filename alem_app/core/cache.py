
from typing import Dict, Optional, Tuple

import redis

from alem_app.database.database import Database, Note
from alem_app.utils.logging import logger


class RedisCacheManager:
    """Lightweight Redis cache: caches notes and tracks dirty ones for periodic flush."""

    def __init__(self, app_config):
        self.enabled = bool(app_config and app_config.get('redis_enabled', True) and redis is not None)
        self.client = None
        self._connected = False
        self._dirty_key = 'alem:dirty'
        if self.enabled:
            try:
                self.client = redis.Redis(
                    host=app_config.get('redis_host', 'localhost'),
                    port=app_config.get('redis_port', 6379),
                    db=app_config.get('redis_db', 0),
                    decode_responses=True,
                )
                # ping once
                self.client.ping()
                self._connected = True
                logger.info("Redis connected")
            except Exception as e:
                logger.warning(f"Redis disabled (connection failed): {e}")
                self.enabled = False

    def key_for(self, note_id: int) -> str:
        return f"alem:note:{note_id}"

    def cache_note(self, note: 'Note'):
        if not (self.enabled and self._connected and note.id):
            return
        self.client.hset(self.key_for(note.id), mapping=note.to_dict())
        self.client.sadd(self._dirty_key, note.id)

    def get_note(self, note_id: int) -> Optional[Dict]:
        if not (self.enabled and self._connected and note_id):
            return None
        data = self.client.hgetall(self.key_for(note_id))
        return data or None

    def mark_dirty(self, note_id: int):
        if not (self.enabled and self._connected and note_id):
            return
        self.client.sadd(self._dirty_key, note_id)

    def dirty_count(self) -> int:
        if not (self.enabled and self._connected):
            return 0
        try:
            return int(self.client.scard(self._dirty_key))
        except Exception:
            return 0

    def flush_to_db(self, db: 'Database') -> Tuple[int, int]:
        """Flush dirty notes back to SQLite. Returns (flushed, errors).""" 
        if not (self.enabled and self._connected):
            return (0, 0)
        flushed = 0
        errors = 0
        try:
            ids = list(self.client.smembers(self._dirty_key))
            for sid in ids:
                try:
                    nid = int(sid)
                except ValueError:
                    continue
                data = self.client.hgetall(self.key_for(nid))
                if not data:
                    self.client.srem(self._dirty_key, nid)
                    continue
                # Normalize types
                note = Note.from_dict({
                    'id': int(data.get('id', nid)),
                    'title': data.get('title', ''),
                    'content': data.get('content', ''),
                    'tags': data.get('tags', ''),
                    'created_at': data.get('created_at'),
                    'updated_at': data.get('updated_at'),
                    'locked': str(data.get('locked', '0')) in ('1', 'True', 'true'),
                    'content_format': data.get('content_format', 'html')
                })
                db.save_note(note)
                self.client.srem(self._dirty_key, nid)
                flushed += 1
        except Exception as e:
            logger.error(f"Redis flush error: {e}")
            errors += 1
        return (flushed, errors)
