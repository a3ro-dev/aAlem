#!/usr/bin/env python3
"""
Enhanced Launcher for Alem 2.0
Provides startup diagnostics, performance monitoring, and environment checks.
"""

import sys
import os
import time
import subprocess
from pathlib import Path
import logging
from datetime import datetime

def setup_logging():
    """Setup logging for the launcher"""
    log_dir = Path.home() / ".alem" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_file = log_dir / f"alem_launcher_{datetime.now().strftime('%Y%m%d')}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

def print_startup_banner():
    """Print the startup banner"""
    banner = """
    ╔═══════════════════════════════════════════════════════════════╗
    ║                                                               ║
    ║                     🚀 Launching Alem 2.0 🚀                 ║
    ║                                                               ║
    ║              Smart Notes • Modern UI • AI-Powered            ║
    ║                                                               ║
    ╚═══════════════════════════════════════════════════════════════╝
    """
    print(banner)

def check_environment(logger):
    """Check the environment before launching"""
    logger.info("🔍 Performing environment checks...")
    
    issues = []
    
    # Check Python version
    if sys.version_info < (3, 8):
        issues.append(f"Python {sys.version} is too old. Requires 3.8+")
    else:
        logger.info(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} detected")
    
    # Check critical dependencies
    critical_deps = {
        'PyQt6': 'PyQt6',
        'markdown': 'markdown',
        'cryptography': 'cryptography',
    }
    
    for name, module in critical_deps.items():
        try:
            __import__(module)
            logger.info(f"✅ {name} available")
        except ImportError:
            issues.append(f"Missing critical dependency: {name}")
    
    # Check optional dependencies
    optional_deps = {
        'Redis': 'redis',
        'Discord RPC': 'pypresence',
        'WebEngine': 'PyQt6.QtWebEngineWidgets',
        'Performance Monitor': 'psutil',
        'AI Features': 'transformers'
    }
    
    available_features = []
    for name, module in optional_deps.items():
        try:
            __import__(module)
            available_features.append(name)
            logger.info(f"✅ {name} available")
        except ImportError:
            logger.info(f"⚠️  {name} not available")
    
    # Check for Alem.py
    app_file = Path(__file__).parent / "Alem.py"
    if not app_file.exists():
        issues.append("Alem.py not found in the same directory")
    
    return issues, available_features

def check_system_resources(logger):
    """Check system resources"""
    logger.info("💻 Checking system resources...")
    
    try:
        import psutil
        
        # Memory check
        memory = psutil.virtual_memory()
        memory_gb = memory.total / (1024**3)
        memory_available_gb = memory.available / (1024**3)
        
        logger.info(f"   RAM: {memory_available_gb:.1f}GB available of {memory_gb:.1f}GB total")
        
        if memory_available_gb < 1:
            logger.warning("⚠️  Low memory warning: Less than 1GB available")
        
        # Disk check
        disk = psutil.disk_usage(Path.home())
        disk_free_gb = disk.free / (1024**3)
        
        logger.info(f"   Disk: {disk_free_gb:.1f}GB free space")
        
        if disk_free_gb < 1:
            logger.warning("⚠️  Low disk space warning: Less than 1GB free")
        
        # CPU check
        cpu_count = psutil.cpu_count()
        logger.info(f"   CPU: {cpu_count} cores")
        
    except ImportError:
        logger.info("   Resource monitoring not available (psutil not installed)")

def check_redis_connection(logger):
    """Check Redis connection if available"""
    try:
        import redis
        
        logger.info("🔄 Checking Redis connection...")
        
        try:
            r = redis.Redis(host='localhost', port=6379, db=0, socket_timeout=2)
            r.ping()
            logger.info("✅ Redis server is running - caching enabled")
            return True
        except (redis.ConnectionError, redis.TimeoutError):
            logger.info("⚠️  Redis server not running - caching disabled")
            return False
    except ImportError:
        logger.info("⚠️  Redis client not available")
        return False

def launch_application(logger, debug_mode=False):
    """Launch the main application"""
    logger.info("🚀 Starting Alem application...")
    
    app_file = Path(__file__).parent / "Alem.py"
    
    # Prepare launch arguments
    args = [sys.executable, str(app_file)]
    
    if debug_mode:
        args.append("--debug")
    
    # Set environment variables for better performance
    env = os.environ.copy()
    env['QT_AUTO_SCREEN_SCALE_FACTOR'] = '1'
    env['QT_ENABLE_HIGHDPI_SCALING'] = '1'
    
    try:
        # Launch with performance monitoring
        start_time = time.time()
        
        process = subprocess.Popen(
            args,
            env=env,
            cwd=Path(__file__).parent
        )
        
        # Wait a moment to check if app started successfully
        time.sleep(2)
        
        if process.poll() is None:
            startup_time = time.time() - start_time
            logger.info(f"✅ Application launched successfully in {startup_time:.2f}s")
            logger.info(f"   Process ID: {process.pid}")
            
            # Wait for application to finish
            return_code = process.wait()
            
            if return_code == 0:
                logger.info("✅ Application closed normally")
            else:
                logger.warning(f"⚠️  Application exited with code {return_code}")
            
            return return_code
        else:
            logger.error(f"❌ Application failed to start (exit code: {process.returncode})")
            return process.returncode
            
    except FileNotFoundError:
        logger.error("❌ Python interpreter not found")
        return 1
    except Exception as e:
        logger.error(f"❌ Failed to launch application: {e}")
        return 1

def show_performance_summary(logger, available_features, redis_available):
    """Show performance summary"""
    print("\n" + "="*60)
    print("📊 PERFORMANCE SUMMARY")
    print("="*60)
    
    print(f"🎯 Available Features: {len(available_features)}")
    for feature in available_features:
        print(f"   ✅ {feature}")
    
    if redis_available:
        print("🚀 Performance Mode: HIGH (Redis caching enabled)")
    else:
        print("⚡ Performance Mode: STANDARD (No caching)")
    
    print("\n💡 Tips for better performance:")
    if not redis_available:
        print("   • Install and start Redis server for caching")
    print("   • Close unused applications to free memory")
    print("   • Use SSD storage for better database performance")
    print("="*60)

def main():
    """Main launcher function"""
    print_startup_banner()
    
    # Setup logging
    logger = setup_logging()
    logger.info("Alem 2.0 Launcher started")
    
    try:
        # Environment checks
        issues, available_features = check_environment(logger)
        
        if issues:
            print("\n❌ CRITICAL ISSUES FOUND:")
            for issue in issues:
                print(f"   • {issue}")
            print("\nPlease run the installation script first:")
            print("   python install_enhanced.py")
            return 1
        
        # System resource checks
        check_system_resources(logger)
        
        # Redis connection check
        redis_available = check_redis_connection(logger)
        
        # Show performance summary
        show_performance_summary(logger, available_features, redis_available)
        
        # Launch application
        print("\n🚀 Launching Alem...")
        return_code = launch_application(logger, debug_mode="--debug" in sys.argv)
        
        print("\n👋 Thanks for using Alem!")
        return return_code
        
    except KeyboardInterrupt:
        logger.info("Launcher interrupted by user")
        print("\n👋 Launch cancelled")
        return 1
    except Exception as e:
        logger.error(f"Launcher error: {e}")
        print(f"\n❌ Launcher error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
