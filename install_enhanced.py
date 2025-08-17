#!/usr/bin/env python3
"""
Enhanced Installation Script for Alem 2.0
Installs all dependencies and sets up the application for optimal performance.
"""

import sys
import subprocess
import os
import platform
from pathlib import Path
import urllib.request
import json

def print_banner():
    """Print the installation banner"""
    banner = """
    ╔═══════════════════════════════════════════════════════════════╗
    ║                                                               ║
    ║                   🌟 Alem 2.0 Installation 🌟                ║
    ║                                                               ║
    ║           Smart Notes with Modern UI & Advanced Features     ║
    ║                                                               ║
    ╚═══════════════════════════════════════════════════════════════╝
    """
    print(banner)

def check_python_version():
    """Check if Python version is compatible"""
    print("🔍 Checking Python version...")
    if sys.version_info < (3, 8):
        print("❌ Error: Python 3.8 or higher is required")
        print(f"   Current version: {sys.version}")
        sys.exit(1)
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} detected")

def check_system_requirements():
    """Check system requirements"""
    print("\n🔍 Checking system requirements...")
    
    # Check OS
    os_name = platform.system()
    print(f"   Operating System: {os_name}")
    
    # Check available memory
    try:
        import psutil
        memory_gb = psutil.virtual_memory().total / (1024**3)
        print(f"   Available RAM: {memory_gb:.1f} GB")
        if memory_gb < 2:
            print("⚠️  Warning: Low memory detected. App may run slower.")
    except ImportError:
        print("   RAM check skipped (psutil not available)")
    
    print("✅ System requirements check completed")

def install_pip_requirements():
    """Install pip requirements"""
    print("\n📦 Installing Python dependencies...")
    
    requirements_file = Path(__file__).parent / "requirements.txt"
    if not requirements_file.exists():
        print("❌ Error: requirements.txt not found")
        sys.exit(1)
    
    try:
        # Upgrade pip first
        print("   Upgrading pip...")
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "--upgrade", "pip"
        ])
        
        # Install requirements
        print("   Installing requirements...")
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-r", str(requirements_file)
        ])
        
        print("✅ Dependencies installed successfully")
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Error installing dependencies: {e}")
        print("\n🔧 Trying alternative installation methods...")
        
        # Try installing core dependencies individually
        core_deps = [
            "PyQt6>=6.6.0",
            "markdown>=3.5.1",
            "cryptography>=41.0.0",
            "psutil>=5.9.0"
        ]
        
        for dep in core_deps:
            try:
                print(f"   Installing {dep}...")
                subprocess.check_call([
                    sys.executable, "-m", "pip", "install", dep
                ])
            except subprocess.CalledProcessError:
                print(f"⚠️  Warning: Could not install {dep}")
        
        print("✅ Core dependencies installed")

def setup_optional_features():
    """Setup optional features"""
    print("\n⚙️ Setting up optional features...")
    
    # Redis setup
    try:
        import redis
        print("✅ Redis client available - caching enabled")
    except ImportError:
        print("⚠️  Redis not available - install Redis server for caching")
    
    # Discord RPC setup
    try:
        import pypresence
        print("✅ Discord RPC available - rich presence enabled")
    except ImportError:
        print("⚠️  Discord RPC not available")
    
    # WebEngine setup
    try:
        from PyQt6.QtWebEngineWidgets import QWebEngineView
        print("✅ WebEngine available - enhanced preview enabled")
    except ImportError:
        print("⚠️  WebEngine not available - using fallback preview")
    
    # AI features setup
    try:
        import transformers
        print("✅ AI features available - semantic search enabled")
    except ImportError:
        print("⚠️  AI features not available - using text search only")

def create_desktop_shortcut():
    """Create desktop shortcut (Windows only)"""
    if platform.system() != "Windows":
        return
        
    print("\n🔗 Creating desktop shortcut...")
    
    try:
        import winshell
        from win32com.client import Dispatch
        
        desktop = winshell.desktop()
        shortcut_path = os.path.join(desktop, "Alem.lnk")
        target = sys.executable
        arguments = str(Path(__file__).parent / "Alem.py")
        icon_path = Path(__file__).parent / "alem.png"
        
        # Verify icon exists
        if not icon_path.exists():
            print(f"⚠️  Warning: App icon not found at {icon_path}")
            icon = ""  # Use default icon
        else:
            icon = str(icon_path)
        
        shell = Dispatch('WScript.Shell')
        shortcut = shell.CreateShortCut(shortcut_path)
        shortcut.Targetpath = target
        shortcut.Arguments = arguments
        shortcut.WorkingDirectory = str(Path(__file__).parent)
        if icon:
            shortcut.IconLocation = icon
        shortcut.save()
        
        print("✅ Desktop shortcut created")
    except ImportError:
        print("⚠️  Could not create desktop shortcut (missing winshell)")
    except Exception as e:
        print(f"⚠️  Could not create desktop shortcut: {e}")

def verify_installation():
    """Verify the installation"""
    print("\n🧪 Verifying installation...")
    
    try:
        # Test import
        print("   Testing imports...")
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import Qt
        import markdown
        print("✅ Core imports successful")
        
        # Test application startup
        print("   Testing application startup...")
        import subprocess
        result = subprocess.run([
            sys.executable, str(Path(__file__).parent / "Alem.py"), "--test"
        ], capture_output=True, timeout=10)
        
        if result.returncode == 0:
            print("✅ Application startup test passed")
        else:
            print("⚠️  Application startup test failed")
            print(f"   Error: {result.stderr.decode()}")
    
    except Exception as e:
        print(f"⚠️  Verification failed: {e}")

def setup_discord_rpc():
    """Setup Discord RPC application"""
    print("\n🎮 Discord RPC Setup Instructions:")
    print("""
    To enable Discord Rich Presence:
    
    1. Go to https://discord.com/developers/applications
    2. Create a new application named "Alem"
    3. Copy the Application ID
    4. Go to Rich Presence > Art Assets
    5. Upload an icon named "alem"
    6. Update the discord_client_id in config.py with your Application ID
    
    This will show your Alem activity on Discord!
    """)

def main():
    """Main installation function"""
    print_banner()
    
    try:
        check_python_version()
        check_system_requirements()
        install_pip_requirements()
        setup_optional_features()
        
        if platform.system() == "Windows":
            create_desktop_shortcut()
        
        verify_installation()
        setup_discord_rpc()
        
        print("\n" + "="*60)
        print("🎉 Installation completed successfully!")
        print("\nTo start Alem:")
        print(f"   python {Path(__file__).parent / 'Alem.py'}")
        print("\nOr use the launcher:")
        print(f"   python {Path(__file__).parent / 'launch_enhanced.py'}")
        print("\nEnjoy your enhanced note-taking experience! 🌟")
        print("="*60)
        
    except KeyboardInterrupt:
        print("\n❌ Installation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Installation failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
