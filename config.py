"""
Configuration settings for Alem application
"""
import os
from pathlib import Path
from typing import Dict, Any

# Application constants
APP_NAME = "Alem"
APP_VERSION = "1.1.1"
APP_AUTHOR = "a3ro-dev"

# Default settings
DEFAULT_SETTINGS = {
    # UI Settings
    "window_width": 1400,
    "window_height": 900,
    "font_family": "Segoe UI",
    "font_size": 13,
    "theme": "dark",
    
    # Editor Settings
    "auto_save_interval": 30000,  # milliseconds
    "search_debounce_delay": 300,  # milliseconds
    "max_recent_files": 10,
    
    # Database Settings
    "db_backup_enabled": True,
    "db_backup_interval": 24,  # hours
    "max_db_size_mb": 100,
    
    # Performance Settings
    "max_search_results": 100,
    "enable_performance_metrics": True,
    "log_level": "INFO",
    
    # AI Settings
    "ai_search_enabled": True,
    "ai_model_cache": True,

    # Markdown / Editor Modes
    "default_content_format": "html",  # 'html' or 'markdown'
    "markdown_extensions": [
        "fenced_code", "codehilite", "tables", "toc"
    ],

    # Redis Cache
    "redis_enabled": True,
    "redis_host": "localhost",
    "redis_port": 6379,
    "redis_db": 0,
    "redis_flush_interval_s": 60,  # periodic flush to DB

    # Discord Rich Presence
    "discord_rpc_enabled": True,
    "discord_client_id": "1405965776325967872",  # replace with your Discord app client id
    "discord_large_image": "alem",  # asset key configured in Discord Dev Portal
    "discord_large_text": "Alem - Smart Notes",
    "discord_buttons": [
        {"label": "GitHub", "url": "https://github.com/a3ro-dev/aAlem"}
    ],
    "discord_update_interval_s": 1,

    # Security (password protection)
    "kdf_iterations": 390000,
}

# Color themes
THEMES = {
    "dark": {
        "primary": "#0a0f1c",
        "secondary": "#0d1421", 
        "accent": "#3b82f6",
        "text": "#e2e8f0",
        "background": "#111827"
    },
    "light": {
        "primary": "#f8fafc",
        "secondary": "#f1f5f9",
        "accent": "#3b82f6", 
        "text": "#1e293b",
        "background": "#ffffff"
    }
}

def get_config_dir() -> Path:
    """Get the configuration directory"""
    config_dir = Path.home() / ".config" / "alem"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir

def get_data_dir() -> Path:
    """Get the data directory"""
    if os.name == 'nt':  # Windows
        data_dir = Path(os.environ.get('APPDATA', Path.home())) / "Alem"
    else:  # Linux/macOS
        data_dir = Path.home() / ".local" / "share" / "alem"
    
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir

def get_log_dir() -> Path:
    """Get the log directory"""
    log_dir = get_data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir

class AppConfig:
    """Application configuration manager"""
    
    def __init__(self):
        self.settings = DEFAULT_SETTINGS.copy()
        self.config_file = get_config_dir() / "settings.json"
        self.load_config()
    
    def load_config(self):
        """Load configuration from file"""
        if self.config_file.exists():
            try:
                import json
                with open(self.config_file, 'r') as f:
                    user_settings = json.load(f)
                    self.settings.update(user_settings)
            except Exception as e:
                print(f"Warning: Could not load config: {e}")
    
    def save_config(self):
        """Save configuration to file"""
        try:
            import json
            with open(self.config_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save config: {e}")
    
    def get(self, key: str, default=None):
        """Get a configuration value"""
        return self.settings.get(key, default)
    
    def set(self, key: str, value: Any):
        """Set a configuration value"""
        self.settings[key] = value
        self.save_config()
    
    def get_theme(self, theme_name: str = None) -> Dict[str, str]:
        """Get theme colors"""
        theme_name = theme_name or self.get("theme", "dark")
        return THEMES.get(theme_name, THEMES["dark"])

# Global config instance
config = AppConfig()
