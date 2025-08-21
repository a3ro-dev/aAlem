
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QIcon, QFont, QKeySequence, QTextCharFormat, QAction
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QLabel, QStatusBar, QProgressBar, QMessageBox, QListWidgetItem, QDialog, QLineEdit, QListWidget, QDialogButtonBox, QFormLayout, QApplication, QInputDialog

from alem_app.core.cache import RedisCacheManager
from alem_app.core.discord_rpc import DiscordRPCManager
from alem_app.database.database import Database, Note
from alem_app.ui.actions import create_menu_bar, setup_shortcuts
from alem_app.ui.left_panel import create_left_panel
from alem_app.ui.right_panel import create_right_panel
from alem_app.ui.settings_dialog import SettingsDialog
from alem_app.utils.encryption import decrypt_content, encrypt_content
from alem_app.utils.logging import logger
from config import config as app_config

try:
    import markdown as md
except ImportError:
    md = None

try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:
    Fernet = None
    InvalidToken = None


class SmartNotesApp(QMainWindow):
    """Main Alem Application Window with enhanced features and glassmorphism UI"""

    def __init__(self):
        super().__init__()
        self.db = Database()
        self.redis_cache = RedisCacheManager(app_config)
        self.discord = DiscordRPCManager(app_config)
        self.current_note: Optional[Note] = None
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self._perform_delayed_search)
        self.last_search_query = ""
        self.last_search_time = 0

        self.preview_timer = QTimer()
        self.preview_timer.setSingleShot(True)
        self.preview_timer.timeout.connect(self.render_preview)

        self.setWindowTitle("Alem - Smart Notes")
        self.setGeometry(100, 100, 1400, 900)
        self.setMinimumSize(800, 600)

        try:
            icon_path = Path(__file__).parent.parent.parent / "alem.png"
            if icon_path.exists():
                self.setWindowIcon(QIcon(str(icon_path)))
        except Exception as e:
            logger.warning(f"Could not set app icon: {e}")

        self.setWindowFlags(Qt.WindowType.Window)

        self.setup_ui()
        setup_shortcuts(self)
        self.load_note_headers()
        self.update_stats()

        # Timers
        self.auto_save_timer = QTimer()
        self.auto_save_timer.timeout.connect(self.auto_save)
        self.redis_flush_timer = QTimer()
        self.redis_flush_timer.timeout.connect(self.flush_cache_periodic)
        self.analytics_timer = QTimer()
        self.analytics_timer.timeout.connect(self.update_analytics)
        self.restart_timers()
        self.analytics_timer.start(1000)

    def setup_ui(self):
        self.setStyleSheet(
            """
            QMainWindow {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(10, 15, 28, 0.95),
                    stop:0.3 rgba(13, 20, 33, 0.92),
                    stop:0.7 rgba(17, 24, 39, 0.94),
                    stop:1 rgba(30, 41, 59, 0.96));
                color: #e2e8f0;
            }
            QWidget { color: #e2e8f0; }
            """
        )
        central_widget = QWidget()
        central_widget.setContentsMargins(8, 8, 8, 8)
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(8, 8, 8, 8)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        content_layout.addWidget(self.splitter)

        self.left_panel = create_left_panel(self)
        self.splitter.addWidget(self.left_panel)
        self.right_panel = create_right_panel(self)
        self.splitter.addWidget(self.right_panel)

        self.splitter.setCollapsible(0, True)
        self.splitter.setCollapsible(1, False)
        self.splitter.setSizes([280, 1120])
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self._last_sidebar_size = 280
        
        # Set minimum sizes for responsive behavior
        self.left_panel.setMinimumWidth(250)
        self.right_panel.setMinimumWidth(400)

        main_layout.addLayout(content_layout)

        create_menu_bar(self)
        self.status_bar = self.create_status_bar()
        self.setStatusBar(self.status_bar)

    def create_status_bar(self):
        bar = QStatusBar()
        bar.setStyleSheet("""
            QStatusBar {
                background: rgba(15, 23, 42, 0.95); color: #94a3b8;
                border-top: 1px solid rgba(51, 65, 85, 0.3);
                font-family: 'Segoe UI', system-ui, sans-serif; font-size: 11px; padding: 4px 8px;
            }
            QLabel {
                color: #94a3b8; padding: 0 6px; background: rgba(30, 41, 59, 0.6);
                border: 1px solid rgba(51, 65, 85, 0.3); border-radius: 4px; margin: 2px;
            }
        """)
        self.analytics_notes = QLabel("Notes: 0")
        self.analytics_format = QLabel("Format: -")
        self.analytics_redis = QLabel("Cache: Off")
        self.analytics_status = QLabel("Ready")
        self.operation_progress = QProgressBar()
        self.operation_progress.setVisible(False)
        self.operation_progress.setFixedWidth(120)
        css = (
            "QProgressBar {"
            "background: #1e293b99;"
            "border: 1px solid #3341554d;"
            "border-radius: 4px;"
            "height: 14px;"
            "}"
            "QProgressBar::chunk {"
            "background: #3b82f699;"
            "border-radius: 3px;"
            "}"
        )
        self.operation_progress.setStyleSheet(css)
        for w in [self.analytics_notes, self.analytics_format, self.analytics_redis, self.analytics_status, self.operation_progress]:
            bar.addPermanentWidget(w)
        bar.showMessage("Ready • Alem Smart Notes")
        return bar

    def set_status(self, message: str, timeout_ms: int = 0):
        if hasattr(self, 'status_bar') and hasattr(self.status_bar, 'showMessage'):
            self.status_bar.showMessage(message, int(timeout_ms))

    def load_note_headers(self):
        note_headers = self.db.get_all_note_headers()
        self.refresh_notes_list(note_headers)

    def refresh_notes_list(self, note_headers: list[Note]):
        self.notes_list.clear()
        for note in note_headers:
            item_text = f"{note.title}"
            if note.tags:
                item_text += f"  •  #{note.tags.replace(',', ' #')}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, note.id)
            item.setToolTip(f"Tags: {note.tags}\nCreated: {note.created_at[:10]}")
            self.notes_list.addItem(item)
        self.update_stats()

    def load_selected_note(self, item: QListWidgetItem):
        note_id = item.data(Qt.ItemDataRole.UserRole)
        note = None
        if self.redis_cache.enabled:
            cached_data = self.redis_cache.get_note(note_id)
            if cached_data:
                try:
                    note = Note.from_dict(cached_data)
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
            content_text = note.content
            if note.locked:
                pwd = self.prompt_password("Unlock Note", "Enter password to unlock this note:")
                if pwd:
                    try:
                        content_text = decrypt_content(content_text, pwd)
                    except (ValueError, InvalidToken):
                        QMessageBox.critical(self, "Error", "Incorrect password or decryption failed.")
                        content_text = ""
                else:
                    content_text = ""
            
            self.format_combo.setCurrentText(note.content_format.upper())
            if note.content_format == 'html':
                self.content_editor.setHtml(content_text)
            else:
                self.content_editor.setPlainText(content_text)

            self.save_btn.setEnabled(False)
            self.set_status(f"Loaded: '{note.title}'")
            self.render_preview()
            self.update_analytics()

    def new_note(self):
        default_fmt = (app_config.get('default_content_format', 'markdown') if app_config else 'markdown')
        self.current_note = Note(title="New Note", content="", content_format=default_fmt)
        self.title_input.setText(self.current_note.title)
        self.tags_input.setText("")
        self.content_editor.clear()
        self.format_combo.setCurrentText(default_fmt.capitalize())
        self.title_input.setFocus()
        self.title_input.selectAll()
        self.save_btn.setEnabled(True)
        self.notes_list.setCurrentItem(None)
        self.render_preview()
        self.update_analytics()

    def save_note(self):
        if not self.current_note: return

        self.current_note.title = self.title_input.text().strip() or "Untitled"
        self.current_note.content_format = self.format_combo.currentText().lower()
        
        if self.current_note.content_format == 'html':
            self.current_note.content = self.content_editor.toHtml()
        else:
            self.current_note.content = self.content_editor.toPlainText()
            
        self.current_note.tags = self.tags_input.text().strip()
        self.current_note.updated_at = datetime.now().isoformat()

        if self.current_note.locked:
            pwd = self.prompt_password("Confirm Password", "Enter password to encrypt before saving:")
            if not pwd:
                QMessageBox.warning(self, "Warning", "Save cancelled: password required for locked notes.")
                return
            try:
                iters = app_config.get('kdf_iterations', 390000) if app_config else 390000
                enc_content = encrypt_content(self.current_note.content, pwd, iters)
                note_to_save = Note(**self.current_note.to_dict())
                note_to_save.content = enc_content
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Encryption failed: {e}")
                return
        else:
            note_to_save = self.current_note

        if self.redis_cache.enabled:
            self.redis_cache.cache_note(note_to_save)
        else:
            self.db.save_note(note_to_save)
            
        self.load_note_headers()
        self.save_btn.setEnabled(False)
        self.set_status(f"Saved: '{self.current_note.title}'")
        self.update_analytics()

    def delete_note(self):
        current_item = self.notes_list.currentItem()
        if not current_item: QMessageBox.warning(self, "Warning", "Please select a note to delete.")
        else:
            note_id = current_item.data(Qt.ItemDataRole.UserRole)
            title = current_item.text().split('  •  #')[0]

            reply = QMessageBox.question(self, "Delete Note", f"Are you sure you want to delete '{title}'?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.db.delete_note(note_id)
                self.load_note_headers()
                self.clear_editor()
                self.set_status(f"Deleted: '{title}'")
                self.update_analytics()

    def clear_editor(self):
        self.title_input.clear()
        self.tags_input.clear()
        self.content_editor.clear()
        self.current_note = None
        self.save_btn.setEnabled(False)
        self.update_analytics()

    def on_content_changed(self):
        if self.current_note is not None:
            self.save_btn.setEnabled(True)
            self.preview_timer.start(250)
            self.update_analytics()

    def on_search(self, text):
        self.last_search_query = text.strip()
        self.search_timer.start(app_config.get('search_debounce_delay', 300) if app_config else 300)

    def _perform_delayed_search(self):
        if self.last_search_query:
            self.perform_search(self.last_search_query)
        else:
            self.load_note_headers()

    def perform_search(self, query: str):
        start_time = time.time()
        self.operation_progress.setVisible(True)
        self.operation_progress.setRange(0, 0)
        try:
            results = self.db.search_note_headers(query)
            self.refresh_notes_list(results)
            self.last_search_time = round((time.time() - start_time) * 1000, 1)
            self.set_status(f"Found {len(results)} results for '{query}' ({self.last_search_time}ms)")
        except Exception as e:
            logger.error(f"Search error: {e}")
            self.set_status(f"Search error: {e}")
        finally:
            self.operation_progress.setVisible(False)
            self.update_analytics()

    def render_preview(self):
        if not self.current_note or not hasattr(self, 'preview_view'): 
            return

        content_format = self.format_combo.currentText().lower()
        
        # Check if we're using QWebEngineView or QTextEdit
        is_web_engine = hasattr(self.preview_view, 'setHtml') and hasattr(self.preview_view, 'page')
        
        if content_format == 'markdown':
            content = self.content_editor.toPlainText()
            if md:
                try:
                    extensions = app_config.get('markdown_extensions', []) if app_config else []
                    html = md.markdown(content, extensions=extensions)
                    
                    if is_web_engine:
                        # Full HTML for QWebEngineView
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
                            </style>
                        </head>
                        <body>
                            {html}
                        </body>
                        </html>
                        """
                        self.preview_view.setHtml(styled_html)
                    else:
                        # For QTextEdit, use simpler HTML or plain text
                        self.preview_view.setHtml(html)
                        
                except Exception as e:
                    logger.error(f"Markdown rendering error: {e}")
                    if is_web_engine:
                        self.preview_view.setHtml(f"<pre>{content}</pre>")
                    else:
                        self.preview_view.setPlainText(content)
            else:
                # No markdown library available
                if is_web_engine:
                    self.preview_view.setHtml(f"<pre>{content}</pre>")
                else:
                    self.preview_view.setPlainText(content)
        else: 
            # HTML format
            if is_web_engine:
                self.preview_view.setHtml(self.content_editor.toHtml())
            else:
                self.preview_view.setHtml(self.content_editor.toHtml())

    def update_analytics(self):
        stats = self.db.get_stats()
        self.analytics_notes.setText(f"Notes: {stats.get('total_notes', 0)}")
        if self.current_note:
            text = self.content_editor.toPlainText()
            words = len([w for w in text.split() if w.strip()])
            chars = len(text)
            self.word_count_label.setText(f"{words} words, {chars} chars")
            format_text = self.current_note.content_format.upper()
            lock_status = "Locked" if self.current_note.locked else "Unlocked"
            self.analytics_format.setText(f"Format: {format_text} | {lock_status}")
            self.lock_btn.setChecked(self.current_note.locked)
            self.lock_btn.setText("🔒" if self.current_note.locked else "🔓")
        else:
            self.word_count_label.setText("0 words, 0 chars")
            self.analytics_format.setText("Format: - | -")
        
        if self.redis_cache.enabled:
            self.analytics_redis.setText(f"Cache: {self.redis_cache.dirty_count()} dirty")
        else:
            self.analytics_redis.setText("Cache: Off")

        if self.last_search_time < 50: performance = "Fast"
        elif self.last_search_time < 200: performance = "Good"
        else: performance = "Slow"
        self.analytics_status.setText(performance if self.last_search_query else "Ready")

    def update_stats(self):
        stats = self.db.get_stats()
        self.notes_count_label.setText(f"Notes: {stats['total_notes']}")
        self.db_size_label.setText(f"Database: {stats['db_size_kb']} KB")
        if self.redis_cache.enabled:
            self.cache_label.setText(f"Cache: {self.redis_cache.dirty_count()} dirty")
        else:
            self.cache_label.setText("Cache: Off")

    def auto_save(self):
        if self.current_note and self.save_btn.isEnabled():
            self.save_note()
            self.set_status("Auto-saved", 2000)

    def flush_cache_periodic(self):
        if self.redis_cache.enabled:
            flushed, errors = self.redis_cache.flush_to_db(self.db)
            if flushed: self.set_status(f"Flushed {flushed} note(s) to DB from cache", 2000)
            if errors: self.set_status("Cache flush error", 3000)
            self.update_analytics()

    def toggle_lock_current(self):
        if not self.current_note: return
        if self.current_note.locked:
            pwd = self.prompt_password("Unlock Note", "Enter password to unlock:")
            if not pwd: return
            try:
                plain_content = decrypt_content(self.current_note.content, pwd)
                self.current_note.locked = False
                if self.current_note.content_format == 'html':
                    self.content_editor.setHtml(plain_content)
                else:
                    self.content_editor.setPlainText(plain_content)
                self.save_btn.setEnabled(True)
            except (ValueError, InvalidToken):
                QMessageBox.critical(self, "Error", "Incorrect password.")
        else:
            if not Fernet:
                QMessageBox.warning(self, "Unavailable", "Install 'cryptography' to lock notes.")
                return
            pwd = self.prompt_password("Lock Note", "Set a password for this note:", confirm=True)
            if pwd:
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
                QMessageBox.warning(self, "Mismatch", "Passwords do not match.")
                return None
            return p1
        return None

    def closeEvent(self, event):
        if self.current_note and self.save_btn.isEnabled():
            reply = QMessageBox.question(self, "Unsaved Changes", "Save before closing?",
                                         QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
            if reply == QMessageBox.StandardButton.Save:
                self.save_note()
            elif reply == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
        self.auto_save_timer.stop()
        self.search_timer.stop()
        self.redis_flush_timer.stop()
        self.flush_cache_periodic()
        self.discord.close()
        settings = self.get_settings()
        if settings:
            settings.setValue("geometry", self.saveGeometry())
            settings.setValue("windowState", self.saveState())
        event.accept()

    def get_settings(self):
        if hasattr(QApplication.instance(), 'settings'):
            return QApplication.instance().settings
        return None

    # --- UI Actions ---
    def toggle_maximize(self):
        if self.isMaximized(): self.showNormal()
        else: self.showMaximized()

    def toggle_fullscreen(self):
        if self.isFullScreen(): self.showNormal()
        else: self.showFullScreen()

    def on_format_changed(self, format_text):
        if self.current_note:
            new_format = format_text.lower()
            if new_format != self.current_note.content_format:
                self.current_note.content_format = new_format
                self.save_btn.setEnabled(True)
                self.update_analytics()

    def on_tab_changed(self, index):
        if index == 1: self.render_preview()

    def insert_link(self):
        text, ok = QInputDialog.getText(self, "Insert Link", "URL:")
        if ok and text:
            if self.format_combo.currentText() == 'MARKDOWN':
                self.content_editor.insertPlainText(f"[link]({text})")
            else:
                self.content_editor.insertHtml(f'<a href="{text}">{text}</a>')

    def insert_image(self):
        text, ok = QInputDialog.getText(self, "Insert Image", "Image URL:")
        if ok and text:
            if self.format_combo.currentText() == 'MARKDOWN':
                self.content_editor.insertPlainText(f"![image]({text})")
            else:
                self.content_editor.insertHtml(f'<img src="{text}" alt="image"/>')

    def insert_code_block(self):
        if self.format_combo.currentText() == 'MARKDOWN':
            self.content_editor.insertPlainText("""
```python
# Your code here
print('Hello, World!')
```
""")
        else:
            self.content_editor.insertHtml("<pre><code>code here</code></pre>")

    def quick_open(self):
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
            results = self.db.search_note_headers(text) if text else self.db.get_all_note_headers()
            for note in results[:20]:
                item = QListWidgetItem(note.title)
                item.setData(Qt.ItemDataRole.UserRole, note.id)
                notes_list.addItem(item)
        search_input.textChanged.connect(update_list)
        update_list("")

        def open_selected():
            current_item = notes_list.currentItem()
            if current_item:
                note_id = current_item.data(Qt.ItemDataRole.UserRole)
                for i in range(self.notes_list.count()):
                    item = self.notes_list.item(i)
                    if item.data(Qt.ItemDataRole.UserRole) == note_id:
                        self.notes_list.setCurrentItem(item)
                        self.load_selected_note(item)
                        break
                dialog.accept()
        notes_list.itemDoubleClicked.connect(open_selected)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(open_selected)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def focus_notes_list(self):
        self.notes_list.setFocus()

    def search_next(self): pass # Placeholder
    def search_previous(self): pass # Placeholder

    def show_settings(self):
        dialog = SettingsDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.settings_changed:
            QMessageBox.information(self, "Settings Saved", "Some settings require an application restart to take effect.")
            self.restart_timers()

    def show_debug_info(self):
        stats = self.db.get_stats()
        redis_info = f"Redis: {'Enabled' if self.redis_cache.enabled else 'Disabled'}"
        if self.redis_cache.enabled: redis_info += f" | Dirty: {self.redis_cache.dirty_count()}"
        info = f"""
Database: {stats['total_notes']} notes, {stats['unique_tags']} tags, {stats['db_size_kb']} KB
Cache: {redis_info}
Current Note: Format {self.current_note.content_format if self.current_note else 'N/A'}, Locked: {self.current_note.locked if self.current_note else 'N/A'}
        """
        QMessageBox.information(self, "Debug Information", info)

    def show_help(self):
        QMessageBox.information(self, "Help", "Shortcuts:\nCtrl+N: New\nCtrl+S: Save\nCtrl+O: Quick Open\nCtrl+D: Delete\nCtrl+L: Lock/Unlock\nCtrl+F: Find\nF5: Refresh Preview")

    def show_about(self):
        QMessageBox.about(self, "About Alem", "Alem - Smart Notes v2.0\nYour modern note-taking companion.")

    def restart_timers(self):
        cfg = app_config or {}
        self.auto_save_timer.start(cfg.get('auto_save_interval', 30000))
        self.redis_flush_timer.start(cfg.get('redis_flush_interval_s', 60) * 1000)

    def update_format_buttons(self):
        if hasattr(self, 'format_buttons'):
            fmt = self.content_editor.currentCharFormat()
            self.format_buttons['B'].setChecked(fmt.fontWeight() == QFont.Weight.Bold)
            self.format_buttons['I'].setChecked(fmt.fontItalic())
            self.format_buttons['U'].setChecked(fmt.fontUnderline())

    def toggle_bold(self):
        self.content_editor.setFontWeight(QFont.Weight.Bold if self.content_editor.fontWeight() != QFont.Weight.Bold else QFont.Weight.Normal)

    def toggle_italic(self):
        self.content_editor.setFontItalic(not self.content_editor.fontItalic())

    def toggle_underline(self):
        self.content_editor.setFontUnderline(not self.content_editor.fontUnderline())

    def set_alignment(self, alignment):
        self.content_editor.setAlignment(alignment)

    def resizeEvent(self, event):
        """Handle window resize events for responsive design"""
        super().resizeEvent(event)
        
        # Adjust splitter sizes based on window width
        window_width = self.width()
        if window_width < 1000:
            # For smaller windows, make sidebar smaller
            if self.splitter.sizes()[0] > 250:
                self.splitter.setSizes([250, window_width - 250])
        elif window_width < 1200:
            # Medium windows
            if self.splitter.sizes()[0] != 280:
                self.splitter.setSizes([280, window_width - 280])
        else:
            # Large windows can have normal sidebar
            if self.splitter.sizes()[0] < 280:
                self.splitter.setSizes([280, window_width - 280])
