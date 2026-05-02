"""Smoke test: launch the main window and verify it initialises without errors.

Run manually (not via pytest) from the repository root:
    python scripts/smoke_test_ghost.py
"""

if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    from alem_app.ui.main_window import SmartNotesApp

    app = QApplication(sys.argv)
    window = SmartNotesApp()
    window.show()
    print("Initialized without errors!")
    sys.exit(app.exec())
