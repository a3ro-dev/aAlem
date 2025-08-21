
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
    QTextEdit, QComboBox, QTabWidget, QStyle
)

from config import config as app_config

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
except ImportError:
    QWebEngineView = None


def create_right_panel(main_window):
    """Create enhanced right panel with modern editor"""
    panel = QWidget()
    panel.setStyleSheet(
        """
        QWidget {
            background: rgba(15, 23, 42, 0.7);
            border: 1px solid rgba(51, 65, 85, 0.3);
            border-radius: 12px;
        }
        """
    )

    layout = QVBoxLayout(panel)
    layout.setSpacing(16)
    layout.setContentsMargins(16, 16, 16, 16)

    # Header with metadata
    header_container = QWidget()
    header_container.setStyleSheet(
        """
        QWidget {
            background: rgba(30, 41, 59, 0.8);
            border: 1px solid rgba(51, 65, 85, 0.3);
            border-radius: 12px;
            padding: 16px;
        }
        """
    )

    header_layout = QVBoxLayout(header_container)
    header_layout.setSpacing(12)

    title_layout = QHBoxLayout()
    title_layout.addWidget(QLabel())

    main_window.title_input = QLineEdit()
    main_window.title_input.setPlaceholderText("Enter an amazing title...")
    main_window.title_input.textChanged.connect(main_window.on_content_changed)
    main_window.title_input.setStyleSheet(
        """
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
        }
        QLineEdit::placeholder { color: #64748b; font-weight: 400; }
        """
    )
    title_layout.addWidget(main_window.title_input)
    header_layout.addLayout(title_layout)

    meta_layout = QHBoxLayout()
    tags_container = QHBoxLayout()
    tags_label = QLabel("Tags:")
    tags_label.setStyleSheet("color:#94a3b8;font-weight:500;font-size:12px;")
    tags_container.addWidget(tags_label)
    main_window.tags_input = QLineEdit()
    main_window.tags_input.setPlaceholderText("Add tags: productivity, ideas, work...")
    main_window.tags_input.textChanged.connect(main_window.on_content_changed)
    main_window.tags_input.setStyleSheet(
        """
        QLineEdit {
            padding: 10px 16px;
            border: 1px solid rgba(51, 65, 85, 0.3);
            border-radius: 8px;
            font-size: 13px;
            color: #e2e8f0;
            background: rgba(15, 23, 42, 0.6);
        }
        QLineEdit:focus {
            border: 1px solid rgba(139, 92, 246, 0.5);
            background: rgba(15, 23, 42, 0.8);
            color: #f1f5f9;
        }
        """
    )
    tags_container.addWidget(main_window.tags_input)
    meta_layout.addLayout(tags_container)

    main_window.lock_btn = QPushButton("Unlock")
    main_window.lock_btn.setFixedSize(40, 40)
    main_window.lock_btn.setCheckable(True)
    main_window.lock_btn.clicked.connect(main_window.toggle_lock_current)
    main_window.lock_btn.setStyleSheet(
        """
        QPushButton { background: rgba(71,85,105,.3); color: #94a3b8; border: 1px solid rgba(71,85,105,.4); border-radius: 8px; font-size: 16px; }
        QPushButton:checked { background: rgba(239,68,68,.3); color:#ef4444; border:1px solid rgba(239,68,68,.4); }
        QPushButton:hover { background: rgba(59,130,246,.3); }
        """
    )
    meta_layout.addWidget(main_window.lock_btn)
    header_layout.addLayout(meta_layout)
    layout.addWidget(header_container)

    # Toolbar
    toolbar_container = QWidget()
    toolbar_container.setStyleSheet(
        """
        QWidget { background: rgba(30,41,59,.8); border: 1px solid rgba(51,65,85,.3); border-radius: 10px; padding: 8px 12px; }
        """
    )
    toolbar_layout = QHBoxLayout(toolbar_container)
    toolbar_layout.setSpacing(6)

    format_group = QHBoxLayout()
    fmt_label = QLabel("Format:")
    fmt_label.setStyleSheet("color:#94a3b8;font-weight:500;font-size:12px;")
    format_group.addWidget(fmt_label)

    main_window.format_combo = QComboBox()
    main_window.format_combo.addItems(["HTML", "Markdown"])
    main_window.format_combo.currentTextChanged.connect(main_window.on_format_changed)
    main_window.format_combo.setStyleSheet(
        """
        QComboBox { background: rgba(15,23,42,.8); border: 1px solid rgba(51,65,85,.3); border-radius: 6px; padding: 4px 8px; color: #e2e8f0; font-weight: 500; min-width: 80px; }
        QComboBox:focus { border: 1px solid rgba(59,130,246,.5); }
        QComboBox::drop-down { border: none; }
        QComboBox::down-arrow { image: none; border-left:4px solid transparent; border-right:4px solid transparent; border-top:4px solid #94a3b8; margin-right:6px; }
        """
    )
    # Set default selection from settings
    try:
        default_fmt = (app_config.get('default_content_format', 'markdown') if app_config else 'markdown').lower()
        main_window.format_combo.setCurrentText('Markdown' if default_fmt == 'markdown' else 'HTML')
    except Exception:
        main_window.format_combo.setCurrentText('Markdown')

    format_group.addWidget(main_window.format_combo)
    format_group.addWidget(QLabel("|"))
    toolbar_layout.addLayout(format_group)

    formatting_buttons = [
        ("B", "Bold", main_window.toggle_bold, None),
        ("I", "Italic", main_window.toggle_italic, None),
        ("U", "Underline", main_window.toggle_underline, None),
        ("", "sep", None, None),
        ("◄", "Align Left", lambda: main_window.set_alignment(Qt.AlignmentFlag.AlignLeft), None),
        ("■", "Center", lambda: main_window.set_alignment(Qt.AlignmentFlag.AlignCenter), None), 
        ("►", "Align Right", lambda: main_window.set_alignment(Qt.AlignmentFlag.AlignRight), None),
        ("", "sep", None, None),
        ("Link", "Insert Link", main_window.insert_link, None),
        ("Img", "Insert Image", main_window.insert_image, None),
        ("Code", "Insert Code", main_window.insert_code_block, None),
    ]

    main_window.format_buttons = {}
    for text, tooltip, action, icon_type in formatting_buttons:
        if text == "":
            sep = QLabel("•")
            sep.setStyleSheet("color:#475569;font-size:14px;margin:0 4px;")
            toolbar_layout.addWidget(sep)
            continue
        btn = QPushButton(text)
        btn.setFixedSize(40, 32)
        btn.setToolTip(tooltip)
        
        # Keep text labels - they're clearer than confusing icons
        if text in ["B", "I", "U"]:
            btn.setCheckable(True)
            main_window.format_buttons[text] = btn
        if action:
            btn.clicked.connect(action)
        btn.setStyleSheet(
            """
            QPushButton { 
                background: rgba(71,85,105,.3); 
                color: #e2e8f0; 
                border: 1px solid rgba(71,85,105,.4); 
                border-radius: 6px; 
                font-weight: 600; 
                font-size: 11px; 
                font-family: 'Segoe UI', system-ui, sans-serif;
                min-width: 36px; 
                min-height: 28px; 
            }
            QPushButton:checked { 
                background: rgba(59,130,246,.4); 
                color: #ffffff; 
                border: 1px solid rgba(59,130,246,.6); 
            }
            QPushButton:hover { 
                background: rgba(71,85,105,.5); 
                color: #f1f5f9; 
                border: 1px solid rgba(71,85,105,.6);
            }
            QPushButton:pressed {
                background: rgba(59,130,246,.3);
            }
            """
        )
        toolbar_layout.addWidget(btn)

    toolbar_layout.addStretch()

    size_controls = QHBoxLayout()
    size_label = QLabel("Size:")
    size_label.setStyleSheet("color:#94a3b8;font-weight:500;font-size:12px;")
    size_controls.addWidget(size_label)
    size_down_btn = QPushButton("A-")
    size_down_btn.setToolTip("Decrease font size")
    size_down_btn.setFixedSize(32, 28)
    size_down_btn.clicked.connect(lambda: main_window.content_editor.zoomOut(1))
    size_up_btn = QPushButton("A+")
    size_up_btn.setToolTip("Increase font size")
    size_up_btn.setFixedSize(32, 28)
    size_up_btn.clicked.connect(lambda: main_window.content_editor.zoomIn(1))
    for b in [size_down_btn, size_up_btn]:
        b.setStyleSheet(
            """
            QPushButton { 
                background: rgba(71,85,105,.3); 
                color: #e2e8f0; 
                border: 1px solid rgba(71,85,105,.4); 
                border-radius: 6px; 
                font-weight: 600; 
                font-size: 10px; 
                font-family: 'Segoe UI', system-ui, sans-serif;
            }
            QPushButton:hover { 
                background: rgba(71,85,105,.4); 
                color: #f1f5f9; 
            }
            """
        )
    size_controls.addWidget(size_down_btn)
    size_controls.addWidget(size_up_btn)
    toolbar_layout.addLayout(size_controls)
    layout.addWidget(toolbar_container)

    # Tabs and editors
    main_window.editor_tabs = QTabWidget()
    main_window.editor_tabs.setStyleSheet(
        """
        QTabWidget::pane { border: 1px solid rgba(51,65,85,.3); border-radius: 12px; background: rgba(30,41,59,.6); padding: 0px; }
        QTabBar::tab { background: rgba(71,85,105,.3); color:#94a3b8; padding: 12px 24px; margin: 2px; border-radius: 8px; font-weight: 600; font-size: 13px; border: 1px solid rgba(71,85,105,.4); min-width: 80px; }
        QTabBar::tab:selected { background: rgba(59,130,246,.3); color:#93c5fd; border: 1px solid rgba(59,130,246,.4); }
        QTabBar::tab:hover:!selected { background: rgba(71,85,105,.4); color:#cbd5e1; }
        """
    )

    edit_tab = QWidget()
    edit_layout = QVBoxLayout(edit_tab)
    edit_layout.setContentsMargins(16, 16, 16, 16)
    main_window.content_editor = QTextEdit()
    main_window.content_editor.textChanged.connect(main_window.on_content_changed)
    main_window.content_editor.cursorPositionChanged.connect(main_window.update_format_buttons)
    main_window.content_editor.setFont(QFont("Segoe UI", 14))
    main_window.content_editor.setStyleSheet(
        """
        QTextEdit { border: 1px solid rgba(51,65,85,.3); border-radius: 12px; padding: 24px; background: rgba(15,23,42,.8); color:#f1f5f9; line-height: 1.6; font-family: 'Segoe UI', system-ui, sans-serif; font-weight: 400; font-size: 14px; selection-background-color: rgba(59,130,246,.3); selection-color: #bfdbfe; }
        QTextEdit:focus { border: 1px solid rgba(59,130,246,.5); background: rgba(15,23,42,.9); }
        QScrollBar:vertical { background: rgba(15,23,42,.4); width: 12px; border-radius: 6px; margin: 0px; }
        QScrollBar::handle:vertical { background: rgba(71,85,105,.6); border-radius: 6px; min-height: 20px; margin: 2px; }
        QScrollBar::handle:vertical:hover { background: rgba(59,130,246,.6); }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        """
    )
    edit_layout.addWidget(main_window.content_editor)
    main_window.editor_tabs.addTab(edit_tab, "Edit")

    preview_tab = QWidget()
    preview_layout = QVBoxLayout(preview_tab)
    preview_layout.setContentsMargins(0, 0, 0, 0)
    if QWebEngineView is not None:
        main_window.preview_view = QWebEngineView()
        main_window.preview_view.setStyleSheet(
            """
            QWebEngineView { border: 1px solid rgba(51,65,85,.3); border-radius: 12px; background: rgba(15,23,42,.8); }
            """
        )
    else:
        main_window.preview_view = QTextEdit()
        main_window.preview_view.setReadOnly(True)
        main_window.preview_view.setStyleSheet(
            """
            QTextEdit { border: 1px solid rgba(51,65,85,.3); border-radius: 12px; padding: 24px; background: rgba(15,23,42,.8); color:#f1f5f9; font-family: 'Segoe UI', system-ui, sans-serif; font-size: 14px; line-height: 1.6; }
            """
        )
    preview_layout.addWidget(main_window.preview_view)
    main_window.editor_tabs.addTab(preview_tab, "Preview")

    main_window.editor_tabs.currentChanged.connect(main_window.on_tab_changed)
    layout.addWidget(main_window.editor_tabs)

    actions_container = QWidget()
    actions_container.setStyleSheet(
        """
        QWidget { background: rgba(30,41,59,.8); border: 1px solid rgba(51,65,85,.3); border-radius: 10px; padding: 12px 16px; }
        """
    )
    actions_layout = QHBoxLayout(actions_container)
    actions_layout.setSpacing(12)
    main_window.word_count_label = QLabel("0 words")
    main_window.word_count_label.setStyleSheet(
        """
        QLabel { color:#64748b; font-weight:500; font-size:12px; background: rgba(15,23,42,.6); padding: 6px 12px; border:1px solid rgba(51,65,85,.3); border-radius: 6px; }
        """
    )
    actions_layout.addWidget(main_window.word_count_label)
    actions_layout.addStretch()
    main_window.save_btn = QPushButton("Save Note")
    main_window.save_btn.clicked.connect(main_window.save_note)
    main_window.save_btn.setEnabled(False)
    try:
        main_window.save_btn.setIcon(main_window.style().standardIcon(main_window.style().StandardPixmap.SP_DialogSaveButton))
        main_window.save_btn.setIconSize(main_window.save_btn.iconSize())
    except Exception:
        pass
    main_window.save_btn.setStyleSheet(
        """
        QPushButton { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 rgba(34,197,94,.3), stop:1 rgba(59,130,246,.2)); color:#22c55e; border:1px solid rgba(34,197,94,.4); padding:10px 20px; border-radius:8px; font-weight:600; font-size:12px; min-height:20px; }
        QPushButton:hover:enabled { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 rgba(34,197,94,.4), stop:1 rgba(59,130,246,.3)); color:#4ade80; border:1px solid rgba(34,197,94,.5); }
        QPushButton:pressed:enabled { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 rgba(34,197,94,.5), stop:1 rgba(59,130,246,.4)); }
        QPushButton:disabled { background: rgba(71,85,105,.2); color:#64748b; border:1px solid rgba(71,85,105,.3); }
        """
    )
    actions_layout.addWidget(main_window.save_btn)
    layout.addWidget(actions_container)
    return panel
