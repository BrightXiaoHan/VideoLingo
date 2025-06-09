#!/usr/bin/env python3
"""
Test script for VideoLingo Lip Sync functionality
"""

import os
import sys
from pathlib import Path
from rich.console import Console
from rich import print as rprint

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

console = Console()

def test_imports():
    """Test if all required modules can be imported"""
    rprint("[bold blue]Testing imports...[/bold blue]")
    
    try:
        from core._13_lip_sync import apply_lip_sync
        rprint("[bold green]✓ Core lip sync module imported successfully[/bold green]")
    except ImportError as e:
        rprint(f"[bold red]✗ Failed to import core lip sync module: {e}[/bold red]")
        return False
    
    try:
        from core.lip_sync_utils.wav2lip_setup import setup_wav2lip_environment
        rprint("[bold green]✓ Wav2Lip setup module imported successfully[/bold green]")
    except ImportError as e:
        rprint(f"[bold red]✗ Failed to import Wav2Lip setup module: {e}[/bold red]")
        return False
    
    return True

def test_config():
    """Test if configuration is properly set up"""
    rprint("[bold blue]Testing configuration...[/bold blue]")
    
    try:
        from core.utils import load_key
        
        # Check if lipsync is enabled in config
        enable_lipsync = load_key("enable_lip_sync")
        rprint(f"[bold yellow]Lip sync enabled in config: {enable_lipsync}[/bold yellow]")
        
        return True
    except Exception as e:
        rprint(f"[bold red]✗ Configuration test failed: {e}[/bold red]")
        return False

def test_dependencies():
    """Test if required dependencies are available"""
    rprint("[bold blue]Testing dependencies...[/bold blue]")
    
    dependencies = [
        ("cv2", "opencv-python"),
        ("numpy", "numpy"),
        ("torch", "torch"),
        ("requests", "requests")
    ]
    
    all_available = True
    
    for module_name, package_name in dependencies:
        try:
            __import__(module_name)
            rprint(f"[bold green]✓ {package_name} available[/bold green]")
        except ImportError:
            rprint(f"[bold red]✗ {package_name} not available[/bold red]")
            all_available = False
    
    return all_available

def test_face_detection():
    """Test face detection functionality"""
    rprint("[bold blue]Testing face detection...[/bold blue]")
    
    try:
        import cv2
        
        # Test if OpenCV face cascade is available
        face_cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        if os.path.exists(face_cascade_path):
            face_cascade = cv2.CascadeClassifier(face_cascade_path)
            rprint("[bold green]✓ Face detection cascade loaded successfully[/bold green]")
            return True
        else:
            rprint("[bold red]✗ Face detection cascade not found[/bold red]")
            return False
    except Exception as e:
        rprint(f"[bold red]✗ Face detection test failed: {e}[/bold red]")
        return False

def test_output_directory():
    """Test if output directory structure is correct"""
    rprint("[bold blue]Testing output directory...[/bold blue]")
    
    output_dir = Path("output")
    if not output_dir.exists():
        output_dir.mkdir(exist_ok=True)
        rprint("[bold yellow]Created output directory[/bold yellow]")
    
    rprint("[bold green]✓ Output directory structure OK[/bold green]")
    return True

def main():
    """Run all tests"""
    rprint("[bold blue]VideoLingo Lip Sync Test Suite[/bold blue]")
    rprint("=" * 50)
    
    tests = [
        ("Import Test", test_imports),
        ("Configuration Test", test_config),
        ("Dependencies Test", test_dependencies),
        ("Face Detection Test", test_face_detection),
        ("Output Directory Test", test_output_directory)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        rprint(f"\n[bold cyan]{test_name}[/bold cyan]")
        if test_func():
            passed += 1
        else:
            rprint(f"[bold red]{test_name} FAILED[/bold red]")
    
    rprint("\n" + "=" * 50)
    rprint(f"[bold cyan]Test Results: {passed}/{total} tests passed[/bold cyan]")
    
    if passed == total:
        rprint("[bold green]🎉 All tests passed! Lip sync functionality is ready.[/bold green]")
        return True
    else:
        rprint("[bold red]❌ Some tests failed. Please check the issues above.[/bold red]")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 