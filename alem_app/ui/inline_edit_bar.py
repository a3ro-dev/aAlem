from PyQt6.QtWidgets import QFrame, QLineEdit, QVBoxLayout, QApplication
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QPoint
from PyQt6.QtGui import QTextCursor
from alem_app.core.llm_router import LLMRouter
import config

class InlineEditWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, instruction: str, selected_text: str):
        super().__init__()
        self.instruction = instruction
        self.selected_text = selected_text

    def run(self):
        try:
            app_config = config.config
            if not app_config.get("groq_api_key", ""):
                self.error.emit("Groq API key not set")
                return

            system_prompt = "You are a writing assistant. Rewrite the given text according to the instruction. Output ONLY the rewritten text, nothing else."
            user_prompt = f"Instruction: {self.instruction}\n\nText to rewrite:\n{self.selected_text}"

            response = LLMRouter.complete(
                prompt=user_prompt,
                system=system_prompt,
                provider="groq",
                model="llama-3.3-70b-versatile",
                stream=False
            )

            output = response.choices[0].message.content
            self.finished.emit(output)
        except Exception as e:
            self.error.emit(str(e))


class InlineEditBar(QFrame):
    def __init__(self, parent_window):
        super().__init__(parent_window)
        self.parent_window = parent_window
        self.editor = None
        self._worker = None

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Popup | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.setStyleSheet("""
            QFrame {
                background-color: #1e2736;
                border: 1px solid #4f98a3;
                border-radius: 8px;
            }
            QLineEdit {
                background: transparent;
                border: none;
                color: white;
                font-family: Inter, sans-serif;
                font-size: 13px;
                padding: 4px 8px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Instruct AI to edit... (Enter to apply, Esc to cancel)")
        self.input_field.returnPressed.connect(self._apply_edit)
        layout.addWidget(self.input_field)

        self.setFixedSize(520, 44)
        self.hide()

    def show_at_cursor(self, editor):
        self.editor = editor
        self.input_field.clear()
        self.input_field.setEnabled(True)
        self.input_field.setPlaceholderText("Instruct AI to edit... (Enter to apply, Esc to cancel)")

        cursor_rect = self.editor.cursorRect()
        global_pos = self.editor.mapToGlobal(cursor_rect.bottomLeft())
        # Map to parent window coordinates if we wanted a child widget,
        # but since it's a Tool/Popup window, global pos works better.

        # Adjust so it displays right below cursor
        x = global_pos.x()
        y = global_pos.y() + 10
        self.move(QPoint(x, y))
        self.show()
        self.input_field.setFocus()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            return
        super().keyPressEvent(event)

    def _apply_edit(self):
        instruction = self.input_field.text().strip()
        if not instruction:
            self.hide()
            return

        cursor = self.editor.textCursor()
        selected_text = cursor.selectedText()

        # Get last 300 characters if no selection
        if not selected_text:
            pos = cursor.position()
            doc_text = self.editor.toPlainText()
            selected_text = doc_text[max(0, pos-300):pos]

        if not selected_text:
            self.hide()
            return

        self.input_field.setPlaceholderText("Thinking...")
        self.input_field.clear()
        self.input_field.setEnabled(False)

        self._worker = InlineEditWorker(instruction, selected_text)
        self._worker.finished.connect(self._on_edit_finished)
        self._worker.error.connect(self._on_edit_error)
        self._worker.start()

    def _on_edit_finished(self, text):
        cursor = self.editor.textCursor()
        if not cursor.hasSelection():
            # Select the last 300 characters to replace them since that's what we edited
            pos = cursor.position()
            doc_text = self.editor.toPlainText()
            start_pos = max(0, pos - 300)
            cursor.setPosition(start_pos)
            cursor.setPosition(pos, QTextCursor.MoveMode.KeepAnchor)

        cursor.insertText(text)
        self.hide()

    def _on_edit_error(self, err_msg):
        from alem_app.utils.logging import logger
        logger.error(f"Inline Edit Error: {err_msg}")
        self.hide()
