
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox, QTabWidget, QVBoxLayout, QWidget
)

from config import config as app_config


class SettingsDialog(QDialog):
    """Modern Settings Dialog with Glassmorphism Design"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Alem Settings")
        self.setModal(True)
        self.setMinimumSize(600, 500)
        self.settings_changed = False

        # Apply glassmorphism style
        self.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(15, 23, 42, 0.95), stop:1 rgba(30, 41, 59, 0.95));
                border: 1px solid rgba(51, 65, 85, 0.3);
                border-radius: 16px;
            }
            QTabWidget::pane {
                border: 1px solid rgba(51, 65, 85, 0.3);
                border-radius: 12px;
                background: rgba(30, 41, 59, 0.6);
                padding: 16px;
            }
            QTabBar::tab {
                background: rgba(71, 85, 105, 0.3);
                color: #94a3b8;
                padding: 12px 20px;
                margin: 2px;
                border-radius: 8px;
                font-weight: 500;
                border: 1px solid rgba(71, 85, 105, 0.4);
            }
            QTabBar::tab:selected {
                background: rgba(59, 130, 246, 0.2);
                color: #93c5fd;
                border: 1px solid rgba(59, 130, 246, 0.3);
            }
            QGroupBox {
                color: #e2e8f0;
                font-weight: 600;
                border: 1px solid rgba(51, 65, 85, 0.3);
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 16px;
                background: rgba(15, 23, 42, 0.4);
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 16px;
                padding: 0 8px 0 8px;
                color: #f1f5f9;
            }
            QLabel {
                color: #cbd5e1;
                font-weight: 500;
            }
            QLineEdit, QSpinBox, QComboBox {
                background: rgba(30, 41, 59, 0.8);
                border: 1px solid rgba(51, 65, 85, 0.3);
                border-radius: 6px;
                padding: 8px 12px;
                color: #e2e8f0;
                font-weight: 400;
            }
            QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
                border: 1px solid rgba(59, 130, 246, 0.5);
                background: rgba(30, 41, 59, 0.9);
            }
            QCheckBox {
                color: #cbd5e1;
                font-weight: 500;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 1px solid rgba(51, 65, 85, 0.5);
                background: rgba(30, 41, 59, 0.6);
            }
            QCheckBox::indicator:checked {
                background: rgba(59, 130, 246, 0.3);
                border: 1px solid rgba(59, 130, 246, 0.5);
            }
            QPushButton {
                background: rgba(59, 130, 246, 0.2);
                color: #3b82f6;
                border: 1px solid rgba(59, 130, 246, 0.3);
                padding: 10px 20px;
                border-radius: 8px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: rgba(59, 130, 246, 0.3);
                color: #60a5fa;
            }
            QPushButton:pressed {
                background: rgba(59, 130, 246, 0.4);
            }
        """)

        self.setup_ui()
        self.load_current_settings()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title = QLabel("Settings")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title.setStyleSheet("color: #f1f5f9; margin-bottom: 16px;")
        layout.addWidget(title)

        # Create tabs
        tabs = QTabWidget()
        layout.addWidget(tabs)

        # General tab
        general_tab = self.create_general_tab()
        tabs.addTab(general_tab, "General")

        # Editor tab
        editor_tab = self.create_editor_tab()
        tabs.addTab(editor_tab, "Editor")

        # Advanced tab
        advanced_tab = self.create_advanced_tab()
        tabs.addTab(advanced_tab, "Advanced")

        # Discord tab
        discord_tab = self.create_discord_tab()
        tabs.addTab(discord_tab, "Discord RPC")

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.save_btn = QPushButton("Save Settings")
        self.save_btn.clicked.connect(self.save_settings)
        button_layout.addWidget(self.save_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

    def create_general_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # UI Settings
        ui_group = QGroupBox("User Interface")
        ui_layout = QFormLayout(ui_group)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["dark", "light"])
        ui_layout.addRow("Theme:", self.theme_combo)

        self.font_family_combo = QComboBox()
        self.font_family_combo.addItems(["Segoe UI", "Arial", "Helvetica", "Times New Roman", "Consolas"])
        ui_layout.addRow("Font Family:", self.font_family_combo)

        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 24)
        ui_layout.addRow("Font Size:", self.font_size_spin)

        layout.addWidget(ui_group)

        # Performance Settings
        perf_group = QGroupBox("Performance")
        perf_layout = QFormLayout(perf_group)

        self.auto_save_spin = QSpinBox()
        self.auto_save_spin.setRange(5000, 300000)
        self.auto_save_spin.setSuffix(" ms")
        perf_layout.addRow("Auto-save Interval:", self.auto_save_spin)

        self.search_delay_spin = QSpinBox()
        self.search_delay_spin.setRange(100, 2000)
        self.search_delay_spin.setSuffix(" ms")
        perf_layout.addRow("Search Delay:", self.search_delay_spin)

        self.max_results_spin = QSpinBox()
        self.max_results_spin.setRange(10, 1000)
        perf_layout.addRow("Max Search Results:", self.max_results_spin)

        layout.addWidget(perf_group)
        layout.addStretch()

        return widget

    def create_editor_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Editor Settings
        editor_group = QGroupBox("Editor Options")
        editor_layout = QFormLayout(editor_group)

        self.default_format_combo = QComboBox()
        self.default_format_combo.addItems(["html", "markdown"])
        editor_layout.addRow("Default Format:", self.default_format_combo)

        self.ai_search_check = QCheckBox("Enable AI Search")
        editor_layout.addRow("AI Features:", self.ai_search_check)

        self.model_cache_check = QCheckBox("Cache AI Models")
        editor_layout.addRow("", self.model_cache_check)

        layout.addWidget(editor_group)

        # Markdown Settings
        md_group = QGroupBox("Markdown Options")
        md_layout = QVBoxLayout(md_group)

        self.fenced_code_check = QCheckBox("Fenced Code Blocks")
        self.tables_check = QCheckBox("Tables")
        self.toc_check = QCheckBox("Table of Contents")
        self.codehilite_check = QCheckBox("Code Highlighting")

        for check in [self.fenced_code_check, self.tables_check, self.toc_check, self.codehilite_check]:
            md_layout.addWidget(check)

        layout.addWidget(md_group)
        layout.addStretch()

        return widget

    def create_advanced_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Redis Settings
        redis_group = QGroupBox("Redis Cache")
        redis_layout = QFormLayout(redis_group)

        self.redis_enabled_check = QCheckBox("Enable Redis")
        redis_layout.addRow("Cache:", self.redis_enabled_check)

        self.redis_host_edit = QLineEdit()
        redis_layout.addRow("Host:", self.redis_host_edit)

        self.redis_port_spin = QSpinBox()
        self.redis_port_spin.setRange(1, 65535)
        redis_layout.addRow("Port:", self.redis_port_spin)

        self.redis_db_spin = QSpinBox()
        self.redis_db_spin.setRange(0, 15)
        redis_layout.addRow("Database:", self.redis_db_spin)

        self.redis_flush_spin = QSpinBox()
        self.redis_flush_spin.setRange(10, 600)
        self.redis_flush_spin.setSuffix(" sec")
        redis_layout.addRow("Flush Interval:", self.redis_flush_spin)

        layout.addWidget(redis_group)

        # Security Settings
        security_group = QGroupBox("Security")
        security_layout = QFormLayout(security_group)

        self.kdf_iterations_spin = QSpinBox()
        self.kdf_iterations_spin.setRange(100000, 1000000)
        self.kdf_iterations_spin.setSuffix(" iterations")
        security_layout.addRow("KDF Iterations:", self.kdf_iterations_spin)

        layout.addWidget(security_group)
        layout.addStretch()

        return widget

    def create_discord_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Discord RPC Settings
        discord_group = QGroupBox("Discord Rich Presence")
        discord_layout = QFormLayout(discord_group)

        self.discord_enabled_check = QCheckBox("Enable Discord RPC")
        discord_layout.addRow("Status:", self.discord_enabled_check)

        self.discord_client_id_edit = QLineEdit()
        discord_layout.addRow("Client ID:", self.discord_client_id_edit)

        self.discord_large_image_edit = QLineEdit()
        discord_layout.addRow("Large Image Key:", self.discord_large_image_edit)

        self.discord_large_text_edit = QLineEdit()
        discord_layout.addRow("Large Text:", self.discord_large_text_edit)

        self.discord_update_spin = QSpinBox()
        self.discord_update_spin.setRange(1, 300)
        self.discord_update_spin.setSuffix(" sec")
        discord_layout.addRow("Update Interval:", self.discord_update_spin)

        layout.addWidget(discord_group)

        # Info
        info_label = QLabel("💡 Configure Discord RPC to show your activity while using Alem")
        info_label.setStyleSheet("color: #64748b; font-style: italic; margin-top: 16px;")
        layout.addWidget(info_label)

        layout.addStretch()
        return widget

    def load_current_settings(self):
        """Load current settings into the dialog"""
        if not app_config:
            return

        # General
        self.theme_combo.setCurrentText(app_config.get('theme', 'dark'))
        self.font_family_combo.setCurrentText(app_config.get('font_family', 'Segoe UI'))
        self.font_size_spin.setValue(app_config.get('font_size', 13))
        self.auto_save_spin.setValue(app_config.get('auto_save_interval', 30000))
        self.search_delay_spin.setValue(app_config.get('search_debounce_delay', 300))
        self.max_results_spin.setValue(app_config.get('max_search_results', 100))

        # Editor
        self.default_format_combo.setCurrentText(app_config.get('default_content_format', 'html'))
        self.ai_search_check.setChecked(app_config.get('ai_search_enabled', True))
        self.model_cache_check.setChecked(app_config.get('ai_model_cache', True))

        # Markdown
        extensions = app_config.get('markdown_extensions', [])
        self.fenced_code_check.setChecked('fenced_code' in extensions)
        self.tables_check.setChecked('tables' in extensions)
        self.toc_check.setChecked('toc' in extensions)
        self.codehilite_check.setChecked('codehilite' in extensions)

        # Redis
        self.redis_enabled_check.setChecked(app_config.get('redis_enabled', True))
        self.redis_host_edit.setText(app_config.get('redis_host', 'localhost'))
        self.redis_port_spin.setValue(app_config.get('redis_port', 6379))
        self.redis_db_spin.setValue(app_config.get('redis_db', 0))
        self.redis_flush_spin.setValue(app_config.get('redis_flush_interval_s', 60))

        # Security
        self.kdf_iterations_spin.setValue(app_config.get('kdf_iterations', 390000))

        # Discord
        self.discord_enabled_check.setChecked(app_config.get('discord_rpc_enabled', True))
        self.discord_client_id_edit.setText(app_config.get('discord_client_id', ''))
        self.discord_large_image_edit.setText(app_config.get('discord_large_image', 'alem'))
        self.discord_large_text_edit.setText(app_config.get('discord_large_text', 'Alem - Smart Notes'))
        self.discord_update_spin.setValue(app_config.get('discord_update_interval_s', 15))

    def save_settings(self):
        """Save settings and apply changes"""
        if not app_config:
            return

        # General
        app_config.set('theme', self.theme_combo.currentText())
        app_config.set('font_family', self.font_family_combo.currentText())
        app_config.set('font_size', self.font_size_spin.value())
        app_config.set('auto_save_interval', self.auto_save_spin.value())
        app_config.set('search_debounce_delay', self.search_delay_spin.value())
        app_config.set('max_search_results', self.max_results_spin.value())

        # Editor
        app_config.set('default_content_format', self.default_format_combo.currentText())
        app_config.set('ai_search_enabled', self.ai_search_check.isChecked())
        app_config.set('ai_model_cache', self.model_cache_check.isChecked())

        # Markdown extensions
        extensions = []
        if self.fenced_code_check.isChecked():
            extensions.append('fenced_code')
        if self.tables_check.isChecked():
            extensions.append('tables')
        if self.toc_check.isChecked():
            extensions.append('toc')
        if self.codehilite_check.isChecked():
            extensions.append('codehilite')
        app_config.set('markdown_extensions', extensions)

        # Redis
        app_config.set('redis_enabled', self.redis_enabled_check.isChecked())
        app_config.set('redis_host', self.redis_host_edit.text())
        app_config.set('redis_port', self.redis_port_spin.value())
        app_config.set('redis_db', self.redis_db_spin.value())
        app_config.set('redis_flush_interval_s', self.redis_flush_spin.value())

        # Security
        app_config.set('kdf_iterations', self.kdf_iterations_spin.value())

        # Discord
        app_config.set('discord_rpc_enabled', self.discord_enabled_check.isChecked())
        app_config.set('discord_client_id', self.discord_client_id_edit.text())
        app_config.set('discord_large_image', self.discord_large_image_edit.text())
        app_config.set('discord_large_text', self.discord_large_text_edit.text())
        app_config.set('discord_update_interval_s', self.discord_update_spin.value())

        self.settings_changed = True
        self.accept()
