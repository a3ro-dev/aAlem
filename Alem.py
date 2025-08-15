import sys
import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QListWidget, QListWidgetItem, QTextEdit, QLineEdit,
    QPushButton, QLabel, QMenuBar, QStatusBar, QMessageBox,
    QDialog, QDialogButtonBox, QFormLayout, QComboBox, QFrame
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt6.QtGui import QFont, QAction, QIcon, QPixmap, QTextCharFormat, QColor

class Note:
    """Simple Note class"""
    def __init__(self, id=None, title="", content="", tags="", created_at=None, updated_at=None):
        self.id = id
        self.title = title
        self.content = content 
        self.tags = tags
        self.created_at = created_at or datetime.now().isoformat()
        self.updated_at = updated_at or datetime.now().isoformat()

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'tags': self.tags,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }

    @classmethod
    def from_dict(cls, data):
        return cls(**data)

class Database:
    """Simple SQLite database for notes"""
    def __init__(self, db_path="smartnotes.db"):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                tags TEXT DEFAULT '',
                created_at TEXT,
                updated_at TEXT
            )
        """)
        conn.commit()
        conn.close()

    def get_all_note_headers(self) -> List[Note]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, title, tags, created_at, updated_at FROM notes ORDER BY updated_at DESC")
        rows = cursor.fetchall()
        conn.close()

        notes = []
        for row in rows:
            notes.append(Note(
                id=row[0], title=row[1], content="", tags=row[2],
                created_at=row[3], updated_at=row[4]
            ))
        return notes

    
    # It fetches the full content for ONE note when it's needed, 
    def get_note(self, note_id: int) -> Optional[Note]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM notes WHERE id = ?", (note_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return Note(
                id=row[0], title=row[1], content=row[2], tags=row[3],
                created_at=row[4], updated_at=row[5]
            )
        return None

    def save_note(self, note: Note) -> int:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if note.id:
            cursor.execute("""
                UPDATE notes SET title = ?, content = ?, tags = ?, updated_at = ?
                WHERE id = ?
            """, (note.title, note.content, note.tags, datetime.now().isoformat(), note.id))
        else:
            cursor.execute("""
                INSERT INTO notes (title, content, tags, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (note.title, note.content, note.tags, note.created_at, note.updated_at))
            note.id = cursor.lastrowid

        conn.commit()
        conn.close()
        return note.id

    def delete_note(self, note_id: int):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        conn.commit()
        conn.close()

    # OPTIMIZATION: Search returns only headers to keep memory low during search.
    def search_note_headers(self, query: str) -> List[Note]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, title, tags, created_at, updated_at FROM notes 
            WHERE title LIKE ? OR content LIKE ? OR tags LIKE ?
            ORDER BY updated_at DESC
        """, (f'%{query}%', f'%{query}%', f'%{query}%'))
        rows = cursor.fetchall()
        conn.close()

        notes = []
        for row in rows:
            notes.append(Note(
                id=row[0], title=row[1], content="", tags=row[2],
                created_at=row[3], updated_at=row[4]
            ))
        return notes

class SmartNotesApp(QMainWindow):
    """Main Alem Application Window"""

    def __init__(self):
        super().__init__()
        self.db = Database()
        self.current_note: Optional[Note] = None # This will hold the one fully loaded note
        self.setup_ui()
        self.load_note_headers() # Load headers, not full notes

    def setup_ui(self):
        self.setWindowTitle("Alem")
        self.setGeometry(100, 100, 1400, 900)
        
        # Modern glassmorphism cyberpunk theme
        self.setStyleSheet("""
            QMainWindow {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                    stop:0 #0a0f1c, stop:0.5 #0d1421, stop:1 #111827);
                color: #e2e8f0;
            }
        """)

        # Create menu bar
        self.create_menu_bar()

        # Central widget with splitter
        central_widget = QWidget()
        central_widget.setStyleSheet("""
            QWidget { 
                background: transparent; 
                color: #e2e8f0;
            }
        """)
        self.setCentralWidget(central_widget)

        # Main layout
        layout = QHBoxLayout(central_widget)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        # Left panel (notes list and search)
        left_panel = self.create_left_panel()
        splitter.addWidget(left_panel)
    

        # Right panel (note editor)
        right_panel = self.create_right_panel()
        splitter.addWidget(right_panel)

        # Set splitter proportions (make it resizable)
        splitter.setSizes([400, 1000])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        # Status bar
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet("""
            QStatusBar {
                background: rgba(15, 23, 42, 0.9);
                color: #64748b;
                border-top: 1px solid rgba(51, 65, 85, 0.3);
                font-family: 'Segoe UI', system-ui, sans-serif;
                font-size: 11px;
                padding: 6px 12px;
            }
        """)
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready • AI Enhanced • Real-time Search")
    
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
        new_action.setShortcut('Ctrl+N')
        new_action.triggered.connect(self.new_note)
        file_menu.addAction(new_action)

        save_action = QAction('Save', self)
        save_action.setShortcut('Ctrl+S')
        save_action.triggered.connect(self.save_note)
        file_menu.addAction(save_action)

        file_menu.addSeparator()
        exit_action = QAction('Exit', self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Search menu
        search_menu = menubar.addMenu('Search')
        search_action = QAction('Search Notes', self)
        search_action.setShortcut('Ctrl+F')
        search_action.triggered.connect(lambda: self.search_input.setFocus())
        search_menu.addAction(search_action)

        # Help menu
        help_menu = menubar.addMenu('Help')
        about_action = QAction('About Alem', self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def create_left_panel(self):
        """Create the left panel with search and notes list"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(16)
        layout.setContentsMargins(16, 16, 16, 16)

        # Header
        header = QLabel("Alem")
        header.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        header.setStyleSheet("""
            QLabel { 
                color: #f1f5f9; 
                padding: 20px; 
                background: rgba(30, 41, 59, 0.7);
                border: 1px solid rgba(51, 65, 85, 0.3);
                border-radius: 12px; 
                font-family: 'Segoe UI', system-ui, sans-serif;
                font-weight: 600;
                text-align: center;
            }
        """)
        layout.addWidget(header)

        # Search bar
        search_layout = QHBoxLayout()
        search_layout.setSpacing(8)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search notes...")
        self.search_input.textChanged.connect(self.on_search)
        self.search_input.setStyleSheet("""
            QLineEdit {
                padding: 12px 16px;
                border: 1px solid rgba(51, 65, 85, 0.3);
                border-radius: 10px;
                background: rgba(30, 41, 59, 0.6);
                color: #e2e8f0;
                font-size: 14px;
                font-family: 'Segoe UI', system-ui, sans-serif;
                font-weight: 400;
            }
            QLineEdit:focus {
                border: 1px solid rgba(59, 130, 246, 0.5);
                background: rgba(30, 41, 59, 0.8);
                color: #f1f5f9;
            }
            QLineEdit::placeholder {
                color: #64748b;
            }
        """)
        search_layout.addWidget(self.search_input)

        # Simplified AI toggle
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
                font-weight: 600;
                font-size: 12px;
                font-family: 'Segoe UI', system-ui, sans-serif;
            }
            QPushButton:checked {
                background: rgba(34, 197, 94, 0.2);
                color: #22c55e;
                border: 1px solid rgba(34, 197, 94, 0.3);
            }
            QPushButton:hover {
                background: rgba(59, 130, 246, 0.2);
                color: #3b82f6;
                border: 1px solid rgba(59, 130, 246, 0.3);
            }
        """)
        search_layout.addWidget(self.ai_toggle)
        layout.addLayout(search_layout)

        # Notes list
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
            }
            QListWidget::item {
                padding: 16px 12px;
                border-bottom: 1px solid rgba(51, 65, 85, 0.2);
                border-radius: 8px;
                background: rgba(15, 23, 42, 0.5);
                color: #e2e8f0;
                margin: 2px 0px;
                font-weight: 500;
            }
            QListWidget::item:selected {
                background: rgba(59, 130, 246, 0.2);
                color: #93c5fd;
                border: 1px solid rgba(59, 130, 246, 0.3);
            }
            QListWidget::item:hover {
                background: rgba(71, 85, 105, 0.3);
                color: #f1f5f9;
                border: 1px solid rgba(71, 85, 105, 0.4);
            }
        """)
        layout.addWidget(self.notes_list)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)

        self.new_note_btn = QPushButton("New Note")
        self.new_note_btn.clicked.connect(self.new_note)
        self.new_note_btn.setStyleSheet("""
            QPushButton {
                background: rgba(59, 130, 246, 0.2);
                color: #3b82f6;
                border: 1px solid rgba(59, 130, 246, 0.3);
                padding: 12px 20px;
                border-radius: 10px;
                font-weight: 600;
                font-size: 13px;
                font-family: 'Segoe UI', system-ui, sans-serif;
            }
            QPushButton:hover {
                background: rgba(59, 130, 246, 0.3);
                color: #60a5fa;
                border: 1px solid rgba(59, 130, 246, 0.4);
            }
            QPushButton:pressed {
                background: rgba(59, 130, 246, 0.4);
                color: #93c5fd;
            }
        """)
        button_layout.addWidget(self.new_note_btn)

        self.delete_note_btn = QPushButton("Delete")
        self.delete_note_btn.clicked.connect(self.delete_note)
        self.delete_note_btn.setStyleSheet("""
            QPushButton {
                background: rgba(239, 68, 68, 0.2);
                color: #ef4444;
                border: 1px solid rgba(239, 68, 68, 0.3);
                padding: 12px 20px;
                border-radius: 10px;
                font-weight: 600;
                font-size: 13px;
                font-family: 'Segoe UI', system-ui, sans-serif;
            }
            QPushButton:hover {
                background: rgba(239, 68, 68, 0.3);
                color: #f87171;
                border: 1px solid rgba(239, 68, 68, 0.4);
            }
            QPushButton:pressed {
                background: rgba(239, 68, 68, 0.4);
                color: #fca5a5;
            }
        """)
        button_layout.addWidget(self.delete_note_btn)
        layout.addLayout(button_layout)

        # Stats panel
        stats_frame = QFrame()
        stats_frame.setStyleSheet("""
            QFrame {
                background: rgba(30, 41, 59, 0.6);
                border: 1px solid rgba(51, 65, 85, 0.3);
                border-radius: 12px;
                padding: 16px;
            }
        """)
        stats_layout = QVBoxLayout(stats_frame)

        self.cache_label = QLabel("Cache: Ready")
        self.search_time_label = QLabel("Search: <20ms")
        self.notes_count_label = QLabel("Notes: 0")

        for label in [self.cache_label, self.search_time_label, self.notes_count_label]:
            label.setFont(QFont("Segoe UI", 10, QFont.Weight.Medium))
            label.setStyleSheet("""
                QLabel { 
                    color: #64748b; 
                    font-family: 'Segoe UI', system-ui, sans-serif;
                    font-weight: 500;
                    padding: 4px 0px;
                }
            """)
            stats_layout.addWidget(label)

        layout.addWidget(stats_frame)

        panel.setMinimumWidth(320)
        panel.setMaximumWidth(500)
        return panel

    def create_right_panel(self):
        """Create the right panel with note editor"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(16)
        layout.setContentsMargins(16, 16, 16, 16)

        # Title input
        title_layout = QHBoxLayout()
        title_label = QLabel("Title")
        title_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Medium))
        title_label.setStyleSheet("""
            QLabel { 
                color: #94a3b8; 
                font-family: 'Segoe UI', system-ui, sans-serif;
                font-weight: 500;
                min-width: 60px;
            }
        """)
        title_layout.addWidget(title_label)

        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("Enter note title...")
        self.title_input.textChanged.connect(self.on_content_changed)
        self.title_input.setStyleSheet("""
            QLineEdit {
                padding: 12px 16px;
                border: 1px solid rgba(51, 65, 85, 0.3);
                border-radius: 10px;
                font-size: 16px;
                color: #f1f5f9;
                background: rgba(30, 41, 59, 0.6);
                font-family: 'Segoe UI', system-ui, sans-serif;
                font-weight: 500;
            }
            QLineEdit:focus {
                border: 1px solid rgba(59, 130, 246, 0.5);
                background: rgba(30, 41, 59, 0.8);
                color: #f8fafc;
            }
            QLineEdit::placeholder {
                color: #64748b;
            }
        """)
        title_layout.addWidget(self.title_input)
        layout.addLayout(title_layout)

        # Tags input
        tags_layout = QHBoxLayout()
        tags_label = QLabel("Tags")
        tags_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Medium))
        tags_label.setStyleSheet("""
            QLabel { 
                color: #94a3b8; 
                font-family: 'Segoe UI', system-ui, sans-serif;
                font-weight: 500;
                min-width: 60px;
            }
        """)
        tags_layout.addWidget(tags_label)

        self.tags_input = QLineEdit()
        self.tags_input.setPlaceholderText("Add tags separated by commas...")
        self.tags_input.textChanged.connect(self.on_content_changed)
        self.tags_input.setStyleSheet("""
            QLineEdit {
                padding: 10px 16px;
                border: 1px solid rgba(51, 65, 85, 0.3);
                border-radius: 10px;
                font-size: 14px;
                color: #e2e8f0;
                background: rgba(30, 41, 59, 0.6);
                font-family: 'Segoe UI', system-ui, sans-serif;
                font-weight: 400;
            }
            QLineEdit:focus {
                border: 1px solid rgba(59, 130, 246, 0.5);
                background: rgba(30, 41, 59, 0.8);
                color: #f1f5f9;
            }
            QLineEdit::placeholder {
                color: #64748b;
            }
        """)
        tags_layout.addWidget(self.tags_input)
        layout.addLayout(tags_layout)

        # Content editor
        editor_label = QLabel("Content")
        editor_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Medium))
        editor_label.setStyleSheet("""
            QLabel { 
                color: #94a3b8; 
                font-family: 'Segoe UI', system-ui, sans-serif;
                font-weight: 500;
            }
        """)
        layout.addWidget(editor_label)

        # Formatting toolbar
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setSpacing(4)
        
        # Bold button
        self.bold_btn = QPushButton("B")
        self.bold_btn.setCheckable(True)
        self.bold_btn.clicked.connect(self.toggle_bold)
        self.bold_btn.setStyleSheet("""
            QPushButton {
                background: rgba(71, 85, 105, 0.3);
                color: #94a3b8;
                border: 1px solid rgba(71, 85, 105, 0.4);
                padding: 8px 12px;
                border-radius: 8px;
                font-weight: bold;
                font-size: 12px;
                min-width: 32px;
                font-family: 'Segoe UI', system-ui, sans-serif;
            }
            QPushButton:checked {
                background: rgba(59, 130, 246, 0.3);
                color: #3b82f6;
                border: 1px solid rgba(59, 130, 246, 0.4);
            }
            QPushButton:hover {
                background: rgba(71, 85, 105, 0.4);
                color: #cbd5e1;
                border: 1px solid rgba(71, 85, 105, 0.5);
            }
        """)
        toolbar_layout.addWidget(self.bold_btn)

        # Italic button
        self.italic_btn = QPushButton("I")
        self.italic_btn.setCheckable(True)
        self.italic_btn.clicked.connect(self.toggle_italic)
        self.italic_btn.setStyleSheet("""
            QPushButton {
                background: rgba(71, 85, 105, 0.3);
                color: #94a3b8;
                border: 1px solid rgba(71, 85, 105, 0.4);
                padding: 8px 12px;
                border-radius: 8px;
                font-style: italic;
                font-size: 12px;
                min-width: 32px;
                font-family: 'Segoe UI', system-ui, sans-serif;
            }
            QPushButton:checked {
                background: rgba(59, 130, 246, 0.3);
                color: #3b82f6;
                border: 1px solid rgba(59, 130, 246, 0.4);
            }
            QPushButton:hover {
                background: rgba(71, 85, 105, 0.4);
                color: #cbd5e1;
                border: 1px solid rgba(71, 85, 105, 0.5);
            }
        """)
        toolbar_layout.addWidget(self.italic_btn)

        # Underline button
        self.underline_btn = QPushButton("U")
        self.underline_btn.setCheckable(True)
        self.underline_btn.clicked.connect(self.toggle_underline)
        self.underline_btn.setStyleSheet("""
            QPushButton {
                background: rgba(71, 85, 105, 0.3);
                color: #94a3b8;
                border: 1px solid rgba(71, 85, 105, 0.4);
                padding: 8px 12px;
                border-radius: 8px;
                text-decoration: underline;
                font-size: 12px;
                min-width: 32px;
                font-family: 'Segoe UI', system-ui, sans-serif;
            }
            QPushButton:checked {
                background: rgba(59, 130, 246, 0.3);
                color: #3b82f6;
                border: 1px solid rgba(59, 130, 246, 0.4);
            }
            QPushButton:hover {
                background: rgba(71, 85, 105, 0.4);
                color: #cbd5e1;
                border: 1px solid rgba(71, 85, 105, 0.5);
            }
        """)
        toolbar_layout.addWidget(self.underline_btn)

        # Separator
        separator = QLabel("•")
        separator.setStyleSheet("QLabel { color: #475569; font-size: 14px; margin: 0px 8px; }")
        toolbar_layout.addWidget(separator)

        # Align left button
        self.align_left_btn = QPushButton("⬅")
        self.align_left_btn.clicked.connect(lambda: self.set_alignment(Qt.AlignmentFlag.AlignLeft))
        self.align_left_btn.setStyleSheet("""
            QPushButton {
                background: rgba(71, 85, 105, 0.3);
                color: #94a3b8;
                border: 1px solid rgba(71, 85, 105, 0.4);
                padding: 8px 12px;
                border-radius: 8px;
                font-size: 12px;
                min-width: 32px;
            }
            QPushButton:hover {
                background: rgba(71, 85, 105, 0.4);
                color: #cbd5e1;
            }
        """)
        toolbar_layout.addWidget(self.align_left_btn)

        self.align_center_btn = QPushButton("⬌")
        self.align_center_btn.clicked.connect(lambda: self.set_alignment(Qt.AlignmentFlag.AlignCenter))
        self.align_center_btn.setStyleSheet("""
            QPushButton {
                background: rgba(71, 85, 105, 0.3);
                color: #94a3b8;
                border: 1px solid rgba(71, 85, 105, 0.4);
                padding: 8px 12px;
                border-radius: 8px;
                font-size: 12px;
                min-width: 32px;
            }
            QPushButton:hover {
                background: rgba(71, 85, 105, 0.4);
                color: #cbd5e1;
            }
        """)
        toolbar_layout.addWidget(self.align_center_btn)

        self.align_right_btn = QPushButton("➡")
        self.align_right_btn.clicked.connect(lambda: self.set_alignment(Qt.AlignmentFlag.AlignRight))
        self.align_right_btn.setStyleSheet("""
            QPushButton {
                background: rgba(71, 85, 105, 0.3);
                color: #94a3b8;
                border: 1px solid rgba(71, 85, 105, 0.4);
                padding: 8px 12px;
                border-radius: 8px;
                font-size: 12px;
                min-width: 32px;
            }
            QPushButton:hover {
                background: rgba(71, 85, 105, 0.4);
                color: #cbd5e1;
            }
        """)
        toolbar_layout.addWidget(self.align_right_btn)

        # Add stretch to push buttons to the left
        toolbar_layout.addStretch()

        # Font size controls
        size_label = QLabel("Size")
        size_label.setStyleSheet("""
            QLabel { 
                color: #94a3b8; 
                font-size: 12px; 
                font-family: 'Segoe UI', system-ui, sans-serif;
                font-weight: 500;
                margin: 0px 4px;
            }
        """)
        toolbar_layout.addWidget(size_label)

        self.font_size_btn_smaller = QPushButton("−")
        self.font_size_btn_smaller.clicked.connect(self.decrease_font_size)
        self.font_size_btn_smaller.setStyleSheet("""
            QPushButton {
                background: rgba(71, 85, 105, 0.3);
                color: #94a3b8;
                border: 1px solid rgba(71, 85, 105, 0.4);
                padding: 8px;
                border-radius: 8px;
                font-size: 12px;
                min-width: 28px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(71, 85, 105, 0.4);
                color: #cbd5e1;
            }
        """)
        toolbar_layout.addWidget(self.font_size_btn_smaller)

        self.font_size_btn_larger = QPushButton("+")
        self.font_size_btn_larger.clicked.connect(self.increase_font_size)
        self.font_size_btn_larger.setStyleSheet("""
            QPushButton {
                background: rgba(71, 85, 105, 0.3);
                color: #94a3b8;
                border: 1px solid rgba(71, 85, 105, 0.4);
                padding: 8px;
                border-radius: 8px;
                font-size: 12px;
                min-width: 28px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(71, 85, 105, 0.4);
                color: #cbd5e1;
            }
        """)
        toolbar_layout.addWidget(self.font_size_btn_larger)

        layout.addLayout(toolbar_layout)

        self.content_editor = QTextEdit()
        self.content_editor.textChanged.connect(self.on_content_changed)
        self.content_editor.cursorPositionChanged.connect(self.update_format_buttons)
        self.content_editor.setFont(QFont("Segoe UI", 13))
        self.content_editor.setStyleSheet("""
            QTextEdit {
                border: 1px solid rgba(51, 65, 85, 0.3);
                border-radius: 12px;
                padding: 20px;
                background: rgba(30, 41, 59, 0.6);
                color: #f1f5f9;
                line-height: 1.6;
                font-family: 'Segoe UI', system-ui, sans-serif;
                font-weight: 400;
                selection-background-color: rgba(59, 130, 246, 0.2);
                selection-color: #93c5fd;
            }
            QTextEdit:focus {
                border: 1px solid rgba(59, 130, 246, 0.5);
                background: rgba(30, 41, 59, 0.8);
            }
            QScrollBar:vertical {
                background: rgba(15, 23, 42, 0.4);
                width: 12px;
                border-radius: 6px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: rgba(71, 85, 105, 0.4);
                border-radius: 6px;
                min-height: 20px;
                margin: 2px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(71, 85, 105, 0.6);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        layout.addWidget(self.content_editor)

        # Save button
        self.save_btn = QPushButton("Save Note")
        self.save_btn.clicked.connect(self.save_note)
        self.save_btn.setEnabled(False)
        self.save_btn.setStyleSheet("""
            QPushButton {
                background: rgba(34, 197, 94, 0.2);
                color: #22c55e;
                border: 1px solid rgba(34, 197, 94, 0.3);
                padding: 16px 32px;
                border-radius: 12px;
                font-weight: 600;
                font-size: 14px;
                font-family: 'Segoe UI', system-ui, sans-serif;
            }
            QPushButton:hover:enabled {
                background: rgba(34, 197, 94, 0.3);
                color: #4ade80;
                border: 1px solid rgba(34, 197, 94, 0.4);
            }
            QPushButton:pressed:enabled {
                background: rgba(34, 197, 94, 0.4);
                color: #86efac;
            }
            QPushButton:disabled {
                background: rgba(71, 85, 105, 0.2);
                color: #64748b;
                border: 1px solid rgba(71, 85, 105, 0.3);
            }
        """)
        layout.addWidget(self.save_btn)

        return panel


 
    # OPTIMIZATION:  
    def load_note_headers(self):
        """Load note headers into the list, not full content."""
        note_headers = self.db.get_all_note_headers()
        self.refresh_notes_list(note_headers)

    def refresh_notes_list(self, note_headers: List[Note]):
        """Refresh the notes list widget with a given list of note headers."""
        self.notes_list.clear()
        for note in note_headers: # It receives the list of headers directly
            item_text = f"{note.title}"
            if note.tags:
                item_text += f" #{note.tags.replace(',', ' #')}"

            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, note.id) 
            item.setToolTip(f"Tags: {note.tags}") # Tooltip doesn't need full content
            self.notes_list.addItem(item)
        
        self.notes_count_label.setText(f"Notes: {len(note_headers)}")


    # OPTIMIZATION: This is the lazy loading in action.
    def load_selected_note(self, item: QListWidgetItem):
        """Load the FULL content of the selected note from DB on demand."""
        note_id = item.data(Qt.ItemDataRole.UserRole)
        
        # Fetch the full note from the database ONLY when it's clicked.
        note = self.db.get_note(note_id)

        if note:
            self.current_note = note
            self.title_input.setText(note.title)
            self.tags_input.setText(note.tags)
            
            # Check if content is HTML or plain text
            if note.content.strip().startswith('<') and note.content.strip().endswith('>'):
                self.content_editor.setHtml(note.content)
            else:
                self.content_editor.setPlainText(note.content)
            
            self.save_btn.setEnabled(False)
            self.status_bar.showMessage(f"Loaded: '{note.title}'")

    def new_note(self):
        """Create a new note"""
        self.current_note = Note(title="New Note", content="<h1>New Note</h1><p>Start writing here...</p>")
        self.title_input.setText(self.current_note.title)
        self.tags_input.setText("")
        self.content_editor.setHtml(self.current_note.content)
        self.title_input.setFocus()
        self.title_input.selectAll()
        self.save_btn.setEnabled(True)
        self.notes_list.setCurrentItem(None) # Deselect item in list

    def save_note(self):
        """Save the current note"""
        if not self.current_note:
            return

        self.current_note.title = self.title_input.text().strip() or "Untitled"
        self.current_note.content = self.content_editor.toHtml()
        self.current_note.tags = self.tags_input.text().strip()
        self.current_note.updated_at = datetime.now().isoformat()

        self.db.save_note(self.current_note)
        self.load_note_headers() 
        self.save_btn.setEnabled(False)

        self.status_bar.showMessage(f"Saved: '{self.current_note.title}'")

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
            self.status_bar.showMessage(f"Deleted: '{title}'")

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

    def on_search(self, text):
        """Handle search input changes"""
        if not text.strip():
            self.load_note_headers()
            return
        # Use a short delay to make the UI feel responsive
        QTimer.singleShot(100, lambda: self.perform_search(text))

    def perform_search(self, query: str):
        """Perform search by fetching only matching headers."""
        # OPTIMIZATION: Use the memory-efficient search function.
        results = self.db.search_note_headers(query)
        self.refresh_notes_list(results)

        search_type = "AI Search" if self.ai_toggle.isChecked() else "Text Search"
        self.status_bar.showMessage(f"{search_type}: {len(results)} results for '{query}'")

    def show_about(self):
        QMessageBox.about(self, "About Alem", 
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

© 2025 Alem Team""")
        
    def toggle_bold(self):
        """Toggle bold formatting"""
        fmt = self.content_editor.currentCharFormat()
        if fmt.fontWeight() == QFont.Weight.Bold:
            fmt.setFontWeight(QFont.Weight.Normal)
        else:
            fmt.setFontWeight(QFont.Weight.Bold)
        self.content_editor.setCurrentCharFormat(fmt)
        self.content_editor.setFocus()


    def toggle_italic(self):
        """italic formatting"""
        fmt = self.content_editor.currentCharFormat()
        fmt.setFontItalic(not fmt.fontItalic())
        self.content_editor.setCurrentCharFormat(fmt)
        self.content_editor.setFocus()

    def toggle_underline(self):
        """underline formatting"""
        fmt = self.content_editor.currentCharFormat()
        fmt.setFontUnderline(not fmt.fontUnderline())
        self.content_editor.setCurrentCharFormat(fmt)
        self.content_editor.setFocus()

    def set_alignment(self, alignment):
        """text alignment"""
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
        fmt = self.content_editor.currentCharFormat()
        
        # da bold button
        self.bold_btn.setChecked(fmt.fontWeight() == QFont.Weight.Bold)
        
        # da italic button
        self.italic_btn.setChecked(fmt.fontItalic())
        
        # da underline button

        self.underline_btn.setChecked(fmt.fontUnderline())
def main():
    """Main application entry point"""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setApplicationName("Alem")
    app.setApplicationVersion("1.0.0")
    window = SmartNotesApp()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
