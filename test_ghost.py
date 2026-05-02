from PyQt6.QtWidgets import QApplication
import sys
from alem_app.ui.main_window import SmartNotesApp

app = QApplication(sys.argv)
window = SmartNotesApp()
window.show()
print("Initialized without errors!")
