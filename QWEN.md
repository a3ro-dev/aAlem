# Alem 2.0 - Smart Notes Application

## Project Overview
Alem 2.0 is a modern, feature-rich note-taking application with a glassmorphism UI design, built using Python and PyQt6. It offers advanced features like Redis caching, Discord Rich Presence, encryption for password-protected notes, and AI-powered semantic search.

## Key Features
- **Glassmorphism UI**: Modern translucent design with dark theme
- **Dual Editing Modes**: Markdown and HTML editing with live preview
- **Rich Text Editing**: WYSIWYG editor with formatting toolbar
- **Advanced Search**: Real-time text search with AI semantic search option
- **Password Protection**: AES encryption with PBKDF2 key derivation
- **Redis Caching**: High-performance caching layer for improved responsiveness
- **Discord Rich Presence**: Shows note-taking activity on Discord
- **Comprehensive Analytics**: Real-time performance metrics in status bar
- **Cross-platform**: Works on Windows, Linux, and macOS

## Project Structure
```
aAlem/
├── alem_app/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── cache.py          # Redis caching implementation
│   │   └── discord_rpc.py    # Discord Rich Presence integration
│   ├── database/
│   │   ├── __init__.py
│   │   └── database.py       # SQLite database with Note model
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── actions.py        # Menu and shortcut setup
│   │   ├── left_panel.py     # Sidebar UI components
│   │   ├── main_window.py    # Main application window
│   │   ├── right_panel.py    # Editor and preview panels
│   │   └── settings_dialog.py # Application settings UI
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── encryption.py     # Note encryption/decryption
│   │   └── logging.py        # Application logging
│   └── main.py               # Application entry point
├── Alem.py                   # Main application launcher
├── config.py                 # Application configuration
├── install_enhanced.py       # Enhanced installation script
├── launch_enhanced.py        # Enhanced launcher with diagnostics
├── requirements.txt          # Python dependencies
├── alem.png                  # Application icon
└── README.md                 # Project documentation
```

## Core Components

### Main Application (alem_app/main.py)
- Entry point with enhanced setup
- Application configuration and styling
- Exception handling and error reporting
- Welcome message for first-time users
- Discord RPC timer management

### Main Window (alem_app/ui/main_window.py)
- Primary UI with split-panel layout
- Note management (create, save, delete, load)
- Search functionality with debouncing
- Markdown/HTML preview rendering
- Analytics and performance monitoring
- Keyboard shortcuts and menu actions
- Responsive design with resize handling

### Database (alem_app/database/database.py)
- SQLite database implementation
- Note model with encryption support
- CRUD operations for notes
- Search functionality
- Statistics and performance metrics

### Redis Cache (alem_app/core/cache.py)
- Redis caching manager for notes
- Dirty note tracking for periodic flush
- Performance optimization through caching

### Encryption (alem_app/utils/encryption.py)
- AES encryption using Fernet
- PBKDF2 key derivation with configurable iterations
- Password-based note protection

### Discord RPC (alem_app/core/discord_rpc.py)
- Discord Rich Presence integration
- Activity updates with customizable details
- Presence management with buttons

## Dependencies
Key dependencies include:
- PyQt6: GUI framework
- PyQt6-WebEngine: Web-based preview rendering
- markdown: Markdown processing
- redis: Caching layer
- cryptography: Note encryption
- pypresence: Discord integration
- psutil: System monitoring

## Installation & Setup
1. Run `python install_enhanced.py` for full installation
2. Configure Discord RPC in config.py (optional)
3. Start Redis server for caching (optional)
4. Launch with `python launch_enhanced.py` or `python Alem.py`

## Configuration
Main configuration is in `config.py`:
- UI settings (themes, fonts, window size)
- Performance settings (cache intervals, search debounce)
- Redis configuration
- Discord RPC settings
- Security parameters (KDF iterations)

## Keyboard Shortcuts
- `Ctrl+N`: New note
- `Ctrl+S`: Save note
- `Ctrl+O`: Quick open
- `Ctrl+F`: Search notes
- `Ctrl+L`: Lock/unlock note
- `Ctrl+1/2`: Switch edit/preview modes
- `F5`: Refresh preview
- `F11`: Toggle fullscreen

## Development Notes
- Uses modern PyQt6 with Fusion style
- Implements lazy loading for performance
- Background processing for non-blocking operations
- Comprehensive error handling and logging
- Responsive UI with adaptive layouts