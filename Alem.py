import sys
import sqlite3
import json
import logging
import hashlib
import threading
import psutil
import gc
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import time

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QListWidget, QListWidgetItem, QTextEdit, QLineEdit,
    QPushButton, QLabel, QStatusBar, QMessageBox, QStyle,
    QDialog, QDialogButtonBox, QFormLayout, QFrame,
    QTabWidget, QScrollArea, QGroupBox, QCheckBox, QSpinBox,
    QComboBox, QSlider, QTextBrowser, QProgressBar
)
from PyQt6.QtCore import Qt, QTimer, QStandardPaths, QThread, pyqtSignal, QPropertyAnimation, QEasingCurve, QRect, QSize
from PyQt6.QtGui import QFont, QAction, QKeySequence, QIcon, QShortcut, QPixmap, QPainter, QBrush, QColor

# Try to import WebEngine for better preview
try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    WEBENGINE_AVAILABLE = True
except ImportError:
    QWebEngineView = None
    WEBENGINE_AVAILABLE = False

# Optional deps
try:
    import markdown as md
    from markdown.extensions import codehilite, fenced_code, tables, toc
except Exception:
    md = None
try:
    import redis
except Exception:
    redis = None
try:
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.backends import default_backend
    from cryptography.fernet import Fernet, InvalidToken
    import base64
    import os as _os
except Exception:
    PBKDF2HMAC = None
    Fernet = None
    InvalidToken = Exception
    base64 = None
try:
    from pypresence import Presence
except Exception:
    Presence = None

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# App config
try:
    from config import config as app_config
except Exception:
    app_config = None


def _derive_key(password: str, salt: bytes, iterations: int = 390000) -> Optional[bytes]:
    """Derive a Fernet-compatible key from a password and salt."""
    if PBKDF2HMAC is None or base64 is None:
        return None
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=iterations,
        backend=default_backend(),
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key


def encrypt_content(plain_text: str, password: str, iterations: int) -> str:
    """Encrypt content; returns JSON string containing metadata and ciphertext."""
    if Fernet is None:
        raise RuntimeError("Encryption support not available. Install 'cryptography'.")
    salt = _os.urandom(16)
    key = _derive_key(password, salt, iterations)
    f = Fernet(key)
    token = f.encrypt(plain_text.encode('utf-8'))
    payload = {
        'enc': True,
        'alg': 'fernet-pbkdf2',
        'it': iterations,
        'salt': base64.urlsafe_b64encode(salt).decode('ascii'),
        'ct': token.decode('ascii')
    }
    return json.dumps(payload)


def decrypt_content(enc_payload: str, password: str) -> str:
    """Decrypt JSON payload back to plaintext."""
    if Fernet is None:
        raise RuntimeError("Encryption support not available. Install 'cryptography'.")
    data = json.loads(enc_payload)
    if not data.get('enc'):
        return enc_payload
    salt = base64.urlsafe_b64decode(data['salt'])
    iterations = int(data.get('it', 390000))
    key = _derive_key(password, salt, iterations)
    f = Fernet(key)
    try:
        pt = f.decrypt(data['ct'].encode('ascii'))
        return pt.decode('utf-8')
    except InvalidToken:
        raise ValueError("Invalid password")


class RedisCacheManager:
    """Lightweight Redis cache: caches notes and tracks dirty ones for periodic flush."""
    def __init__(self):
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
                    'locked': str(data.get('locked', '0')) in ('1','True','true'),
                    'content_format': data.get('content_format', 'html')
                })
                db.save_note(note)
                self.client.srem(self._dirty_key, nid)
                flushed += 1
        except Exception as e:
            logger.error(f"Redis flush error: {e}")
            errors += 1
        return (flushed, errors)


class DiscordRPCManager:
    def __init__(self):
        self.enabled = bool(app_config and app_config.get('discord_rpc_enabled', True) and Presence is not None)
        self.rpc = None
        self.started = datetime.now()
        if self.enabled:
            try:
                client_id = app_config.get('discord_client_id')
                self.rpc = Presence(client_id)
                self.rpc.connect()
                logger.info("Discord RPC connected")
                # Immediate initial update so presence (including buttons) shows right away
                try:
                    self.update(state="Idle", details="Alem - Smart Notes")
                except Exception as _e:
                    logger.debug(f"Discord initial update failed: {_e}")
            except Exception as e:
                logger.warning(f"Discord RPC disabled: {e}")
                self.enabled = False

    def update(self, state: str = "Editing notes", details: str = "Alem - Smart Notes"):
        if not self.enabled or self.rpc is None:
            return
        try:
            buttons = app_config.get('discord_buttons', []) if app_config else []
            logger.debug(f"Updating Discord RPC (buttons={buttons})")
            self.rpc.update(
                state=state,
                details=details,
                # Use a default asset key; ensure you upload an asset with this name in your Discord app
                large_image=app_config.get('discord_large_image', 'alem') if app_config else 'alem',
                large_text=app_config.get('discord_large_text', 'Alem'),
                start=int(self.started.timestamp()),
                buttons=buttons if buttons else None,
            )
        except Exception as e:
            logger.debug(f"Discord RPC update failed: {e}")
            # don't disable permanently; transient errors are okay

    def close(self):
        if self.enabled and self.rpc is not None:
            try:
                self.rpc.clear()
                self.rpc.close()
            except Exception:
                pass

class SettingsDialog(QDialog):
    """Modern Settings Dialog with Glassmorphism Design"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Alem Settings")
        self.setModal(True)
        self.setMinimumSize(600, 500)
        self.settings_changed = False
        
        # Apply glassmorphism style
        self.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(15, 23, 42, 0.95), stop:1 rgba(30, 41, 59, 0.95));
                border: 1px solid rgba(51, 65, 85, 0.3);
                border-radius: 16px;
            }
            QTabWidget::pane {
                border: 1px solid rgba(51, 65, 85, 0.3);
                border-radius: 12px;
                background: rgba(30, 41, 59, 0.6);
                padding: 16px;
            }
            QTabBar::tab {
                background: rgba(71, 85, 105, 0.3);
                color: #94a3b8;
                padding: 12px 20px;
                margin: 2px;
                border-radius: 8px;
                font-weight: 500;
                border: 1px solid rgba(71, 85, 105, 0.4);
            }
            QTabBar::tab:selected {
                background: rgba(59, 130, 246, 0.2);
                color: #93c5fd;
                border: 1px solid rgba(59, 130, 246, 0.3);
            }
            QGroupBox {
                color: #e2e8f0;
                font-weight: 600;
                border: 1px solid rgba(51, 65, 85, 0.3);
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 16px;
                background: rgba(15, 23, 42, 0.4);
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 16px;
                padding: 0 8px 0 8px;
                color: #f1f5f9;
            }
            QLabel {
                color: #cbd5e1;
                font-weight: 500;
            }
            QLineEdit, QSpinBox, QComboBox {
                background: rgba(30, 41, 59, 0.8);
                border: 1px solid rgba(51, 65, 85, 0.3);
                border-radius: 6px;
                padding: 8px 12px;
                color: #e2e8f0;
                font-weight: 400;
            }
            QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
                border: 1px solid rgba(59, 130, 246, 0.5);
                background: rgba(30, 41, 59, 0.9);
            }
            QCheckBox {
                color: #cbd5e1;
                font-weight: 500;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 1px solid rgba(51, 65, 85, 0.5);
                background: rgba(30, 41, 59, 0.6);
            }
            QCheckBox::indicator:checked {
                background: rgba(59, 130, 246, 0.3);
                border: 1px solid rgba(59, 130, 246, 0.5);
            }
            QPushButton {
                background: rgba(59, 130, 246, 0.2);
                color: #3b82f6;
                border: 1px solid rgba(59, 130, 246, 0.3);
                padding: 10px 20px;
                border-radius: 8px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: rgba(59, 130, 246, 0.3);
                color: #60a5fa;
            }
            QPushButton:pressed {
                background: rgba(59, 130, 246, 0.4);
            }
        """)
        
        self.setup_ui()
        self.load_current_settings()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel("Settings")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title.setStyleSheet("color: #f1f5f9; margin-bottom: 16px;")
        layout.addWidget(title)
        
        # Create tabs
        tabs = QTabWidget()
        layout.addWidget(tabs)
        
        # General tab
        general_tab = self.create_general_tab()
        tabs.addTab(general_tab, "General")
        
        # Editor tab  
        editor_tab = self.create_editor_tab()
        tabs.addTab(editor_tab, "Editor")
        
        # Advanced tab
        advanced_tab = self.create_advanced_tab()
        tabs.addTab(advanced_tab, "Advanced")
        
        # Discord tab
        discord_tab = self.create_discord_tab()
        tabs.addTab(discord_tab, "Discord RPC")
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.save_btn = QPushButton("Save Settings")
        self.save_btn.clicked.connect(self.save_settings)
        button_layout.addWidget(self.save_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
    
    def create_general_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # UI Settings
        ui_group = QGroupBox("User Interface")
        ui_layout = QFormLayout(ui_group)
        
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["dark", "light"])
        ui_layout.addRow("Theme:", self.theme_combo)
        
        self.font_family_combo = QComboBox()
        self.font_family_combo.addItems(["Segoe UI", "Arial", "Helvetica", "Times New Roman", "Consolas"])
        ui_layout.addRow("Font Family:", self.font_family_combo)
        
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 24)
        ui_layout.addRow("Font Size:", self.font_size_spin)
        
        layout.addWidget(ui_group)
        
        # Performance Settings
        perf_group = QGroupBox("Performance")
        perf_layout = QFormLayout(perf_group)
        
        self.auto_save_spin = QSpinBox()
        self.auto_save_spin.setRange(5000, 300000)
        self.auto_save_spin.setSuffix(" ms")
        perf_layout.addRow("Auto-save Interval:", self.auto_save_spin)
        
        self.search_delay_spin = QSpinBox()
        self.search_delay_spin.setRange(100, 2000)
        self.search_delay_spin.setSuffix(" ms")
        perf_layout.addRow("Search Delay:", self.search_delay_spin)
        
        self.max_results_spin = QSpinBox()
        self.max_results_spin.setRange(10, 1000)
        perf_layout.addRow("Max Search Results:", self.max_results_spin)
        
        layout.addWidget(perf_group)
        layout.addStretch()
        
        return widget
    
    def create_editor_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Editor Settings
        editor_group = QGroupBox("Editor Options")
        editor_layout = QFormLayout(editor_group)
        
        self.default_format_combo = QComboBox()
        self.default_format_combo.addItems(["html", "markdown"])
        editor_layout.addRow("Default Format:", self.default_format_combo)
        
        self.ai_search_check = QCheckBox("Enable AI Search")
        editor_layout.addRow("AI Features:", self.ai_search_check)
        
        self.model_cache_check = QCheckBox("Cache AI Models")
        editor_layout.addRow("", self.model_cache_check)
        
        layout.addWidget(editor_group)
        
        # Markdown Settings
        md_group = QGroupBox("Markdown Options")
        md_layout = QVBoxLayout(md_group)
        
        self.fenced_code_check = QCheckBox("Fenced Code Blocks")
        self.tables_check = QCheckBox("Tables")
        self.toc_check = QCheckBox("Table of Contents")
        self.codehilite_check = QCheckBox("Code Highlighting")
        
        for check in [self.fenced_code_check, self.tables_check, self.toc_check, self.codehilite_check]:
            md_layout.addWidget(check)
        
        layout.addWidget(md_group)
        layout.addStretch()
        
        return widget
    
    def create_advanced_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Redis Settings
        redis_group = QGroupBox("Redis Cache")
        redis_layout = QFormLayout(redis_group)
        
        self.redis_enabled_check = QCheckBox("Enable Redis")
        redis_layout.addRow("Cache:", self.redis_enabled_check)
        
        self.redis_host_edit = QLineEdit()
        redis_layout.addRow("Host:", self.redis_host_edit)
        
        self.redis_port_spin = QSpinBox()
        self.redis_port_spin.setRange(1, 65535)
        redis_layout.addRow("Port:", self.redis_port_spin)
        
        self.redis_db_spin = QSpinBox()
        self.redis_db_spin.setRange(0, 15)
        redis_layout.addRow("Database:", self.redis_db_spin)
        
        self.redis_flush_spin = QSpinBox()
        self.redis_flush_spin.setRange(10, 600)
        self.redis_flush_spin.setSuffix(" sec")
        redis_layout.addRow("Flush Interval:", self.redis_flush_spin)
        
        layout.addWidget(redis_group)
        
        # Security Settings
        security_group = QGroupBox("Security")
        security_layout = QFormLayout(security_group)
        
        self.kdf_iterations_spin = QSpinBox()
        self.kdf_iterations_spin.setRange(100000, 1000000)
        self.kdf_iterations_spin.setSuffix(" iterations")
        security_layout.addRow("KDF Iterations:", self.kdf_iterations_spin)
        
        layout.addWidget(security_group)
        layout.addStretch()
        
        return widget
    
    def create_discord_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Discord RPC Settings
        discord_group = QGroupBox("Discord Rich Presence")
        discord_layout = QFormLayout(discord_group)
        
        self.discord_enabled_check = QCheckBox("Enable Discord RPC")
        discord_layout.addRow("Status:", self.discord_enabled_check)
        
        self.discord_client_id_edit = QLineEdit()
        discord_layout.addRow("Client ID:", self.discord_client_id_edit)
        
        self.discord_large_image_edit = QLineEdit()
        discord_layout.addRow("Large Image Key:", self.discord_large_image_edit)
        
        self.discord_large_text_edit = QLineEdit()
        discord_layout.addRow("Large Text:", self.discord_large_text_edit)
        
        self.discord_update_spin = QSpinBox()
        self.discord_update_spin.setRange(1, 300)
        self.discord_update_spin.setSuffix(" sec")
        discord_layout.addRow("Update Interval:", self.discord_update_spin)
        
        layout.addWidget(discord_group)
        
        # Info
        info_label = QLabel("💡 Configure Discord RPC to show your activity while using Alem")
        info_label.setStyleSheet("color: #64748b; font-style: italic; margin-top: 16px;")
        layout.addWidget(info_label)
        
        layout.addStretch()
        return widget
    
    def load_current_settings(self):
        """Load current settings into the dialog"""
        if not app_config:
            return
            
        # General
        self.theme_combo.setCurrentText(app_config.get('theme', 'dark'))
        self.font_family_combo.setCurrentText(app_config.get('font_family', 'Segoe UI'))
        self.font_size_spin.setValue(app_config.get('font_size', 13))
        self.auto_save_spin.setValue(app_config.get('auto_save_interval', 30000))
        self.search_delay_spin.setValue(app_config.get('search_debounce_delay', 300))
        self.max_results_spin.setValue(app_config.get('max_search_results', 100))
        
        # Editor
        self.default_format_combo.setCurrentText(app_config.get('default_content_format', 'html'))
        self.ai_search_check.setChecked(app_config.get('ai_search_enabled', True))
        self.model_cache_check.setChecked(app_config.get('ai_model_cache', True))
        
        # Markdown
        extensions = app_config.get('markdown_extensions', [])
        self.fenced_code_check.setChecked('fenced_code' in extensions)
        self.tables_check.setChecked('tables' in extensions)
        self.toc_check.setChecked('toc' in extensions)
        self.codehilite_check.setChecked('codehilite' in extensions)
        
        # Redis
        self.redis_enabled_check.setChecked(app_config.get('redis_enabled', True))
        self.redis_host_edit.setText(app_config.get('redis_host', 'localhost'))
        self.redis_port_spin.setValue(app_config.get('redis_port', 6379))
        self.redis_db_spin.setValue(app_config.get('redis_db', 0))
        self.redis_flush_spin.setValue(app_config.get('redis_flush_interval_s', 60))
        
        # Security
        self.kdf_iterations_spin.setValue(app_config.get('kdf_iterations', 390000))
        
        # Discord
        self.discord_enabled_check.setChecked(app_config.get('discord_rpc_enabled', True))
        self.discord_client_id_edit.setText(app_config.get('discord_client_id', ''))
        self.discord_large_image_edit.setText(app_config.get('discord_large_image', 'alem'))
        self.discord_large_text_edit.setText(app_config.get('discord_large_text', 'Alem - Smart Notes'))
        self.discord_update_spin.setValue(app_config.get('discord_update_interval_s', 15))
    
    def save_settings(self):
        """Save settings and apply changes"""
        if not app_config:
            return
            
        # General
        app_config.set('theme', self.theme_combo.currentText())
        app_config.set('font_family', self.font_family_combo.currentText())
        app_config.set('font_size', self.font_size_spin.value())
        app_config.set('auto_save_interval', self.auto_save_spin.value())
        app_config.set('search_debounce_delay', self.search_delay_spin.value())
        app_config.set('max_search_results', self.max_results_spin.value())
        
        # Editor
        app_config.set('default_content_format', self.default_format_combo.currentText())
        app_config.set('ai_search_enabled', self.ai_search_check.isChecked())
        app_config.set('ai_model_cache', self.model_cache_check.isChecked())
        
        # Markdown extensions
        extensions = []
        if self.fenced_code_check.isChecked():
            extensions.append('fenced_code')
        if self.tables_check.isChecked():
            extensions.append('tables')
        if self.toc_check.isChecked():
            extensions.append('toc')
        if self.codehilite_check.isChecked():
            extensions.append('codehilite')
        app_config.set('markdown_extensions', extensions)
        
        # Redis
        app_config.set('redis_enabled', self.redis_enabled_check.isChecked())
        app_config.set('redis_host', self.redis_host_edit.text())
        app_config.set('redis_port', self.redis_port_spin.value())
        app_config.set('redis_db', self.redis_db_spin.value())
        app_config.set('redis_flush_interval_s', self.redis_flush_spin.value())
        
        # Security
        app_config.set('kdf_iterations', self.kdf_iterations_spin.value())
        
        # Discord
        app_config.set('discord_rpc_enabled', self.discord_enabled_check.isChecked())
        app_config.set('discord_client_id', self.discord_client_id_edit.text())
        app_config.set('discord_large_image', self.discord_large_image_edit.text())
        app_config.set('discord_large_text', self.discord_large_text_edit.text())
        app_config.set('discord_update_interval_s', self.discord_update_spin.value())
        
        self.settings_changed = True
        self.accept()


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
                """, (note.title, note.content, note.tags, datetime.now().isoformat(), int(note.locked), note.content_format, note.id))
            else:
                cursor.execute("""
                    INSERT INTO notes (title, content, tags, created_at, updated_at, locked, content_format)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (note.title, note.content, note.tags, note.created_at, note.updated_at, int(note.locked), note.content_format))
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

class SmartNotesApp(QMainWindow):
    """Main Alem Application Window with enhanced features and glassmorphism UI"""

    def __init__(self):
        super().__init__()
        self.db = Database()
        self.redis_cache = RedisCacheManager()
        self.discord = DiscordRPCManager()
        self.current_note: Optional[Note] = None
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self._perform_delayed_search)
        self.last_search_query = ""

        self.preview_timer = QTimer()
        self.preview_timer.setSingleShot(True)
        self.preview_timer.timeout.connect(self.render_preview)

        # Enhanced window properties for proper resizing and snapping
        self.setWindowTitle("Alem - Smart Notes")
        self.setGeometry(100, 100, 1400, 900)
        self.setMinimumSize(800, 600)  # Set minimum size for resizing
        
        # Set window icon properly
        try:
            icon_path = Path(__file__).parent / "alem.png"
            if icon_path.exists():
                self.setWindowIcon(QIcon(str(icon_path)))
                # Also set taskbar icon on Windows
                if hasattr(self, 'setWindowIcon'):
                    self.setWindowIcon(QIcon(str(icon_path)))
        except Exception as e:
            logger.warning(f"Could not set app icon: {e}")
        
        # Enable proper window resizing and snapping
        self.setWindowFlags(Qt.WindowType.Window)  # Standard window with title bar
        
        self.setup_ui()
        self.setup_shortcuts()
        self.load_note_headers()
        self.update_stats()

        # Auto-save timer
        self.auto_save_timer = QTimer()
        self.auto_save_timer.timeout.connect(self.auto_save)
        interval = (app_config.get('auto_save_interval', 30000) if app_config else 30000)
        self.auto_save_timer.start(int(interval))

        # Redis periodic flush
        self.redis_flush_timer = QTimer()
        self.redis_flush_timer.timeout.connect(self.flush_cache_periodic)
        flush_s = (app_config.get('redis_flush_interval_s', 60) if app_config else 60)
        self.redis_flush_timer.start(int(flush_s * 1000))

        # Analytics update timer
        self.analytics_timer = QTimer()
        self.analytics_timer.timeout.connect(self.update_analytics)
        self.analytics_timer.start(1000)  # Update every second

    def set_status(self, message: str, timeout_ms: int = 0):
        """Show a status message regardless of status bar implementation.
        If using the custom QWidget status area, updates the label.
        If a real QStatusBar exists, also calls showMessage.
        """
        try:
            if hasattr(self, 'status_message') and isinstance(self.status_message, QLabel):
                self.status_message.setText(message)
            if hasattr(self, 'status_bar') and hasattr(self.status_bar, 'showMessage'):
                # QStatusBar API supports optional timeout
                if timeout_ms:
                    self.status_bar.showMessage(message, int(timeout_ms))
                else:
                    self.status_bar.showMessage(message)
        except Exception as e:
            logger.debug(f"Failed to set status message: {e}")

    def setup_shortcuts(self):
        """Setup Windows-style keyboard shortcuts"""
        # File operations
        QShortcut(QKeySequence.StandardKey.New, self, self.new_note)
        QShortcut(QKeySequence.StandardKey.Save, self, self.save_note)
        QShortcut(QKeySequence.StandardKey.Open, self, self.quick_open)
        QShortcut(QKeySequence("Ctrl+D"), self, self.delete_note)
        QShortcut(QKeySequence("Ctrl+L"), self, self.toggle_lock_current)
        
        # Edit operations
        QShortcut(QKeySequence.StandardKey.Undo, self, lambda: self.content_editor.undo())
        QShortcut(QKeySequence.StandardKey.Redo, self, lambda: self.content_editor.redo())
        QShortcut(QKeySequence.StandardKey.Cut, self, lambda: self.content_editor.cut())
        QShortcut(QKeySequence.StandardKey.Copy, self, lambda: self.content_editor.copy())
        QShortcut(QKeySequence.StandardKey.Paste, self, lambda: self.content_editor.paste())
        QShortcut(QKeySequence.StandardKey.SelectAll, self, lambda: self.content_editor.selectAll())
        
        # Search and navigation
        QShortcut(QKeySequence.StandardKey.Find, self, lambda: self.search_input.setFocus())
        QShortcut(QKeySequence("Ctrl+G"), self, self.focus_notes_list)
        QShortcut(QKeySequence("F3"), self, self.search_next)
        QShortcut(QKeySequence("Shift+F3"), self, self.search_previous)
        
        # Formatting
        QShortcut(QKeySequence.StandardKey.Bold, self, self.toggle_bold)
        QShortcut(QKeySequence.StandardKey.Italic, self, self.toggle_italic)
        QShortcut(QKeySequence.StandardKey.Underline, self, self.toggle_underline)
        
        # View modes
        QShortcut(QKeySequence("Ctrl+1"), self, lambda: self.editor_tabs.setCurrentIndex(0))
        QShortcut(QKeySequence("Ctrl+2"), self, lambda: self.editor_tabs.setCurrentIndex(1))
        QShortcut(QKeySequence("F5"), self, self.render_preview)
        QShortcut(QKeySequence("F11"), self, self.toggle_fullscreen)
        
        # Application
        QShortcut(QKeySequence("Ctrl+,"), self, self.show_settings)
        QShortcut(QKeySequence("Ctrl+Shift+I"), self, self.show_debug_info)
        QShortcut(QKeySequence("F1"), self, self.show_help)
        QShortcut(QKeySequence.StandardKey.Quit, self, self.close)

    def setup_ui(self):
        """Setup the UI with native window frame and status bar."""
        # Theme
        self.setStyleSheet("""
            QMainWindow {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(10, 15, 28, 0.95),
                    stop:0.3 rgba(13, 20, 33, 0.92),
                    stop:0.7 rgba(17, 24, 39, 0.94),
                    stop:1 rgba(30, 41, 59, 0.96));
                color: #e2e8f0;
            }
            QWidget { color: #e2e8f0; }
        """)

        # Central widget
        central_widget = QWidget()
        central_widget.setContentsMargins(8, 8, 8, 8)
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Content area
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(8, 8, 8, 8)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        content_layout.addWidget(splitter)

        # Left panel
        splitter.addWidget(self.create_left_panel())
        # Right panel
        splitter.addWidget(self.create_right_panel())
        splitter.setSizes([400, 1000])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        main_layout.addLayout(content_layout)

        # Status bar
        self.status_bar = self.create_status_bar()
        self.setStatusBar(self.status_bar)

    def create_title_bar(self):
        """Create custom title bar with glassmorphism"""
        title_bar = QWidget()
        title_bar.setFixedHeight(40)
        title_bar.setStyleSheet("""
            QWidget {
                background: rgba(15, 23, 42, 0.9);
                border-radius: 12px 12px 0 0;
                border-bottom: 1px solid rgba(51, 65, 85, 0.3);
            }
            QLabel {
                color: #f1f5f9;
                font-weight: 600;
                font-size: 14px;
            }
            QPushButton {
                background: rgba(71, 85, 105, 0.3);
                border: 1px solid rgba(71, 85, 105, 0.4);
                border-radius: 6px;
                color: #94a3b8;
                font-weight: 600;
                font-size: 12px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background: rgba(239, 68, 68, 0.3);
                color: #ef4444;
                border: 1px solid rgba(239, 68, 68, 0.4);
            }
        """)
        
        layout = QHBoxLayout(title_bar)
        layout.setContentsMargins(16, 8, 16, 8)
        
        # App title and icon
        title_layout = QHBoxLayout()
        
        app_icon = QLabel("🌟")
        app_icon.setStyleSheet("font-size: 16px;")
        title_layout.addWidget(app_icon)
        
        app_title = QLabel("Alem - Smart Notes")
        title_layout.addWidget(app_title)
        
        layout.addLayout(title_layout)
        layout.addStretch()
        
        # Window controls
        minimize_btn = QPushButton("−")
        minimize_btn.setFixedSize(32, 24)
        minimize_btn.clicked.connect(self.showMinimized)
        layout.addWidget(minimize_btn)
        
        maximize_btn = QPushButton("□")
        maximize_btn.setFixedSize(32, 24)
        maximize_btn.clicked.connect(self.toggle_maximize)
        layout.addWidget(maximize_btn)
        
        close_btn = QPushButton("×")
        close_btn.setFixedSize(32, 24)
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)
        
        return title_bar

    def create_status_bar(self):
        """Create a clean status bar with working analytics."""
        bar = QStatusBar()
        bar.setStyleSheet("""
            QStatusBar {
                background: rgba(15, 23, 42, 0.95);
                color: #94a3b8;
                border-top: 1px solid rgba(51, 65, 85, 0.3);
                font-family: 'Segoe UI', system-ui, sans-serif;
                font-size: 11px;
                padding: 4px 8px;
            }
            QLabel {
                color: #94a3b8;
                padding: 0 6px;
                background: rgba(30, 41, 59, 0.6);
                border: 1px solid rgba(51, 65, 85, 0.3);
                border-radius: 4px;
                margin: 2px;
            }
        """)

        # Working analytics widgets
        self.analytics_notes = QLabel("Notes: 0")
        self.analytics_format = QLabel("Format: -")
        self.analytics_redis = QLabel("Cache: Off")
        self.analytics_status = QLabel("Ready")

        # Progress for long operations
        self.operation_progress = QProgressBar()
        self.operation_progress.setVisible(False)
        self.operation_progress.setFixedWidth(120)
        self.operation_progress.setStyleSheet("""
            QProgressBar {
                background: rgba(30, 41, 59, 0.6); 
                border: 1px solid rgba(51, 65, 85, 0.3); 
                border-radius: 4px; 
                height: 14px;
            } 
            QProgressBar::chunk {
                background: rgba(59, 130, 246, 0.6); 
                border-radius: 3px;
            }
        """)

        for w in [self.analytics_notes, self.analytics_format, self.analytics_redis, self.analytics_status, self.operation_progress]:
            bar.addPermanentWidget(w)
        bar.showMessage("Ready • Alem Smart Notes")
        return bar
        # This duplicate UI setup code has been removed - UI is now handled in setup_ui()
    
    def create_menu_bar(self):
        """Create the menu bar"""
        menubar = self.menuBar()
        menubar.setStyleSheet("""
            QMenuBar {
                background: rgba(15, 23, 42, 0.95);
                color: #e2e8f0;
                border-bottom: 1px solid rgba(51, 65, 85, 0.3);
                font-family: 'Segoe UI', system-ui, sans-serif;
                font-size: 13px;
                font-weight: 500;
            }
            QMenuBar::item {
                background-color: transparent;
                padding: 8px 16px;
                margin: 2px 0px;
                border-radius: 6px;
            }
            QMenuBar::item:selected {
                background: rgba(59, 130, 246, 0.2);
                color: #93c5fd;
            }
            QMenu {
                background: rgba(15, 23, 42, 0.98);
                color: #e2e8f0;
                border: 1px solid rgba(51, 65, 85, 0.3);
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item {
                padding: 8px 16px;
                border-radius: 6px;
                margin: 1px;
            }
            QMenu::item:selected {
                background: rgba(59, 130, 246, 0.2);
                color: #93c5fd;
            }
        """)

        # File menu
        file_menu = menubar.addMenu('File')

        new_action = QAction('New Note', self)
        new_action.setShortcut(QKeySequence.StandardKey.New)
        new_action.triggered.connect(self.new_note)
        file_menu.addAction(new_action)

        save_action = QAction('Save', self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self.save_note)
        file_menu.addAction(save_action)

        lock_action = QAction('Lock/Unlock Note', self)
        lock_action.setShortcut('Ctrl+L')
        lock_action.triggered.connect(self.toggle_lock_current)
        file_menu.addAction(lock_action)

        file_menu.addSeparator()
        exit_action = QAction('Exit', self)
        exit_action.setShortcut(QKeySequence.StandardKey.Close)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Search menu
        search_menu = menubar.addMenu('Search')
        search_action = QAction('Search Notes', self)
        search_action.setShortcut(QKeySequence.StandardKey.Find)
        search_action.triggered.connect(lambda: self.search_input.setFocus())
        search_menu.addAction(search_action)

        # View menu
        view_menu = menubar.addMenu('View')
        self.action_show_edit = QAction('Edit Mode', self)
        self.action_show_edit.setShortcut('Ctrl+1')
        self.action_show_edit.triggered.connect(lambda: self.editor_tabs.setCurrentIndex(0))
        view_menu.addAction(self.action_show_edit)

        self.action_show_preview = QAction('Preview Mode', self)
        self.action_show_preview.setShortcut('Ctrl+2')
        self.action_show_preview.triggered.connect(lambda: self.editor_tabs.setCurrentIndex(1))
        view_menu.addAction(self.action_show_preview)

        self.action_refresh_preview = QAction('Refresh Preview', self)
        self.action_refresh_preview.setShortcut('F5')
        self.action_refresh_preview.triggered.connect(self.render_preview)
        view_menu.addAction(self.action_refresh_preview)

        # Help menu
        help_menu = menubar.addMenu('Help')
        about_action = QAction('About Alem', self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    def create_left_panel(self):
        """Create enhanced left panel with glassmorphism design"""
        panel = QWidget()
        panel.setStyleSheet("""
            QWidget {
                background: rgba(15, 23, 42, 0.7);
                border: 1px solid rgba(51, 65, 85, 0.3);
                border-radius: 12px;
            }
        """)
        
        layout = QVBoxLayout(panel)
        layout.setSpacing(16)
        layout.setContentsMargins(16, 16, 16, 16)

        # Enhanced header with logo
        header_widget = QWidget()
        header_widget.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(59, 130, 246, 0.1), stop:1 rgba(139, 92, 246, 0.1));
                border: 1px solid rgba(59, 130, 246, 0.3);
                border-radius: 12px;
                padding: 20px;
            }
        """)
        
        header_layout = QVBoxLayout(header_widget)
        
        app_logo = QLabel()
        try:
            icon_path = Path(__file__).parent / "alem.png"
            if icon_path.exists():
                pm = QPixmap(str(icon_path))
                app_logo.setPixmap(pm.scaled(QSize(40, 40), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        except Exception:
            pass
        app_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(app_logo)
        
        header = QLabel("Alem")
        header.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        header.setStyleSheet("""
            QLabel { 
                color: #f1f5f9; 
                font-family: 'Segoe UI', system-ui, sans-serif;
                font-weight: 700;
                text-align: center;
                background: transparent;
                border: none;
            }
        """)
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(header)
        
        tagline = QLabel("Smart Notes")
        tagline.setStyleSheet("""
            QLabel {
                color: #94a3b8;
                font-size: 12px;
                font-weight: 500;
                text-align: center;
                background: transparent;
                border: none;
            }
        """)
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(tagline)
        
        layout.addWidget(header_widget)

        # Enhanced search bar with AI toggle
        search_container = QWidget()
        search_container.setStyleSheet("""
            QWidget {
                background: rgba(30, 41, 59, 0.8);
                border: 1px solid rgba(51, 65, 85, 0.3);
                border-radius: 12px;
                padding: 8px;
            }
        """)
        
        search_layout = QVBoxLayout(search_container)
        search_layout.setSpacing(8)
        
        # Search input with icon
        search_input_layout = QHBoxLayout()
        search_input_layout.setSpacing(8)
        
    # Removed emoji icon for cleaner look
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search notes with AI...")
        self.search_input.textChanged.connect(self.on_search)
        self.search_input.setStyleSheet("""
            QLineEdit {
                padding: 12px 16px;
                border: 1px solid rgba(51, 65, 85, 0.3);
                border-radius: 10px;
                background: rgba(15, 23, 42, 0.8);
                color: #e2e8f0;
                font-size: 14px;
                font-family: 'Segoe UI', system-ui, sans-serif;
                font-weight: 400;
            }
            QLineEdit:focus {
                border: 1px solid rgba(59, 130, 246, 0.5);
                background: rgba(15, 23, 42, 0.9);
                color: #f1f5f9;
                box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
            }
            QLineEdit::placeholder {
                color: #64748b;
            }
        """)
        search_input_layout.addWidget(self.search_input)
        
        # AI Toggle with enhanced design
        self.ai_toggle = QPushButton("AI")
        self.ai_toggle.setCheckable(True)
        self.ai_toggle.setChecked(True)
        self.ai_toggle.setFixedSize(50, 44)
        self.ai_toggle.setStyleSheet("""
            QPushButton {
                background: rgba(239, 68, 68, 0.2);
                color: #ef4444;
                border: 1px solid rgba(239, 68, 68, 0.3);
                border-radius: 10px;
                font-weight: 700;
                font-size: 12px;
                font-family: 'Segoe UI', system-ui, sans-serif;
            }
            QPushButton:checked {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(34, 197, 94, 0.3), stop:1 rgba(59, 130, 246, 0.3));
                color: #22c55e;
                border: 1px solid rgba(34, 197, 94, 0.4);
                box-shadow: 0 0 0 2px rgba(34, 197, 94, 0.1);
            }
            QPushButton:hover {
                background: rgba(59, 130, 246, 0.2);
                color: #3b82f6;
                border: 1px solid rgba(59, 130, 246, 0.3);
                transform: scale(1.05);
            }
        """)
        search_input_layout.addWidget(self.ai_toggle)
        
        search_layout.addLayout(search_input_layout)
        
        # Search filters
        filters_layout = QHBoxLayout()
        
        self.filter_all = QPushButton("All")
        self.filter_recent = QPushButton("Recent")
        self.filter_locked = QPushButton("🔒")
        
        for btn in [self.filter_all, self.filter_recent, self.filter_locked]:
            btn.setCheckable(True)
            btn.setStyleSheet("""
                QPushButton {
                    background: rgba(71, 85, 105, 0.3);
                    color: #94a3b8;
                    border: 1px solid rgba(71, 85, 105, 0.4);
                    padding: 6px 12px;
                    border-radius: 6px;
                    font-weight: 500;
                    font-size: 11px;
                }
                QPushButton:checked {
                    background: rgba(59, 130, 246, 0.3);
                    color: #3b82f6;
                    border: 1px solid rgba(59, 130, 246, 0.4);
                }
                QPushButton:hover {
                    background: rgba(71, 85, 105, 0.4);
                    color: #cbd5e1;
                }
            """)
            filters_layout.addWidget(btn)
        
        self.filter_all.setChecked(True)
        filters_layout.addStretch()
        
        search_layout.addLayout(filters_layout)
        layout.addWidget(search_container)

        # Enhanced notes list with better styling
        self.notes_list = QListWidget()
        self.notes_list.itemClicked.connect(self.load_selected_note)
        self.notes_list.setStyleSheet("""
            QListWidget {
                border: 1px solid rgba(51, 65, 85, 0.3);
                border-radius: 12px;
                background: rgba(30, 41, 59, 0.6);
                color: #e2e8f0;
                padding: 8px;
                font-size: 14px;
                font-family: 'Segoe UI', system-ui, sans-serif;
                outline: none;
            }
            QListWidget::item {
                padding: 16px 12px;
                border-bottom: 1px solid rgba(51, 65, 85, 0.2);
                border-radius: 10px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(15, 23, 42, 0.7), stop:1 rgba(30, 41, 59, 0.5));
                color: #e2e8f0;
                margin: 3px 2px;
                font-weight: 500;
                border: 1px solid rgba(51, 65, 85, 0.2);
            }
            QListWidget::item:selected {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(59, 130, 246, 0.3), stop:1 rgba(139, 92, 246, 0.2));
                color: #93c5fd;
                border: 1px solid rgba(59, 130, 246, 0.4);
                box-shadow: 0 4px 12px rgba(59, 130, 246, 0.2);
            }
            QListWidget::item:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(71, 85, 105, 0.4), stop:1 rgba(59, 130, 246, 0.2));
                color: #f1f5f9;
                border: 1px solid rgba(71, 85, 105, 0.5);
                transform: translateY(-1px);
            }
            QScrollBar:vertical {
                background: rgba(15, 23, 42, 0.4);
                width: 8px;
                border-radius: 4px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: rgba(71, 85, 105, 0.6);
                border-radius: 4px;
                min-height: 20px;
                margin: 2px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(59, 130, 246, 0.6);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        layout.addWidget(self.notes_list)

        # Enhanced action buttons
        button_container = QWidget()
        button_container.setStyleSheet("""
            QWidget {
                background: rgba(30, 41, 59, 0.6);
                border: 1px solid rgba(51, 65, 85, 0.3);
                border-radius: 12px;
                padding: 12px;
            }
        """)
        
        button_layout = QVBoxLayout(button_container)
        button_layout.setSpacing(8)
        
        # Primary actions
        primary_layout = QHBoxLayout()
        primary_layout.setSpacing(8)
        
        self.new_note_btn = QPushButton("New Note")
        self.new_note_btn.clicked.connect(self.new_note)
        try:
            self.new_note_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
            self.new_note_btn.setIconSize(QSize(18, 18))
        except Exception:
            pass
        self.new_note_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(59, 130, 246, 0.3), stop:1 rgba(139, 92, 246, 0.2));
                color: #93c5fd;
                border: 1px solid rgba(59, 130, 246, 0.4);
                padding: 12px 16px;
                border-radius: 8px;
                font-weight: 600;
                font-size: 12px;
                font-family: 'Segoe UI', system-ui, sans-serif;
                min-height: 20px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(59, 130, 246, 0.4), stop:1 rgba(139, 92, 246, 0.3));
                color: #bfdbfe;
                border: 1px solid rgba(59, 130, 246, 0.5);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(59, 130, 246, 0.5), stop:1 rgba(139, 92, 246, 0.4));
            }
        """)
        primary_layout.addWidget(self.new_note_btn)
        
        self.delete_note_btn = QPushButton("Delete")
        self.delete_note_btn.clicked.connect(self.delete_note)
        self.delete_note_btn.setFixedSize(60, 40)
        try:
            self.delete_note_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon))
            self.delete_note_btn.setIconSize(QSize(16, 16))
        except Exception:
            pass
        self.delete_note_btn.setStyleSheet("""
            QPushButton {
                background: rgba(239, 68, 68, 0.2);
                color: #ef4444;
                border: 1px solid rgba(239, 68, 68, 0.3);
                padding: 8px 12px;
                border-radius: 8px;
                font-weight: 600;
                font-size: 11px;
                font-family: 'Segoe UI', system-ui, sans-serif;
                min-height: 20px;
            }
            QPushButton:hover {
                background: rgba(239, 68, 68, 0.3);
                color: #f87171;
                border: 1px solid rgba(239, 68, 68, 0.4);
            }
            QPushButton:pressed {
                background: rgba(239, 68, 68, 0.4);
            }
        """)
        primary_layout.addWidget(self.delete_note_btn)
        
        button_layout.addLayout(primary_layout)
        
        # Secondary actions
        secondary_layout = QHBoxLayout()
        secondary_layout.setSpacing(6)
        
        self.import_btn = QPushButton("Import")
        self.export_btn = QPushButton("Export")
        self.settings_btn = QPushButton("Settings")
        # Add standard icons where available
        try:
            self.import_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))
            self.export_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))
            self.settings_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView))
            for b in [self.import_btn, self.export_btn, self.settings_btn]:
                b.setIconSize(QSize(14, 14))
        except Exception:
            pass
        
        for btn in [self.import_btn, self.export_btn, self.settings_btn]:
            btn.setStyleSheet("""
                QPushButton {
                    background: rgba(71, 85, 105, 0.3);
                    color: #94a3b8;
                    border: 1px solid rgba(71, 85, 105, 0.4);
                    padding: 6px 10px;
                    border-radius: 6px;
                    font-weight: 500;
                    font-size: 10px;
                    font-family: 'Segoe UI', system-ui, sans-serif;
                    min-height: 16px;
                }
                QPushButton:hover {
                    background: rgba(71, 85, 105, 0.4);
                    color: #cbd5e1;
                    border: 1px solid rgba(71, 85, 105, 0.5);
                }
            """)
            secondary_layout.addWidget(btn)
        
        self.settings_btn.clicked.connect(self.show_settings)
        button_layout.addLayout(secondary_layout)
        
        layout.addWidget(button_container)

        # Enhanced stats panel with real-time metrics
        stats_frame = QFrame()
        stats_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(30, 41, 59, 0.8), stop:1 rgba(15, 23, 42, 0.6));
                border: 1px solid rgba(51, 65, 85, 0.3);
                border-radius: 12px;
                padding: 16px;
            }
        """)
        stats_layout = QVBoxLayout(stats_frame)
        
        stats_title = QLabel("📊 Analytics")
        stats_title.setStyleSheet("""
            QLabel {
                color: #f1f5f9;
                font-weight: 600;
                font-size: 13px;
                margin-bottom: 8px;
                border: none;
                background: transparent;
            }
        """)
        stats_layout.addWidget(stats_title)

        # Stats labels for the left panel
        self.cache_label = QLabel("Cache: Ready")
        self.notes_count_label = QLabel("Notes: 0")
        self.db_size_label = QLabel("Database: 0 KB")

        for label in [self.cache_label, self.notes_count_label, self.db_size_label]:
            label.setFont(QFont("Segoe UI", 10, QFont.Weight.Medium))
            label.setStyleSheet("""
                QLabel { 
                    color: #94a3b8; 
                    font-family: 'Segoe UI', system-ui, sans-serif;
                    font-weight: 500;
                    padding: 4px 8px;
                    background: rgba(15, 23, 42, 0.5);
                    border: 1px solid rgba(51, 65, 85, 0.2);
                    border-radius: 6px;
                    margin: 2px 0px;
                }
            """)
            stats_layout.addWidget(label)

        layout.addWidget(stats_frame)

        panel.setMinimumWidth(320)
        panel.setMaximumWidth(500)
        return panel

    def create_right_panel(self):
        """Create enhanced right panel with modern editor"""
        panel = QWidget()
        panel.setStyleSheet("""
            QWidget {
                background: rgba(15, 23, 42, 0.7);
                border: 1px solid rgba(51, 65, 85, 0.3);
                border-radius: 12px;
            }
        """)
        
        layout = QVBoxLayout(panel)
        layout.setSpacing(16)
        layout.setContentsMargins(16, 16, 16, 16)

        # Enhanced header with note metadata
        header_container = QWidget()
        header_container.setStyleSheet("""
            QWidget {
                background: rgba(30, 41, 59, 0.8);
                border: 1px solid rgba(51, 65, 85, 0.3);
                border-radius: 12px;
                padding: 16px;
            }
        """)
        
        header_layout = QVBoxLayout(header_container)
        header_layout.setSpacing(12)
        
        # Title input with enhanced styling
        title_layout = QHBoxLayout()
        title_icon = QLabel()
        title_layout.addWidget(title_icon)

        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("Enter an amazing title...")
        self.title_input.textChanged.connect(self.on_content_changed)
        self.title_input.setStyleSheet("""
            QLineEdit {
                padding: 14px 18px;
                border: 1px solid rgba(51, 65, 85, 0.3);
                border-radius: 10px;
                font-size: 18px;
                color: #f1f5f9;
                background: rgba(15, 23, 42, 0.8);
                font-family: 'Segoe UI', system-ui, sans-serif;
                font-weight: 600;
            }
            QLineEdit:focus {
                border: 1px solid rgba(59, 130, 246, 0.5);
                background: rgba(15, 23, 42, 0.9);
                color: #f8fafc;
                box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
            }
            QLineEdit::placeholder {
                color: #64748b;
                font-weight: 400;
            }
        """)
        title_layout.addWidget(self.title_input)
        header_layout.addLayout(title_layout)

        # Tags and metadata row
        meta_layout = QHBoxLayout()
        
        # Tags input
        tags_container = QHBoxLayout()
        tags_icon = QLabel("🏷️")
        tags_icon.setStyleSheet("font-size: 16px; color: #a78bfa;")
        tags_container.addWidget(tags_icon)
        
        self.tags_input = QLineEdit()
        self.tags_input.setPlaceholderText("Add tags: productivity, ideas, work...")
        self.tags_input.textChanged.connect(self.on_content_changed)
        self.tags_input.setStyleSheet("""
            QLineEdit {
                padding: 10px 16px;
                border: 1px solid rgba(51, 65, 85, 0.3);
                border-radius: 8px;
                font-size: 13px;
                color: #e2e8f0;
                background: rgba(15, 23, 42, 0.6);
                font-family: 'Segoe UI', system-ui, sans-serif;
                font-weight: 400;
            }
            QLineEdit:focus {
                border: 1px solid rgba(139, 92, 246, 0.5);
                background: rgba(15, 23, 42, 0.8);
                color: #f1f5f9;
            }
            QLineEdit::placeholder {
                color: #64748b;
            }
        """)
        tags_container.addWidget(self.tags_input)
        meta_layout.addLayout(tags_container)
        
        # Lock button
        self.lock_btn = QPushButton("Unlock")
        self.lock_btn.setFixedSize(40, 40)
        self.lock_btn.setCheckable(True)
        self.lock_btn.clicked.connect(self.toggle_lock_current)
        self.lock_btn.setStyleSheet("""
            QPushButton {
                background: rgba(71, 85, 105, 0.3);
                color: #94a3b8;
                border: 1px solid rgba(71, 85, 105, 0.4);
                border-radius: 8px;
                font-size: 16px;
            }
            QPushButton:checked {
                background: rgba(239, 68, 68, 0.3);
                color: #ef4444;
                border: 1px solid rgba(239, 68, 68, 0.4);
            }
            QPushButton:hover {
                background: rgba(59, 130, 246, 0.3);
                transform: scale(1.1);
            }
        """)
        meta_layout.addWidget(self.lock_btn)
        
        header_layout.addLayout(meta_layout)
        layout.addWidget(header_container)

        # Enhanced formatting toolbar
        toolbar_container = QWidget()
        toolbar_container.setStyleSheet("""
            QWidget {
                background: rgba(30, 41, 59, 0.8);
                border: 1px solid rgba(51, 65, 85, 0.3);
                border-radius: 10px;
                padding: 8px 12px;
            }
        """)
        
        toolbar_layout = QHBoxLayout(toolbar_container)
        toolbar_layout.setSpacing(6)
        
        # Format mode selector
        format_group = QHBoxLayout()
        format_label = QLabel("Format:")
        format_label.setStyleSheet("color: #94a3b8; font-weight: 500; font-size: 12px;")
        format_group.addWidget(format_label)
        
        self.format_combo = QComboBox()
        self.format_combo.addItems(["HTML", "Markdown"])
        self.format_combo.currentTextChanged.connect(self.on_format_changed)
        self.format_combo.setStyleSheet("""
            QComboBox {
                background: rgba(15, 23, 42, 0.8);
                border: 1px solid rgba(51, 65, 85, 0.3);
                border-radius: 6px;
                padding: 4px 8px;
                color: #e2e8f0;
                font-weight: 500;
                min-width: 80px;
            }
            QComboBox:focus {
                border: 1px solid rgba(59, 130, 246, 0.5);
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 4px solid #94a3b8;
                margin-right: 6px;
            }
        """)
        format_group.addWidget(self.format_combo)
        format_group.addWidget(QLabel("|"))
        toolbar_layout.addLayout(format_group)

        # Text formatting buttons with better icons
        formatting_buttons = [
            ("B", "Bold", self.toggle_bold),
            ("I", "Italic", self.toggle_italic),
            ("U", "Underline", self.toggle_underline),
            ("", "sep", None),
            ("L", "Align Left", lambda: self.set_alignment(Qt.AlignmentFlag.AlignLeft)),
            ("C", "Center", lambda: self.set_alignment(Qt.AlignmentFlag.AlignCenter)),
            ("R", "Align Right", lambda: self.set_alignment(Qt.AlignmentFlag.AlignRight)),
            ("", "sep", None),
            ("🔗", "Insert Link", self.insert_link),
            ("📷", "Insert Image", self.insert_image),
            ("</>", "Insert Code", self.insert_code_block),
        ]
        
        self.format_buttons = {}
        
        for text, tooltip, action in formatting_buttons:
            if text == "":
                separator = QLabel("•")
                separator.setStyleSheet("color: #475569; font-size: 14px; margin: 0 4px;")
                toolbar_layout.addWidget(separator)
                continue
                
            btn = QPushButton(text)
            btn.setFixedSize(32, 32)
            btn.setToolTip(tooltip)
            
            if text in ["B", "I", "U"]:
                btn.setCheckable(True)
                self.format_buttons[text] = btn
            
            if action:
                btn.clicked.connect(action)
                
            btn.setStyleSheet("""
                QPushButton {
                    background: rgba(71, 85, 105, 0.3);
                    color: #94a3b8;
                    border: 1px solid rgba(71, 85, 105, 0.4);
                    border-radius: 6px;
                    font-weight: 600;
                    font-size: 11px;
                    font-family: 'Segoe UI', system-ui, sans-serif;
                    min-width: 28px;
                    min-height: 28px;
                }
                QPushButton:checked {
                    background: rgba(59, 130, 246, 0.3);
                    color: #3b82f6;
                    border: 1px solid rgba(59, 130, 246, 0.4);
                }
                QPushButton:hover {
                    background: rgba(71, 85, 105, 0.4);
                    color: #cbd5e1;
                    transform: translateY(-1px);
                }
            """)
            toolbar_layout.addWidget(btn)

        toolbar_layout.addStretch()
        
        # Font size controls
        size_controls = QHBoxLayout()
        size_controls.addWidget(QLabel("Size:"))
        
        size_down_btn = QPushButton("−")
        size_down_btn.setFixedSize(28, 28)
        size_down_btn.clicked.connect(self.decrease_font_size)
        
        size_up_btn = QPushButton("+")
        size_up_btn.setFixedSize(28, 28)
        size_up_btn.clicked.connect(self.increase_font_size)
        
        for btn in [size_down_btn, size_up_btn]:
            btn.setStyleSheet("""
                QPushButton {
                    background: rgba(71, 85, 105, 0.3);
                    color: #94a3b8;
                    border: 1px solid rgba(71, 85, 105, 0.4);
                    border-radius: 6px;
                    font-weight: bold;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background: rgba(71, 85, 105, 0.4);
                    color: #cbd5e1;
                }
            """)
        
        size_controls.addWidget(size_down_btn)
        size_controls.addWidget(size_up_btn)
        toolbar_layout.addLayout(size_controls)
        
        layout.addWidget(toolbar_container)

        # Enhanced editor tabs with better preview
        self.editor_tabs = QTabWidget()
        self.editor_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid rgba(51, 65, 85, 0.3);
                border-radius: 12px;
                background: rgba(30, 41, 59, 0.6);
                padding: 0px;
            }
            QTabBar::tab {
                background: rgba(71, 85, 105, 0.3);
                color: #94a3b8;
                padding: 12px 24px;
                margin: 2px;
                border-radius: 8px;
                font-weight: 600;
                font-size: 13px;
                border: 1px solid rgba(71, 85, 105, 0.4);
                min-width: 80px;
            }
            QTabBar::tab:selected {
                background: rgba(59, 130, 246, 0.3);
                color: #93c5fd;
                border: 1px solid rgba(59, 130, 246, 0.4);
                box-shadow: 0 2px 8px rgba(59, 130, 246, 0.2);
            }
            QTabBar::tab:hover:!selected {
                background: rgba(71, 85, 105, 0.4);
                color: #cbd5e1;
            }
        """)
        
        # Edit tab
        edit_tab = QWidget()
        edit_layout = QVBoxLayout(edit_tab)
        edit_layout.setContentsMargins(16, 16, 16, 16)
        
        self.content_editor = QTextEdit()
        self.content_editor.textChanged.connect(self.on_content_changed)
        self.content_editor.cursorPositionChanged.connect(self.update_format_buttons)
        self.content_editor.setFont(QFont("Segoe UI", 14))
        self.content_editor.setStyleSheet("""
            QTextEdit {
                border: 1px solid rgba(51, 65, 85, 0.3);
                border-radius: 12px;
                padding: 24px;
                background: rgba(15, 23, 42, 0.8);
                color: #f1f5f9;
                line-height: 1.6;
                font-family: 'Segoe UI', 'San Francisco', system-ui, sans-serif;
                font-weight: 400;
                font-size: 14px;
                selection-background-color: rgba(59, 130, 246, 0.3);
                selection-color: #bfdbfe;
            }
            QTextEdit:focus {
                border: 1px solid rgba(59, 130, 246, 0.5);
                background: rgba(15, 23, 42, 0.9);
                box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
            }
            QScrollBar:vertical {
                background: rgba(15, 23, 42, 0.4);
                width: 12px;
                border-radius: 6px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: rgba(71, 85, 105, 0.6);
                border-radius: 6px;
                min-height: 20px;
                margin: 2px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(59, 130, 246, 0.6);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        edit_layout.addWidget(self.content_editor)
        self.editor_tabs.addTab(edit_tab, "✏️ Edit")

        # Enhanced preview tab
        preview_tab = QWidget()
        preview_layout = QVBoxLayout(preview_tab)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        
        # Use web view for better markdown rendering if available
        try:
            self.preview_view = QWebEngineView()
            self.preview_view.setStyleSheet("""
                QWebEngineView {
                    border: 1px solid rgba(51, 65, 85, 0.3);
                    border-radius: 12px;
                    background: rgba(15, 23, 42, 0.8);
                }
            """)
        except:
            # Fallback to QTextEdit
            self.preview_view = QTextEdit()
            self.preview_view.setReadOnly(True)
            self.preview_view.setStyleSheet("""
                QTextEdit {
                    border: 1px solid rgba(51, 65, 85, 0.3);
                    border-radius: 12px;
                    padding: 24px;
                    background: rgba(15, 23, 42, 0.8);
                    color: #f1f5f9;
                    font-family: 'Segoe UI', system-ui, sans-serif;
                    font-size: 14px;
                    line-height: 1.6;
                }
            """)
        
        preview_layout.addWidget(self.preview_view)
        self.editor_tabs.addTab(preview_tab, "👁️ Preview")

        self.editor_tabs.currentChanged.connect(self.on_tab_changed)
        layout.addWidget(self.editor_tabs)

        # Enhanced action buttons
        actions_container = QWidget()
        actions_container.setStyleSheet("""
            QWidget {
                background: rgba(30, 41, 59, 0.8);
                border: 1px solid rgba(51, 65, 85, 0.3);
                border-radius: 10px;
                padding: 12px 16px;
            }
        """)
        
        actions_layout = QHBoxLayout(actions_container)
        actions_layout.setSpacing(12)
        
        # Word count display
        self.word_count_label = QLabel("0 words")
        self.word_count_label.setStyleSheet("""
            QLabel {
                color: #64748b;
                font-weight: 500;
                font-size: 12px;
                background: rgba(15, 23, 42, 0.6);
                padding: 6px 12px;
                border: 1px solid rgba(51, 65, 85, 0.3);
                border-radius: 6px;
            }
        """)
        actions_layout.addWidget(self.word_count_label)
        
        actions_layout.addStretch()
        
        # Action buttons
        self.save_btn = QPushButton("Save Note")
        self.save_btn.clicked.connect(self.save_note)
        self.save_btn.setEnabled(False)
        try:
            self.save_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))
            self.save_btn.setIconSize(QSize(20,20))
        except Exception:
            pass
        self.save_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(34, 197, 94, 0.3), stop:1 rgba(59, 130, 246, 0.2));
                color: #22c55e;
                border: 1px solid rgba(34, 197, 94, 0.4);
                padding: 10px 20px;
                border-radius: 8px;
                font-weight: 600;
                font-size: 12px;
                font-family: 'Segoe UI', system-ui, sans-serif;
                min-height: 20px;
            }
            QPushButton:hover:enabled {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(34, 197, 94, 0.4), stop:1 rgba(59, 130, 246, 0.3));
                color: #4ade80;
                border: 1px solid rgba(34, 197, 94, 0.5);
                transform: translateY(-1px);
                box-shadow: 0 2px 8px rgba(34, 197, 94, 0.3);
            }
            QPushButton:pressed:enabled {
                transform: translateY(0px);
                box-shadow: 0 1px 4px rgba(34, 197, 94, 0.2);
            }
            QPushButton:disabled {
                background: rgba(71, 85, 105, 0.2);
                color: #64748b;
                border: 1px solid rgba(71, 85, 105, 0.3);
            }
        """)
        actions_layout.addWidget(self.save_btn)
        
        layout.addWidget(actions_container)
        
        return panel

    # Additional UI Methods
    def toggle_maximize(self):
        """Toggle between normal and maximized window"""
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def toggle_fullscreen(self):
        """Toggle fullscreen mode"""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def on_format_changed(self, format_text):
        """Handle format change in combo box"""
        if not self.current_note:
            return
        
        new_format = format_text.lower()
        if new_format != self.current_note.content_format:
            self.current_note.content_format = new_format
            self.save_btn.setEnabled(True)
            self.update_analytics()

    def on_tab_changed(self, index):
        """Handle tab change to refresh preview"""
        if index == 1:  # Preview tab
            self.render_preview()

    def insert_link(self):
        """Insert a link in the editor"""
        if self.current_note and self.current_note.content_format == 'markdown':
            cursor = self.content_editor.textCursor()
            cursor.insertText("[Link Text](https://example.com)")
        else:
            # HTML mode
            cursor = self.content_editor.textCursor()
            cursor.insertHtml('<a href="https://example.com">Link Text</a>')

    def insert_image(self):
        """Insert an image in the editor"""
        if self.current_note and self.current_note.content_format == 'markdown':
            cursor = self.content_editor.textCursor()
            cursor.insertText("![Alt Text](image_url)")
        else:
            cursor = self.content_editor.textCursor()
            cursor.insertHtml('<img src="image_url" alt="Alt Text" />')

    def insert_code_block(self):
        """Insert a code block"""
        if self.current_note and self.current_note.content_format == 'markdown':
            cursor = self.content_editor.textCursor()
            cursor.insertText("```python\n# Your code here\nprint('Hello, World!')\n```")
        else:
            cursor = self.content_editor.textCursor()
            cursor.insertHtml('<pre><code>// Your code here\nconsole.log("Hello, World!");</code></pre>')

    def quick_open(self):
        """Quick open dialog for notes"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Quick Open")
        dialog.setModal(True)
        dialog.resize(400, 300)
        
        layout = QVBoxLayout(dialog)
        
        search_input = QLineEdit()
        search_input.setPlaceholderText("Type to search notes...")
        layout.addWidget(search_input)
        
        notes_list = QListWidget()
        layout.addWidget(notes_list)
        
        def update_list(text):
            notes_list.clear()
            if text:
                results = self.db.search_note_headers(text)
            else:
                results = self.db.get_all_note_headers()
            
            for note in results[:20]:  # Limit to 20 results
                item = QListWidgetItem(note.title)
                item.setData(Qt.ItemDataRole.UserRole, note.id)
                notes_list.addItem(item)
        
        search_input.textChanged.connect(update_list)
        update_list("")  # Initial load
        
        def open_selected():
            current_item = notes_list.currentItem()
            if current_item:
                note_id = current_item.data(Qt.ItemDataRole.UserRole)
                # Find and select the note in main list
                for i in range(self.notes_list.count()):
                    item = self.notes_list.item(i)
                    if item.data(Qt.ItemDataRole.UserRole) == note_id:
                        self.notes_list.setCurrentItem(item)
                        self.load_selected_note(item)
                        break
                dialog.accept()
        
        notes_list.itemDoubleClicked.connect(lambda: open_selected())
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(open_selected)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        dialog.exec()

    def focus_notes_list(self):
        """Focus the notes list"""
        self.notes_list.setFocus()

    def search_next(self):
        """Search next occurrence"""
        # Implementation for search navigation
        pass

    def search_previous(self):
        """Search previous occurrence"""
        # Implementation for search navigation
        pass

    def show_settings(self):
        """Show settings dialog"""
        dialog = SettingsDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            if dialog.settings_changed:
                QMessageBox.information(self, "Settings", "Settings saved successfully!")
                # Restart timers with new intervals if changed
                self.restart_timers()

    def show_debug_info(self):
        """Show debug information"""
        stats = self.db.get_stats()
        redis_info = f"Redis: {'Enabled' if self.redis_cache.enabled else 'Disabled'}"
        if self.redis_cache.enabled:
            redis_info += f" | Dirty: {self.redis_cache.dirty_count()}"
        
        info = f"""Debug Information:

Database:
• Notes: {stats['total_notes']}
• Tags: {stats['unique_tags']}
• Size: {stats['db_size_kb']} KB

Cache:
• {redis_info}

Current Note:
• Format: {self.current_note.content_format if self.current_note else 'None'}
• Locked: {self.current_note.locked if self.current_note else 'None'}
• Words: {len(self.content_editor.toPlainText().split()) if self.current_note else 0}

Application:
• Version: {app_config.get('APP_VERSION', '1.0') if app_config else '1.0'}
• Discord RPC: {'Enabled' if self.discord.enabled else 'Disabled'}
        """
        
        QMessageBox.information(self, "Debug Information", info)

    def show_help(self):
        """Show help dialog"""
        help_text = """Alem - Smart Notes Help

Keyboard Shortcuts:
• Ctrl+N: New Note
• Ctrl+S: Save Note
• Ctrl+O: Quick Open
• Ctrl+D: Delete Note
• Ctrl+L: Lock/Unlock Note
• Ctrl+F: Search Notes
• Ctrl+1: Edit Mode
• Ctrl+2: Preview Mode
• F5: Refresh Preview
• F11: Toggle Fullscreen

Features:
• Rich text editing with formatting
• Markdown support with live preview
• AI-powered search (when enabled)
• Redis caching for performance
• Discord Rich Presence
• Password protection for notes
• Real-time analytics

Tips:
• Use tags to organize your notes
• Lock sensitive notes with passwords
• Enable AI search for better results
• Use Markdown for better formatting
        """
        
        QMessageBox.information(self, "Help - Alem", help_text)

    def restart_timers(self):
        """Restart timers with updated intervals"""
        if app_config:
            # Auto-save timer
            self.auto_save_timer.stop()
            interval = app_config.get('auto_save_interval', 30000)
            self.auto_save_timer.start(int(interval))
            
            # Redis flush timer
            self.redis_flush_timer.stop()
            flush_s = app_config.get('redis_flush_interval_s', 60)
            self.redis_flush_timer.start(int(flush_s * 1000))

    def update_analytics(self):
        """Update real-time analytics with working widgets"""
        try:
            # Notes count
            stats = self.db.get_stats()
            self.analytics_notes.setText(f"Notes: {stats.get('total_notes', 0)}")
            
            # Current note analytics
            if self.current_note:
                text = self.content_editor.toPlainText()
                words = len([w for w in text.split() if w.strip()])
                chars = len(text)
                
                # Update word count label in editor
                if hasattr(self, 'word_count_label'):
                    self.word_count_label.setText(f"{words} words, {chars} chars")
                
                # Format and lock status
                format_text = self.current_note.content_format.upper()
                lock_status = "Locked" if self.current_note.locked else "Unlocked"
                self.analytics_format.setText(f"Format: {format_text} | {lock_status}")
                
                # Update lock button
                if hasattr(self, 'lock_btn'):
                    self.lock_btn.setChecked(self.current_note.locked)
                    self.lock_btn.setText("🔒" if self.current_note.locked else "🔓")
            else:
                if hasattr(self, 'word_count_label'):
                    self.word_count_label.setText("0 words, 0 chars")
                self.analytics_format.setText("Format: - | -")
            
            # Redis status
            if self.redis_cache.enabled:
                dirty_count = self.redis_cache.dirty_count()
                self.analytics_redis.setText(f"Cache: {dirty_count} dirty")
            else:
                self.analytics_redis.setText("Cache: Off")
            
            # Status indicator
            if hasattr(self, 'last_search_time'):
                if self.last_search_time < 50:
                    self.analytics_status.setText("Fast")
                elif self.last_search_time < 200:
                    self.analytics_status.setText("Good")
                else:
                    self.analytics_status.setText("Slow")
            else:
                self.analytics_status.setText("Ready")
                
        except Exception as e:
            logger.error(f"Error updating analytics: {e}")
            # Set fallback values
            self.analytics_notes.setText("Notes: ?")
            self.analytics_format.setText("Format: - | -")
            self.analytics_redis.setText("Cache: error")
            self.analytics_status.setText("Error")

    # OPTIMIZATION: Lazy loading of note headers
    def load_note_headers(self):
        note_headers = self.db.get_all_note_headers()
        self.refresh_notes_list(note_headers)

    def refresh_notes_list(self, note_headers: List[Note]):
        """Refresh the notes list widget with a given list of note headers."""
        self.notes_list.clear()
        for note in note_headers:
            item_text = f"{note.title}"
            if note.tags:
                item_text += f" #{note.tags.replace(',', ' #')}"

            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, note.id) 
            item.setToolTip(f"Tags: {note.tags}\nCreated: {note.created_at[:10]}")
            self.notes_list.addItem(item)
        
        self.update_stats()


    # OPTIMIZATION: This is the lazy loading in action.
    def load_selected_note(self, item: QListWidgetItem):
        """Load the FULL content of the selected note from DB on demand."""
        note_id = item.data(Qt.ItemDataRole.UserRole)
        
        # Fetch the full note from the database ONLY when it's clicked.
        note = None
        # Try Redis cache first
        rd = self.redis_cache.get_note(note_id)
        if rd:
            try:
                note = Note.from_dict({
                    'id': int(rd.get('id', note_id)),
                    'title': rd.get('title',''),
                    'content': rd.get('content',''),
                    'tags': rd.get('tags',''),
                    'created_at': rd.get('created_at'),
                    'updated_at': rd.get('updated_at'),
                    'locked': str(rd.get('locked','0')) in ('1','True','true'),
                    'content_format': rd.get('content_format','html')
                })
            except Exception:
                note = None
        if not note:
            note = self.db.get_note(note_id)
            if note and self.redis_cache.enabled:
                self.redis_cache.cache_note(note)

        if note:
            self.current_note = note
            self.title_input.setText(note.title)
            self.tags_input.setText(note.tags)
            # Load content based on format and lock
            content_text = note.content
            if note.locked:
                # prompt for password
                pwd = self.prompt_password("Unlock Note", "Enter password to unlock this note:")
                if pwd:
                    try:
                        content_text = decrypt_content(content_text, pwd)
                    except Exception:
                        QMessageBox.critical(self, "Error", "Incorrect password or decryption failed.")
                        content_text = ""
                else:
                    content_text = ""
            if note.content_format == 'html':
                if content_text.strip().startswith('<'):
                    self.content_editor.setHtml(content_text)
                else:
                    self.content_editor.setPlainText(content_text)
            else:
                # markdown: edit raw text
                self.content_editor.setPlainText(content_text)
            
            self.save_btn.setEnabled(False)
            self.set_status(f"Loaded: '{note.title}'")
            self.render_preview()
            self.update_analytics()

    def new_note(self):
        """Create a new note"""
        default_fmt = (app_config.get('default_content_format','html') if app_config else 'html')
        default_content = "# Start writing here..." if default_fmt == 'markdown' else "<p>Start writing here...</p>"
        self.current_note = Note(title="New Note", content=default_content, content_format=default_fmt)
        self.title_input.setText(self.current_note.title)
        self.tags_input.setText("")
        if self.current_note.content_format == 'html':
            self.content_editor.setHtml(self.current_note.content)
        else:
            self.content_editor.setPlainText(self.current_note.content)
        self.title_input.setFocus()
        self.title_input.selectAll()
        self.save_btn.setEnabled(True)
        self.notes_list.setCurrentItem(None) # Deselect item in list
        self.render_preview()
        self.update_analytics()

    def save_note(self):
        """Save the current note"""
        if not self.current_note:
            return

        self.current_note.title = self.title_input.text().strip() or "Untitled"
        # Capture content based on format
        if self.current_note.content_format == 'html':
            self.current_note.content = self.content_editor.toHtml()
        else:
            self.current_note.content = self.content_editor.toPlainText()
        self.current_note.tags = self.tags_input.text().strip()
        self.current_note.updated_at = datetime.now().isoformat()

        # If locked, ensure encryption before persisting/caching
        if self.current_note.locked:
            pwd = self.prompt_password("Confirm Password", "Enter password to encrypt before saving:")
            if not pwd:
                QMessageBox.warning(self, "Warning", "Save cancelled: password required for locked notes.")
                return
            try:
                iters = app_config.get('kdf_iterations', 390000) if app_config else 390000
                enc = encrypt_content(self.current_note.content, pwd, iters)
                self.current_note.content = enc
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Encryption failed: {e}")
                return

        if self.redis_cache.enabled:
            self.redis_cache.cache_note(self.current_note)
        else:
            self.db.save_note(self.current_note)
        self.load_note_headers()
        self.save_btn.setEnabled(False)
        self.set_status(f"Saved: '{self.current_note.title}'")
        self.update_analytics()

    def delete_note(self):
        """Delete the selected note"""
        current_item = self.notes_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Warning", "Please select a note to delete.")
            return

        note_id = current_item.data(Qt.ItemDataRole.UserRole)
        # We don't need to fetch the full note just to get its title for the dialog
        title = current_item.text().split(' #')[0] 

        reply = QMessageBox.question(
            self, "Delete Note", 
            f"Are you sure you want to delete '{title}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.db.delete_note(note_id)
            self.load_note_headers() 
            self.clear_editor()
            self.set_status(f"Deleted: '{title}'")
            self.update_analytics()

    def clear_editor(self):
        """Clear the editor"""
        self.title_input.clear()
        self.tags_input.clear()
        self.content_editor.clear()
        self.current_note = None
        self.save_btn.setEnabled(False)

    def on_content_changed(self):
        """Handle content changes"""
        if not self.current_note:
            self.new_note()
        self.save_btn.setEnabled(True)
        # live preview debounce
        self.preview_timer.stop()
        self.preview_timer.start(250)
        self.update_analytics()

    def on_search(self, text):
        if not text.strip():
            self.load_note_headers()
            return
        
        self.last_search_query = text.strip()
        self.search_timer.stop()
        self.search_timer.start(300)  # 300ms delay for debouncing

    def _perform_delayed_search(self):
        """Perform the actual search after debounce delay"""
        if self.last_search_query:
            self.perform_search(self.last_search_query)

    def perform_search(self, query: str):
        """Enhanced search with timing and better feedback"""
        start_time = time.time()
        
        # Show progress
        self.operation_progress.setVisible(True)
        self.operation_progress.setRange(0, 0)  # Indeterminate progress
        
        try:
            results = self.db.search_note_headers(query)
            self.refresh_notes_list(results)
            
            search_time = round((time.time() - start_time) * 1000, 1)
            self.last_search_time = search_time
            
            search_type = "🤖 AI Search" if self.ai_toggle.isChecked() else "🔍 Text Search"
            
            self.set_status(f"{search_type}: {len(results)} results for '{query}' ({search_time}ms)")
            # Update search time in status bar
            self.set_status(f"Search completed in {search_time}ms", 2000)
            
            # Update performance indicator
            if search_time < 50:
                performance = "Blazing"
            elif search_time < 100:
                performance = "Fast"
            elif search_time < 300:
                performance = "Good"
            else:
                performance = "Slow"
            
            self.analytics_status.setText(performance)
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            self.set_status(f"Search error: {e}")
        finally:
            self.operation_progress.setVisible(False)
            self.update_analytics()

    def show_about(self):
            """Alem v1.0
Smart Note-Taking Application

A minimalist, AI-enhanced note-taking app designed for developers and professionals.

Features:
• Rich text editing with formatting tools
• AI-powered semantic search
• Tag-based organization
• Lightweight and fast performance
• Offline-first design
• Professional, glassmorphism UI

Built with PyQt6 and SQLite
Optimized for productivity and performance

© 2025 Alem Team"""
        
    def toggle_bold(self):
        """Toggle bold formatting"""
        fmt = self.content_editor.currentCharFormat()
        if fmt.fontWeight() == QFont.Weight.Bold:
            fmt.setFontWeight(QFont.Weight.Normal)
        else:
            fmt.setFontWeight(QFont.Weight.Bold)
            fmt.setFontWeight(QFont.Weight.Bold)
        self.content_editor.setCurrentCharFormat(fmt)
        self.content_editor.setFocus()
        self.update_analytics()


    def toggle_italic(self):
        fmt = self.content_editor.currentCharFormat()
        fmt.setFontItalic(not fmt.fontItalic())
        fmt.setFontItalic(not fmt.fontItalic())
        self.content_editor.setCurrentCharFormat(fmt)
        self.content_editor.setFocus()
        self.update_analytics()

    def toggle_underline(self):
        fmt = self.content_editor.currentCharFormat()
        fmt.setFontUnderline(not fmt.fontUnderline())
        fmt.setFontUnderline(not fmt.fontUnderline())
        self.content_editor.setCurrentCharFormat(fmt)
        self.content_editor.setFocus()
        self.update_analytics()

    def set_alignment(self, alignment):
        self.content_editor.setAlignment(alignment)
        self.content_editor.setFocus()

    def decrease_font_size(self):
        """Decrease font size"""
        current_font = self.content_editor.currentFont()
        size = current_font.pointSize()
        if size > 8:  # Minimum font size
            current_font.setPointSize(size - 1)
            self.content_editor.setCurrentFont(current_font)
        self.content_editor.setFocus()

    def increase_font_size(self):
        """Increase font size"""
        current_font = self.content_editor.currentFont()
        size = current_font.pointSize()
        if size < 24:  # Maximum font size
            current_font.setPointSize(size + 1)
            self.content_editor.setCurrentFont(current_font)
        self.content_editor.setFocus()

    def update_format_buttons(self):
        """Update toolbar buttons based on current formatting"""
        # Skip if formatting buttons don't exist yet (they're not implemented in current UI)
        try:
            fmt = self.content_editor.currentCharFormat()
            
            # Update bold button if it exists
            if hasattr(self, 'bold_btn'):
                self.bold_btn.setChecked(fmt.fontWeight() == QFont.Weight.Bold)
            
            # Update italic button if it exists
            if hasattr(self, 'italic_btn'):
                self.italic_btn.setChecked(fmt.fontItalic())
            
            # Update underline button if it exists
            if hasattr(self, 'underline_btn'):
                self.underline_btn.setChecked(fmt.fontUnderline())
        except Exception:
            # Silently ignore if formatting buttons aren't ready
            pass

    def render_preview(self):
        """Enhanced markdown and HTML preview rendering"""
        if not self.current_note:
            if hasattr(self.preview_view, 'setHtml'):
                self.preview_view.setHtml("")
            else:
                self.preview_view.setPlainText("")
            return
        
        content = self.content_editor.toPlainText() if self.current_note.content_format == 'markdown' else self.content_editor.toHtml()
        
        if self.current_note.content_format == 'markdown':
            if md is None:
                # Fallback to plain text if markdown not available
                if hasattr(self.preview_view, 'setHtml'):
                    self.preview_view.setHtml(f"<pre>{content}</pre>")
                else:
                    self.preview_view.setPlainText(content)
                return
            
            try:
                # Get extensions from config
                extensions = app_config.get('markdown_extensions', ["fenced_code", "tables", "toc"]) if app_config else ["fenced_code", "tables"]
                
                # Convert markdown to HTML
                html_content = md.markdown(content, extensions=extensions)
                
                # Apply dark theme CSS for better appearance
                styled_html = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="utf-8">
                    <style>
                        body {{
                            background: rgba(15, 23, 42, 0.9);
                            color: #f1f5f9;
                            font-family: 'Segoe UI', system-ui, sans-serif;
                            line-height: 1.6;
                            padding: 24px;
                            margin: 0;
                        }}
                        h1, h2, h3, h4, h5, h6 {{
                            color: #93c5fd;
                            margin-top: 1.5em;
                            margin-bottom: 0.5em;
                            font-weight: 600;
                        }}
                        h1 {{ font-size: 2em; border-bottom: 2px solid rgba(59, 130, 246, 0.3); padding-bottom: 0.3em; }}
                        h2 {{ font-size: 1.6em; border-bottom: 1px solid rgba(59, 130, 246, 0.2); padding-bottom: 0.2em; }}
                        p {{ margin-bottom: 1em; }}
                        a {{
                            color: #60a5fa;
                            text-decoration: none;
                            border-bottom: 1px solid rgba(96, 165, 250, 0.3);
                        }}
                        a:hover {{
                            color: #93c5fd;
                            border-bottom-color: rgba(147, 197, 253, 0.6);
                        }}
                        code {{
                            background: rgba(30, 41, 59, 0.8);
                            color: #fbbf24;
                            padding: 2px 6px;
                            border-radius: 4px;
                            font-family: 'Consolas', 'Monaco', monospace;
                            font-size: 0.9em;
                        }}
                        pre {{
                            background: rgba(30, 41, 59, 0.8);
                            border: 1px solid rgba(51, 65, 85, 0.3);
                            border-radius: 8px;
                            padding: 16px;
                            overflow-x: auto;
                            margin: 1em 0;
                        }}
                        pre code {{
                            background: transparent;
                            padding: 0;
                            color: #e2e8f0;
                        }}
                        blockquote {{
                            border-left: 4px solid rgba(59, 130, 246, 0.5);
                            padding-left: 16px;
                            margin: 1em 0;
                            color: #cbd5e1;
                            font-style: italic;
                            background: rgba(30, 41, 59, 0.3);
                            border-radius: 0 8px 8px 0;
                            padding: 12px 16px;
                        }}
                        table {{
                            border-collapse: collapse;
                            width: 100%;
                            margin: 1em 0;
                            border: 1px solid rgba(51, 65, 85, 0.3);
                            border-radius: 8px;
                            overflow: hidden;
                        }}
                        th, td {{
                            border: 1px solid rgba(51, 65, 85, 0.3);
                            padding: 12px;
                            text-align: left;
                        }}
                        th {{
                            background: rgba(59, 130, 246, 0.2);
                            color: #93c5fd;
                            font-weight: 600;
                        }}
                        tr:nth-child(even) {{
                            background: rgba(30, 41, 59, 0.3);
                        }}
                        ul, ol {{
                            padding-left: 1.5em;
                            margin: 1em 0;
                        }}
                        li {{
                            margin-bottom: 0.5em;
                        }}
                        hr {{
                            border: none;
                            height: 2px;
                            background: linear-gradient(90deg, rgba(59, 130, 246, 0.5), rgba(139, 92, 246, 0.3));
                            margin: 2em 0;
                            border-radius: 1px;
                        }}
                        img {{
                            max-width: 100%;
                            height: auto;
                            border-radius: 8px;
                            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
                        }}
                        .codehilite {{
                            background: rgba(30, 41, 59, 0.8);
                            border-radius: 8px;
                            padding: 16px;
                            overflow-x: auto;
                        }}
                    </style>
                </head>
                <body>
                    {html_content}
                </body>
                </html>
                """
                
                if hasattr(self.preview_view, 'setHtml'):
                    self.preview_view.setHtml(styled_html)
                else:
                    self.preview_view.setHtml(styled_html)
                    
            except Exception as e:
                logger.error(f"Markdown rendering error: {e}")
                # Fallback to plain text
                if hasattr(self.preview_view, 'setHtml'):
                    self.preview_view.setHtml(f"<pre style='color: #f1f5f9; background: rgba(15, 23, 42, 0.9); padding: 20px;'>{content}</pre>")
                else:
                    self.preview_view.setPlainText(content)
        else:
            # HTML content - just mirror current editor HTML with enhanced styling
            styled_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <style>
                    body {{
                        background: rgba(15, 23, 42, 0.9);
                        color: #f1f5f9;
                        font-family: 'Segoe UI', system-ui, sans-serif;
                        line-height: 1.6;
                        padding: 24px;
                        margin: 0;
                    }}
                </style>
            </head>
            <body>
                {content}
            </body>
            </html>
            """
            
            if hasattr(self.preview_view, 'setHtml'):
                self.preview_view.setHtml(styled_content)
            else:
                self.preview_view.setHtml(content)

    # This method is now handled by the main update_analytics method above

    def toggle_lock_current(self):
        if not self.current_note:
            return
        if self.current_note.locked:
            # unlock
            pwd = self.prompt_password("Unlock Note", "Enter password to unlock:")
            if not pwd:
                return
            try:
                plain = decrypt_content(self.current_note.content, pwd)
                self.current_note.locked = False
                # load plaintext into editor
                if self.current_note.content_format == 'html' and plain.strip().startswith('<'):
                    self.content_editor.setHtml(plain)
                else:
                    self.content_editor.setPlainText(plain)
                self.save_btn.setEnabled(True)
            except Exception:
                QMessageBox.critical(self, "Error", "Incorrect password.")
                return
        else:
            if Fernet is None:
                QMessageBox.warning(self, "Unavailable", "Cryptography not installed. Install 'cryptography' to lock notes.")
                return
            pwd = self.prompt_password("Lock Note", "Set a password to lock this note:", confirm=True)
            if not pwd:
                return
            # will encrypt on save
            self.current_note.locked = True
            self.save_btn.setEnabled(True)
        self.update_analytics()

    def prompt_password(self, title: str, label: str, confirm: bool = False) -> Optional[str]:
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        form = QFormLayout(dlg)
        inp1 = QLineEdit()
        inp1.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow(QLabel(label), inp1)
        inp2 = None
        if confirm:
            inp2 = QLineEdit()
            inp2.setEchoMode(QLineEdit.EchoMode.Password)
            form.addRow(QLabel("Confirm password:"), inp2)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        form.addRow(btns)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            p1 = inp1.text()
            if confirm:
                if p1 and inp2 and p1 == inp2.text():
                    return p1
                else:
                    QMessageBox.warning(self, "Mismatch", "Passwords do not match.")
                    return None
            return p1
        return None

    def flush_cache_periodic(self):
        if not self.redis_cache.enabled:
            return
        try:
            flushed, errors = self.redis_cache.flush_to_db(self.db)
            if flushed:
                self.set_status(f"Flushed {flushed} note(s) to DB from cache", 2000)
            self.update_analytics()
        except Exception as e:
            logger.error(f"Cache flush failed: {e}")

    def update_stats(self):
        """Update statistics display"""
        try:
            stats = self.db.get_stats()
            self.notes_count_label.setText(f"Notes: {stats['total_notes']}")
            self.db_size_label.setText(f"Database: {stats['db_size_kb']} KB")
            
            # Update cache status
            if self.redis_cache.enabled:
                dirty_count = self.redis_cache.dirty_count()
                self.cache_label.setText(f"Cache: {dirty_count} dirty")
            else:
                self.cache_label.setText("Cache: Off")
        except Exception as e:
            logger.error(f"Error updating stats: {e}")
            self.notes_count_label.setText("Notes: ?")
            self.db_size_label.setText("Database: ? KB")
            self.cache_label.setText("Cache: Error")

    def auto_save(self):
        """Auto-save current note if modified"""
        try:
            if self.current_note and self.save_btn.isEnabled():
                self.save_note()
                self.set_status("Auto-saved", 2000)
        except Exception as e:
            logger.error(f"Auto-save failed: {e}")

    def closeEvent(self, event):
        """Handle application close with auto-save"""
        if self.current_note and self.save_btn.isEnabled():
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "You have unsaved changes. Save before closing?",
                QMessageBox.StandardButton.Save | 
                QMessageBox.StandardButton.Discard | 
                QMessageBox.StandardButton.Cancel
            )
            
            if reply == QMessageBox.StandardButton.Save:
                self.save_note()
            elif reply == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
        
        # Stop timers
        self.auto_save_timer.stop()
        self.search_timer.stop()
        self.redis_flush_timer.stop()
        # Final flush to DB from Redis
        try:
            self.flush_cache_periodic()
        except Exception:
            pass
        # Close Discord RPC
        try:
            self.discord.close()
        except Exception:
            pass
        
        # Save window geometry
        settings = QApplication.instance().settings if hasattr(QApplication.instance(), 'settings') else None
        if settings:
            settings.setValue("geometry", self.saveGeometry())
            settings.setValue("windowState", self.saveState())
        
        event.accept()
def main():
    """Enhanced main application entry point"""
    import sys
    from PyQt6.QtCore import QSettings
    
    # Set up application with enhanced properties
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setApplicationName("Alem")
    app.setApplicationVersion("2.0.0")
    app.setApplicationDisplayName("Alem - Smart Notes")
    app.setOrganizationName("Alem")
    app.setOrganizationDomain("alem.dev")
    
    # App icon
    try:
        icon_path = Path(__file__).parent / "alem.png"
        if icon_path.exists():
            app.setWindowIcon(QIcon(str(icon_path)))
            # Set taskbar icon on Windows
            if hasattr(app, 'setWindowIcon'):
                app.setWindowIcon(QIcon(str(icon_path)))
        else:
            logger.warning(f"App icon not found at: {icon_path}")
    except Exception as e:
        logger.warning(f"Could not set app icon: {e}")
    
    # High DPI support
    try:
        if hasattr(Qt.ApplicationAttribute, 'AA_EnableHighDpiScaling'):
            app.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
        if hasattr(Qt.ApplicationAttribute, 'AA_UseHighDpiPixmaps'):
            app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    except AttributeError:
        pass
    
    # Settings
    settings = QSettings()
    app.settings = settings
    
    try:
        # Create and show main window
        window = SmartNotesApp()
        
        # Restore window geometry
        geometry = settings.value("geometry")
        if geometry:
            window.restoreGeometry(geometry)
        else:
            # Center window on screen
            screen = app.primaryScreen().availableGeometry()
            x = (screen.width() - window.width()) // 2
            y = (screen.height() - window.height()) // 2
            window.move(x, y)
        
        window_state = settings.value("windowState")
        if window_state:
            window.restoreState(window_state)
        
        window.show()
        
        # Discord presence updates
        if window.discord.enabled:
            rpc_timer = QTimer()
            rpc_timer.timeout.connect(lambda: window.discord.update(
                state="Taking smart notes", 
                details="Alem - Enhanced productivity"
            ))
            interval = (app_config.get('discord_update_interval_s', 15) if app_config else 15)
            rpc_timer.start(int(interval * 1000))
            window.rpc_timer = rpc_timer
        
        # Handle command line arguments
        if len(sys.argv) > 1 and "--test" in sys.argv:
            QTimer.singleShot(3000, app.quit)
            logger.info("Test mode: Application will close in 3 seconds")
        
        # Setup global exception handler for better error reporting
        def handle_exception(exc_type, exc_value, exc_traceback):
            if issubclass(exc_type, KeyboardInterrupt):
                sys.__excepthook__(exc_type, exc_value, exc_traceback)
                return
            
            logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
            
            # Show user-friendly error dialog
            error_msg = f"An unexpected error occurred:\n\n{exc_type.__name__}: {exc_value}"
            QMessageBox.critical(None, "Application Error", error_msg)
        
        sys.excepthook = handle_exception
        
        # Show welcome message for first-time users
        if not settings.value("first_run_completed", False):
            welcome_msg = """Welcome to Alem 2.0! 🌟

New Features:
• Glassmorphism UI with modern design
• Enhanced keyboard shortcuts (Windows-style)
• Better Markdown rendering with live preview
• Real-time analytics in status bar
• Discord Rich Presence support
• Redis caching for improved performance
• Password protection for sensitive notes
• Comprehensive settings panel

Press F1 anytime for help!
            """
            QMessageBox.information(window, "Welcome to Alem 2.0", welcome_msg)
            settings.setValue("first_run_completed", True)
        
        sys.exit(app.exec())
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        QMessageBox.critical(None, "Fatal Error", f"Application failed to start:\n{e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
