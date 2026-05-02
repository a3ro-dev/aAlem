from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QPoint
from PyQt6.QtGui import QTextCursor
from alem_app.core.llm_router import LLMRouter
import config

class ActionWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, action_name: str, full_note: str):
        super().__init__()
        self.action_name = action_name
        self.full_note = full_note

    def run(self):
        try:
            app_config = config.config
            provider = "groq"
            if app_config.get("groq_api_key", ""):
                provider = "groq"
            elif app_config.get("nvidia_api_key", ""):
                provider = "nvidia"
            elif app_config.get("glm_api_key", ""):
                provider = "glm"
            else:
                self.error.emit("No API key configured for any provider")
                return

            system_prompt = f"You are a writing assistant. Perform the requested action on the given text. Output ONLY the resulting text, nothing else."
            user_prompt = f"Action: {self.action_name}\n\nText:\n{self.full_note}"

            response = LLMRouter.complete(
                prompt=user_prompt,
                system=system_prompt,
                provider=provider,
                model=None, # Fallback to LLMRouter's default per provider
                stream=False
            )

            output = response.choices[0].message.content
            self.finished.emit(output)
        except Exception as e:
            self.error.emit(str(e))


class CommandPalette(QDialog):
    def __init__(self, parent_window):
        super().__init__(parent_window, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Popup)
        self.parent_window = parent_window
        self.setFixedSize(600, 400)
        self._worker = None

        self.setStyleSheet("""
            QDialog {
                background-color: #1e2736;
                border: 1px solid #4f98a3;
                border-radius: 8px;
            }
            QLineEdit {
                background: rgba(15,23,42,.8);
                border: 1px solid #4f98a3;
                border-radius: 6px;
                color: white;
                padding: 10px;
                font-size: 14px;
                margin: 10px;
            }
            QListWidget {
                background: transparent;
                border: none;
                color: white;
                font-size: 13px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 10px;
                border-radius: 6px;
            }
            QListWidget::item:selected {
                background-color: #3b82f6;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search commands or notes...")
        self.search_input.textChanged.connect(self._filter_list)
        layout.addWidget(self.search_input)

        self.list_widget = QListWidget()
        self.list_widget.itemActivated.connect(self._execute_item)
        layout.addWidget(self.list_widget)

        # Handle arrow keys in search input to navigate list
        self.search_input.installEventFilter(self)

        self._all_items = []

    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent
        if obj is self.search_input and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key == Qt.Key.Key_Down:
                self.list_widget.setCurrentRow((self.list_widget.currentRow() + 1) % self.list_widget.count())
                return True
            elif key == Qt.Key.Key_Up:
                self.list_widget.setCurrentRow((self.list_widget.currentRow() - 1) % self.list_widget.count())
                return True
            elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if self.list_widget.currentItem():
                    self._execute_item(self.list_widget.currentItem())
                return True
        return super().eventFilter(obj, event)

    def show_palette(self):
        self.search_input.clear()
        self._populate_list()

        # Position at top-center of parent window
        parent_rect = self.parent_window.geometry()
        x = parent_rect.x() + (parent_rect.width() - self.width()) // 2
        y = parent_rect.y() + 50
        self.move(x, y)

        self.show()
        self.search_input.setFocus()
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    def _populate_list(self):
        self.list_widget.clear()
        self._all_items = []

        # 1. Notes
        notes = self.parent_window.db.get_all_notes()
        for note in notes:
            item = {
                "display": f"📄 {note.title}",
                "type": "note",
                "data": note
            }
            self._all_items.append(item)

        # 2. AI Actions
        ai_actions = [
            "✨ Summarize note",
            "✨ Improve writing",
            "✨ Fix grammar",
            "✨ Make it shorter",
            "✨ Make it longer",
            "✨ Extract key points"
        ]
        for action in ai_actions:
            item = {
                "display": action,
                "type": "ai_action",
                "data": action
            }
            self._all_items.append(item)

        # 3. App Actions
        app_actions = [
            ("⚙ Settings", self.parent_window.show_settings),
            ("📝 New Note", self.parent_window.new_note),
            ("💾 Save Note", self.parent_window.save_note)
        ]
        for display, func in app_actions:
            item = {
                "display": display,
                "type": "app_action",
                "data": func
            }
            self._all_items.append(item)

        self._filter_list("")

    def _filter_list(self, query):
        self.list_widget.clear()
        query = query.lower()

        from difflib import SequenceMatcher
        filtered = []

        for item in self._all_items:
            display = item["display"].lower()
            if not query:
                filtered.append((item, 1.0))
            elif query in display:
                filtered.append((item, 1.0))
            else:
                ratio = SequenceMatcher(None, query, display).ratio()
                if ratio > 0.3:
                    filtered.append((item, ratio))

        filtered.sort(key=lambda x: x[1], reverse=True)

        for item, _ in filtered:
            list_item = QListWidgetItem(item["display"])
            list_item.setData(Qt.ItemDataRole.UserRole, item)
            self.list_widget.addItem(list_item)

        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    def _execute_item(self, list_item):
        item_data = list_item.data(Qt.ItemDataRole.UserRole)
        self.hide()

        if item_data["type"] == "note":
            note = item_data["data"]
            self.parent_window.load_note(note)
        elif item_data["type"] == "app_action":
            func = item_data["data"]
            func()
        elif item_data["type"] == "ai_action":
            action_name = item_data["data"]
            self._run_ai_action(action_name)

    def _run_ai_action(self, action_name):
        editor = self.parent_window.content_editor
        full_note = editor.toPlainText()

        if not full_note.strip():
            return

        self._worker = ActionWorker(action_name, full_note)
        self._worker.finished.connect(lambda result: self._on_ai_action_finished(editor, result))
        self._worker.error.connect(self._on_ai_action_error)
        self._worker.start()

    def _on_ai_action_finished(self, editor, result):
        cursor = editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(f"\n\n--- AI Action Result ---\n{result}\n")

    def _on_ai_action_error(self, err_msg):
        from alem_app.utils.logging import logger
        logger.error(f"Command Palette AI Action Error: {err_msg}")
