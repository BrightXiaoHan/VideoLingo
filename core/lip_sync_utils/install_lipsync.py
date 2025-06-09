#!/usr/bin/env python3

import subprocess
import sys
import os
from rich.console import Console
from rich import print as rprint

console = Console()

def install_lipsync_dependencies():
    """Install dependencies required for lip sync functionality"""
    
    rprint("[bold blue]Installing lip sync dependencies...[/bold blue]")
    
    # List of packages to install
    packages = [
        "torch>=1.9.0",
        "torchvision>=0.10.0", 
        "torchaudio>=0.9.0",
        "face-alignment",
        "gfpgan",
        "basicsr",
        "facexlib",
        "realesrgan",
        "scipy",
        "scikit-image",
        "dlib"
    ]
    
    for package in packages:
        try:
            rprint(f"[bold yellow]Installing {package}...[/bold yellow]")
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", package
            ])
            rprint(f"[bold green]✓ Successfully installed {package}[/bold green]")
        except subprocess.CalledProcessError as e:
            rprint(f"[bold red]✗ Failed to install {package}: {e}[/bold red]")
            return False
    
    rprint("[bold green]All lip sync dependencies installed successfully![/bold green]")
    return True

def check_gpu_availability():
    """Check if CUDA is available for GPU acceleration"""
    try:
        import torch
        if torch.cuda.is_available():
            gpu_count = torch.cuda.device_count()
            gpu_name = torch.cuda.get_device_name(0)
            rprint(f"[bold green]GPU detected: {gpu_name} (Count: {gpu_count})[/bold green]")
            return True
        else:
            rprint("[bold yellow]No GPU detected. Lip sync will run on CPU (slower).[/bold yellow]")
            return False
    except ImportError:
        rprint("[bold red]PyTorch not installed. Please install PyTorch first.[/bold red]")
        return False

if __name__ == "__main__":
    rprint("[bold blue]Setting up VideoLingo Lip Sync functionality...[/bold blue]")
    
    if install_lipsync_dependencies():
        check_gpu_availability()
        rprint("[bold green]Lip sync setup complete! 🎭[/bold green]")
    else:
        rprint("[bold red]Lip sync setup failed! ❌[/bold red]")
        sys.exit(1) 