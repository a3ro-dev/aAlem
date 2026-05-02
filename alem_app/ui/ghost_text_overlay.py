from PyQt6.QtWidgets import QWidget, QTextEdit
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QColor

class GhostTextOverlay(QWidget):
    def __init__(self, editor: QTextEdit):
        super().__init__(editor)
        self.editor = editor
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._text = ""
        self.resize(self.editor.size())

    def show_suggestion(self, text: str):
        self._text = text
        self.setGeometry(self.editor.geometry())
        self.raise_()
        self.update()

    def clear(self):
        self._text = ""
        self.update()

    def paintEvent(self, event):
        if not self._text:
            return

        painter = QPainter(self)
        painter.setFont(self.editor.font())
        painter.setPen(QColor(150, 150, 150, 180))

        cursor_rect = self.editor.cursorRect()
        x = cursor_rect.right()
        y = cursor_rect.top()

        text_rect = cursor_rect.adjusted(0, 0, self.width() - x, self.height() - y)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, self._text)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.resize(self.editor.size())
