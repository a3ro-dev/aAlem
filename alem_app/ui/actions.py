
from PyQt6.QtGui import QAction, QKeySequence, QShortcut


def create_menu_bar(main_window):
    """Create the menu bar"""
    menubar = main_window.menuBar()
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

    new_action = QAction('New Note', main_window)
    new_action.setShortcut(QKeySequence.StandardKey.New)
    new_action.triggered.connect(main_window.new_note)
    file_menu.addAction(new_action)

    save_action = QAction('Save', main_window)
    save_action.setShortcut(QKeySequence.StandardKey.Save)
    save_action.triggered.connect(main_window.save_note)
    file_menu.addAction(save_action)

    lock_action = QAction('Lock/Unlock Note', main_window)
    lock_action.setShortcut('Ctrl+L')
    lock_action.triggered.connect(main_window.toggle_lock_current)
    file_menu.addAction(lock_action)

    file_menu.addSeparator()
    exit_action = QAction('Exit', main_window)
    exit_action.setShortcut(QKeySequence.StandardKey.Close)
    exit_action.triggered.connect(main_window.close)
    file_menu.addAction(exit_action)

    # Search menu
    search_menu = menubar.addMenu('Search')
    search_action = QAction('Search Notes', main_window)
    search_action.setShortcut(QKeySequence.StandardKey.Find)
    search_action.triggered.connect(lambda: main_window.search_input.setFocus())
    search_menu.addAction(search_action)

    # View menu
    view_menu = menubar.addMenu('View')
    main_window.action_show_edit = QAction('Edit Mode', main_window)
    main_window.action_show_edit.setShortcut('Ctrl+1')
    main_window.action_show_edit.triggered.connect(lambda: main_window.editor_tabs.setCurrentIndex(0))
    view_menu.addAction(main_window.action_show_edit)

    main_window.action_show_preview = QAction('Preview Mode', main_window)
    main_window.action_show_preview.setShortcut('Ctrl+2')
    main_window.action_show_preview.triggered.connect(lambda: main_window.editor_tabs.setCurrentIndex(1))
    view_menu.addAction(main_window.action_show_preview)

    main_window.action_refresh_preview = QAction('Refresh Preview', main_window)
    main_window.action_refresh_preview.setShortcut('F5')
    main_window.action_refresh_preview.triggered.connect(main_window.render_preview)
    view_menu.addAction(main_window.action_refresh_preview)

    # Help menu
    help_menu = menubar.addMenu('Help')
    about_action = QAction('About Alem', main_window)
    about_action.triggered.connect(main_window.show_about)
    help_menu.addAction(about_action)


def setup_shortcuts(main_window):
    """Setup Windows-style keyboard shortcuts"""
    # File operations
    QShortcut(QKeySequence.StandardKey.New, main_window, main_window.new_note)
    QShortcut(QKeySequence.StandardKey.Save, main_window, main_window.save_note)
    QShortcut(QKeySequence.StandardKey.Open, main_window, main_window.quick_open)
    QShortcut(QKeySequence("Ctrl+D"), main_window, main_window.delete_note)
    QShortcut(QKeySequence("Ctrl+L"), main_window, main_window.toggle_lock_current)

    # Edit operations
    QShortcut(QKeySequence.StandardKey.Undo, main_window, lambda: main_window.content_editor.undo())
    QShortcut(QKeySequence.StandardKey.Redo, main_window, lambda: main_window.content_editor.redo())
    QShortcut(QKeySequence.StandardKey.Cut, main_window, lambda: main_window.content_editor.cut())
    QShortcut(QKeySequence.StandardKey.Copy, main_window, lambda: main_window.content_editor.copy())
    QShortcut(QKeySequence.StandardKey.Paste, main_window, lambda: main_window.content_editor.paste())
    QShortcut(QKeySequence.StandardKey.SelectAll, main_window, lambda: main_window.content_editor.selectAll())

    # Search and navigation
    QShortcut(QKeySequence.StandardKey.Find, main_window, lambda: main_window.search_.setFocus())
    QShortcut(QKeySequence("Ctrl+G"), main_window, main_window.focus_notes_list)
    QShortcut(QKeySequence("F3"), main_window, main_window.search_next)
    QShortcut(QKeySequence("Shift+F3"), main_window, main_window.search_previous)

    # Formatting
    QShortcut(QKeySequence.StandardKey.Bold, main_window, main_window.toggle_bold)
    QShortcut(QKeySequence.StandardKey.Italic, main_window, main_window.toggle_italic)
    QShortcut(QKeySequence.StandardKey.Underline, main_window, main_window.toggle_underline)

    # View modes
    QShortcut(QKeySequence("Ctrl+1"), main_window, lambda: main_window.editor_tabs.setCurrentIndex(0))
    QShortcut(QKeySequence("Ctrl+2"), main_window, lambda: main_window.editor_tabs.setCurrentIndex(1))
    QShortcut(QKeySequence("F5"), main_window, main_window.render_preview)
    QShortcut(QKeySequence("F11"), main_window, main_window.toggle_fullscreen)

    # Application
    QShortcut(QKeySequence("Ctrl+,"), main_window, main_window.show_settings)
    QShortcut(QKeySequence("Ctrl+Shift+I"), main_window, main_window.show_debug_info)
    QShortcut(QKeySequence("F1"), main_window, main_window.show_help)
    QShortcut(QKeySequence.StandardKey.Quit, main_window, main_window.close)
