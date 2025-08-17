
from pathlib import Path

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QPixmap
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QListWidget, QFrame, QStyle
)


def create_left_panel(main_window):
    """Create enhanced left panel with glassmorphism design"""
    panel = QWidget()
    panel.setStyleSheet("""
        QWidget {
            background: rgba(15, 23, 42, 0.7);
            border: 1px solid rgba(51, 65, 85, 0.3);
            border-radius: 12px;
        }
    """)

    layout = QVBoxLayout(panel)
    layout.setSpacing(16)
    layout.setContentsMargins(16, 16, 16, 16)

    # Enhanced header with logo
    header_widget = QWidget()
    header_widget.setStyleSheet("""
        QWidget {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 rgba(59, 130, 246, 0.1), stop:1 rgba(139, 92, 246, 0.1));
            border: 1px solid rgba(59, 130, 246, 0.3);
            border-radius: 12px;
            padding: 20px;
        }
    """)

    header_layout = QVBoxLayout(header_widget)

    app_logo = QLabel()
    try:
        icon_path = Path(__file__).parent.parent / "alem.png"
        if icon_path.exists():
            pm = QPixmap(str(icon_path))
            app_logo.setPixmap(pm.scaled(QSize(40, 40), Qt.AspectRatioMode.KeepAspectRatio,
                                          Qt.TransformationMode.SmoothTransformation))
    except Exception:
        pass
    app_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
    header_layout.addWidget(app_logo)

    header = QLabel("Alem")
    header.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
    header.setStyleSheet("""
        QLabel { 
            color: #f1f5f9; 
            font-family: 'Segoe UI', system-ui, sans-serif;
            font-weight: 700;
            text-align: center;
            background: transparent;
            border: none;
        }
    """)
    header.setAlignment(Qt.AlignmentFlag.AlignCenter)
    header_layout.addWidget(header)

    tagline = QLabel("Smart Notes")
    tagline.setStyleSheet("""
        QLabel {
            color: #94a3b8;
            font-size: 12px;
            font-weight: 500;
            text-align: center;
            background: transparent;
            border: none;
        }
    """)
    tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
    header_layout.addWidget(tagline)

    layout.addWidget(header_widget)

    # Enhanced search bar with AI toggle
    search_container = QWidget()
    search_container.setStyleSheet("""
        QWidget {
            background: rgba(30, 41, 59, 0.8);
            border: 1px solid rgba(51, 65, 85, 0.3);
            border-radius: 12px;
            padding: 8px;
        }
    """)

    search_layout = QVBoxLayout(search_container)
    search_layout.setSpacing(8)

    # Search input with icon
    search_input_layout = QHBoxLayout()
    search_input_layout.setSpacing(8)

    main_window.search_input = QLineEdit()
    main_window.search_input.setPlaceholderText("Search notes with AI...")
    main_window.search_input.textChanged.connect(main_window.on_search)
    main_window.search_input.setStyleSheet("""
        QLineEdit {
            padding: 12px 16px;
            border: 1px solid rgba(51, 65, 85, 0.3);
            border-radius: 10px;
            background: rgba(15, 23, 42, 0.8);
            color: #e2e8f0;
            font-size: 14px;
            font-family: 'Segoe UI', system-ui, sans-serif;
            font-weight: 400;
        }
        QLineEdit:focus {
            border: 1px solid rgba(59, 130, 246, 0.5);
            background: rgba(15, 23, 42, 0.9);
            color: #f1f5f9;
        }
        QLineEdit::placeholder {
            color: #64748b;
        }
    """)
    search_input_layout.addWidget(main_window.search_input)

    # AI Toggle with enhanced design
    main_window.ai_toggle = QPushButton("AI")
    main_window.ai_toggle.setCheckable(True)
    main_window.ai_toggle.setChecked(True)
    main_window.ai_toggle.setFixedSize(50, 44)
    main_window.ai_toggle.setStyleSheet("""
        QPushButton {
            background: rgba(239, 68, 68, 0.2);
            color: #ef4444;
            border: 1px solid rgba(239, 68, 68, 0.3);
            border-radius: 10px;
            font-weight: 700;
            font-size: 12px;
            font-family: 'Segoe UI', system-ui, sans-serif;
        }
        QPushButton:checked {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 rgba(34, 197, 94, 0.3), stop:1 rgba(59, 130, 246, 0.3));
            color: #22c55e;
            border: 1px solid rgba(34, 197, 94, 0.4);
            /* box-shadow removed for compatibility */
        }
        QPushButton:hover {
            background: rgba(59, 130, 246, 0.2);
            color: #3b82f6;
            border: 1px solid rgba(59, 130, 246, 0.3);
            /* transform removed for compatibility */
        }
    """)
    search_input_layout.addWidget(main_window.ai_toggle)

    search_layout.addLayout(search_input_layout)

    # Search filters
    filters_layout = QHBoxLayout()

    main_window.filter_all = QPushButton("All")
    main_window.filter_recent = QPushButton("Recent")
    main_window.filter_locked = QPushButton("🔒")

    for btn in [main_window.filter_all, main_window.filter_recent, main_window.filter_locked]:
        btn.setCheckable(True)
        btn.setStyleSheet("""
            QPushButton {
                background: rgba(71, 85, 105, 0.3);
                color: #94a3b8;
                border: 1px solid rgba(71, 85, 105, 0.4);
                padding: 6px 12px;
                border-radius: 6px;
                font-weight: 500;
                font-size: 11px;
            }
            QPushButton:checked {
                background: rgba(59, 130, 246, 0.3);
                color: #3b82f6;
                border: 1px solid rgba(59, 130, 246, 0.4);
            }
            QPushButton:hover {
                background: rgba(71, 85, 105, 0.4);
                color: #cbd5e1;
            }
        """)
        filters_layout.addWidget(btn)

    main_window.filter_all.setChecked(True)
    filters_layout.addStretch()

    search_layout.addLayout(filters_layout)
    layout.addWidget(search_container)

    # Enhanced notes list with better styling
    main_window.notes_list = QListWidget()
    main_window.notes_list.itemClicked.connect(main_window.load_selected_note)
    main_window.notes_list.setStyleSheet("""
        QListWidget {
            border: 1px solid rgba(51, 65, 85, 0.3);
            border-radius: 12px;
            background: rgba(30, 41, 59, 0.6);
            color: #e2e8f0;
            padding: 8px;
            font-size: 14px;
            font-family: 'Segoe UI', system-ui, sans-serif;
            outline: none;
        }
        QListWidget::item {
            padding: 16px 12px;
            border-bottom: 1px solid rgba(51, 65, 85, 0.2);
            border-radius: 10px;
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 rgba(15, 23, 42, 0.7), stop:1 rgba(30, 41, 59, 0.5));
            color: #e2e8f0;
            margin: 3px 2px;
            font-weight: 500;
            border: 1px solid rgba(51, 65, 85, 0.2);
        }
        QListWidget::item:selected {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 rgba(59, 130, 246, 0.3), stop:1 rgba(139, 92, 246, 0.2));
            color: #93c5fd;
            border: 1px solid rgba(59, 130, 246, 0.4);
            /* box-shadow removed for compatibility */
        }
        QListWidget::item:hover {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 rgba(71, 85, 105, 0.4), stop:1 rgba(59, 130, 246, 0.2));
            color: #f1f5f9;
            border: 1px solid rgba(71, 85, 105, 0.5);
        }
        QScrollBar:vertical {
            background: rgba(15, 23, 42, 0.4);
            width: 8px;
            border-radius: 4px;
            margin: 0px;
        }
        QScrollBar::handle:vertical {
            background: rgba(71, 85, 105, 0.6);
            border-radius: 4px;
            min-height: 20px;
            margin: 2px;
        }
        QScrollBar::handle:vertical:hover {
            background: rgba(59, 130, 246, 0.6);
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
        }
    """)
    layout.addWidget(main_window.notes_list)

    # Enhanced action buttons
    button_container = QWidget()
    button_container.setStyleSheet("""
        QWidget {
            background: rgba(30, 41, 59, 0.6);
            border: 1px solid rgba(51, 65, 85, 0.3);
            border-radius: 12px;
            padding: 12px;
        }
    """)

    button_layout = QVBoxLayout(button_container)
    button_layout.setSpacing(8)

    # Primary actions
    primary_layout = QHBoxLayout()
    primary_layout.setSpacing(8)

    main_window.new_note_btn = QPushButton("New Note")
    main_window.new_note_btn.clicked.connect(main_window.new_note)
    try:
        main_window.new_note_btn.setIcon(main_window.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
        main_window.new_note_btn.setIconSize(QSize(18, 18))
    except Exception:
        pass
    main_window.new_note_btn.setStyleSheet("""
        QPushButton {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 rgba(59, 130, 246, 0.3), stop:1 rgba(139, 92, 246, 0.2));
            color: #93c5fd;
            border: 1px solid rgba(59, 130, 246, 0.4);
            padding: 12px 16px;
            border-radius: 8px;
            font-weight: 600;
            font-size: 12px;
            font-family: 'Segoe UI', system-ui, sans-serif;
            min-height: 20px;
        }
        QPushButton:hover {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 rgba(59, 130, 246, 0.4), stop:1 rgba(139, 92, 246, 0.3));
            color: #bfdbfe;
            border: 1px solid rgba(59, 130, 246, 0.5);
        }
        QPushButton:pressed {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 rgba(59, 130, 246, 0.5), stop:1 rgba(139, 92, 246, 0.4));
        }
    """)
    primary_layout.addWidget(main_window.new_note_btn)

    main_window.delete_note_btn = QPushButton("🗑 Delete")
    main_window.delete_note_btn.clicked.connect(main_window.delete_note)
    main_window.delete_note_btn.setMinimumWidth(90)
    main_window.delete_note_btn.setFixedHeight(40)
    try:
        main_window.delete_note_btn.setIcon(main_window.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon))
        main_window.delete_note_btn.setIconSize(QSize(16, 16))
    except Exception:
        pass
    main_window.delete_note_btn.setStyleSheet("""
        QPushButton {
            background: rgba(239, 68, 68, 0.25);
            color: #fecaca;
            border: 1px solid rgba(239, 68, 68, 0.5);
            padding: 8px 12px;
            border-radius: 8px;
            font-weight: 600;
            font-size: 11px;
            font-family: 'Segoe UI', system-ui, sans-serif;
            min-height: 20px;
        }
        QPushButton:hover {
            background: rgba(239, 68, 68, 0.35);
            color: #fff;
            border: 1px solid rgba(239, 68, 68, 0.6);
        }
        QPushButton:pressed {
            background: rgba(239, 68, 68, 0.45);
        }
    """)
    primary_layout.addWidget(main_window.delete_note_btn)

    button_layout.addLayout(primary_layout)

    # Secondary actions (remove Import/Export for now)
    secondary_layout = QHBoxLayout()
    secondary_layout.setSpacing(6)

    main_window.settings_btn = QPushButton("Settings")
    try:
        main_window.settings_btn.setIcon(main_window.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView))
        main_window.settings_btn.setIconSize(QSize(14, 14))
    except Exception:
        pass
    main_window.settings_btn.setStyleSheet("""
        QPushButton {
            background: rgba(71, 85, 105, 0.3);
            color: #94a3b8;
            border: 1px solid rgba(71, 85, 105, 0.4);
            padding: 6px 10px;
            border-radius: 6px;
            font-weight: 500;
            font-size: 10px;
            font-family: 'Segoe UI', system-ui, sans-serif;
            min-height: 16px;
        }
        QPushButton:hover {
            background: rgba(71, 85, 105, 0.4);
            color: #cbd5e1;
            border: 1px solid rgba(71, 85, 105, 0.5);
        }
    """)
    secondary_layout.addWidget(main_window.settings_btn)
    main_window.settings_btn.clicked.connect(main_window.show_settings)
    button_layout.addLayout(secondary_layout)

    layout.addWidget(button_container)

    # Enhanced stats panel with real-time metrics
    stats_frame = QFrame()
    stats_frame.setStyleSheet("""
        QFrame {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 rgba(30, 41, 59, 0.8), stop:1 rgba(15, 23, 42, 0.6));
            border: 1px solid rgba(51, 65, 85, 0.3);
            border-radius: 12px;
            padding: 16px;
        }
    """)
    stats_layout = QVBoxLayout(stats_frame)

    stats_title = QLabel("📊 Analytics")
    stats_title.setStyleSheet("""
        QLabel {
            color: #f1f5f9;
            font-weight: 600;
            font-size: 13px;
            margin-bottom: 8px;
            border: none;
            background: transparent;
        }
    """)
    stats_layout.addWidget(stats_title)

    # Stats labels for the left panel
    main_window.cache_label = QLabel("Cache: Ready")
    main_window.notes_count_label = QLabel("Notes: 0")
    main_window.db_size_label = QLabel("Database: 0 KB")

    for label in [main_window.cache_label, main_window.notes_count_label, main_window.db_size_label]:
        label.setFont(QFont("Segoe UI", 10, QFont.Weight.Medium))
        label.setStyleSheet("""
            QLabel { 
                color: #94a3b8; 
                font-family: 'Segoe UI', system-ui, sans-serif;
                font-weight: 500;
                padding: 4px 8px;
                background: rgba(15, 23, 42, 0.5);
                border: 1px solid rgba(51, 65, 85, 0.2);
                border-radius: 6px;
                margin: 2px 0px;
            }
        """)
        stats_layout.addWidget(label)

    layout.addWidget(stats_frame)

    panel.setMinimumWidth(320)
    panel.setMaximumWidth(500)
    return panel
