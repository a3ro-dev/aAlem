import sys
from pathlib import Path

from PyQt6.QtCore import QSettings, QTimer, Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QMessageBox

from alem_app.ui.main_window import SmartNotesApp
from alem_app.utils.logging import logger
from config import config as app_config


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
        icon_path = Path(__file__).parent.parent / "alem.png"
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
