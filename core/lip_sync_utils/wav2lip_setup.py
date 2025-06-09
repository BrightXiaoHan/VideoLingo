import os
import subprocess
import requests
import zipfile
from pathlib import Path
import shutil
from rich.console import Console
from rich import print as rprint

console = Console()

# ------------
# Model URLs and checksums
# ------------
MODEL_URLS = {
    "wav2lip_gan.pth": {
        "url": "https://iiitaphyd-my.sharepoint.com/:u:/g/personal/radrabha_m_research_iiit_ac_in/EdjI7bZlgApMqsVoEUUXpLsBxqXbn5z8VTmoxp55YNDcIA?e=n9ljGW&download=1",
        "size": 148917889  # bytes
    },
    "wav2lip.pth": {
        "url": "https://iiitaphyd-my.sharepoint.com/:u:/g/personal/radrabha_m_research_iiit_ac_in/Eb3LEzbfuKlJiR600lQWRxgBIY27JZg80f7V9jtMfbNDaQ?e=TBFBVW&download=1", 
        "size": 148917889  # bytes
    },
    "s3fd.pth": {
        "url": "https://www.adrianbulat.com/downloads/python-fan/s3fd-619a316812.pth",
        "size": 89843225  # bytes
    }
}

def setup_wav2lip_environment():
    """Setup Easy-Wav2Lip environment with automatic model downloads"""
    
    wav2lip_dir = os.path.join("core", "lip_sync_utils", "Easy-Wav2Lip")
    
    # Clone Easy-Wav2Lip if not exists
    if not os.path.exists(wav2lip_dir):
        rprint("[bold blue]Setting up Easy-Wav2Lip environment...[/bold blue]")
        if not clone_wav2lip_repo(wav2lip_dir):
            return None
    
    # Install requirements
    if not install_wav2lip_requirements(wav2lip_dir):
        return None
    
    # Download models
    if not download_wav2lip_models(wav2lip_dir):
        return None
    
    rprint("[bold green]Easy-Wav2Lip environment setup complete![/bold green]")
    return wav2lip_dir

def clone_wav2lip_repo(wav2lip_dir):
    """Clone the Easy-Wav2Lip repository"""
    try:
        # Create parent directory
        os.makedirs(os.path.dirname(wav2lip_dir), exist_ok=True)
        
        # Clone repository
        subprocess.run([
            'git', 'clone', 
            'https://github.com/anothermartz/Easy-Wav2Lip.git',
            wav2lip_dir
        ], check=True, capture_output=True)
        
        rprint("[bold green]Successfully cloned Easy-Wav2Lip repository[/bold green]")
        return True
        
    except subprocess.CalledProcessError as e:
        rprint(f"[bold red]Failed to clone Easy-Wav2Lip: {e}[/bold red]")
        return False

def install_wav2lip_requirements(wav2lip_dir):
    """Install Easy-Wav2Lip requirements"""
    requirements_file = os.path.join(wav2lip_dir, "requirements.txt")
    
    if not os.path.exists(requirements_file):
        rprint("[bold yellow]No requirements.txt found in Easy-Wav2Lip[/bold yellow]")
        return True
    
    try:
        rprint("[bold blue]Installing Easy-Wav2Lip requirements...[/bold blue]")
        subprocess.run([
            'pip', 'install', '-r', requirements_file
        ], check=True, capture_output=True)
        
        rprint("[bold green]Successfully installed Easy-Wav2Lip requirements[/bold green]")
        return True
        
    except subprocess.CalledProcessError as e:
        rprint(f"[bold red]Failed to install requirements: {e}[/bold red]")
        return False

def download_wav2lip_models(wav2lip_dir):
    """Download required models for Wav2Lip"""
    
    # Setup directories
    checkpoints_dir = os.path.join(wav2lip_dir, "checkpoints")
    face_detection_dir = os.path.join(wav2lip_dir, "face_detection", "detection", "sfd")
    
    os.makedirs(checkpoints_dir, exist_ok=True)
    os.makedirs(face_detection_dir, exist_ok=True)
    
    # Download models
    models_to_download = [
        ("wav2lip_gan.pth", checkpoints_dir),
        ("wav2lip.pth", checkpoints_dir),
        ("s3fd.pth", face_detection_dir)
    ]
    
    for model_name, target_dir in models_to_download:
        model_path = os.path.join(target_dir, model_name)
        
        if os.path.exists(model_path):
            # Check file size
            file_size = os.path.getsize(model_path)
            expected_size = MODEL_URLS[model_name]["size"]
            
            if file_size == expected_size:
                rprint(f"[bold green]{model_name} already exists and is valid[/bold green]")
                continue
            else:
                rprint(f"[bold yellow]{model_name} exists but size mismatch, re-downloading...[/bold yellow]")
                os.remove(model_path)
        
        if not download_model(model_name, model_path):
            return False
    
    return True

def download_model(model_name, target_path):
    """Download a single model file"""
    
    if model_name not in MODEL_URLS:
        rprint(f"[bold red]Unknown model: {model_name}[/bold red]")
        return False
    
    url = MODEL_URLS[model_name]["url"]
    expected_size = MODEL_URLS[model_name]["size"]
    
    try:
        rprint(f"[bold blue]Downloading {model_name}...[/bold blue]")
        
        # Download with progress
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded_size = 0
        
        with open(target_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded_size += len(chunk)
                    
                    # Show progress
                    if total_size > 0:
                        progress = (downloaded_size / total_size) * 100
                        print(f"\rProgress: {progress:.1f}%", end='', flush=True)
        
        print()  # New line after progress
        
        # Verify download
        file_size = os.path.getsize(target_path)
        if file_size != expected_size:
            rprint(f"[bold red]Size mismatch for {model_name}: {file_size} != {expected_size}[/bold red]")
            os.remove(target_path)
            return False
        
        rprint(f"[bold green]Successfully downloaded {model_name}[/bold green]")
        return True
        
    except Exception as e:
        rprint(f"[bold red]Failed to download {model_name}: {e}[/bold red]")
        if os.path.exists(target_path):
            os.remove(target_path)
        return False

def create_wav2lip_inference_script():
    """Create a simplified inference script for VideoLingo integration"""
    
    script_content = '''
import os
import sys
import argparse
import cv2
import numpy as np
import torch
from pathlib import Path

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def run_wav2lip_inference(checkpoint_path, face_path, audio_path, output_path, 
                         resize_factor=1.0, padding=[0, 10, 0, 0], no_smooth=True):
    """Run Wav2Lip inference with simplified interface"""
    
    try:
        # Import Wav2Lip modules
        from inference import main as wav2lip_main
        
        # Prepare arguments
        args = argparse.Namespace(
            checkpoint_path=checkpoint_path,
            face=face_path,
            audio=audio_path,
            outfile=output_path,
            static=False,
            fps=25,
            pads=padding,
            face_det_batch_size=16,
            wav2lip_batch_size=128,
            resize_factor=resize_factor,
            crop=[0, -1, 0, -1],
            box=[-1, -1, -1, -1],
            rotate=0,
            nosmooth=no_smooth
        )
        
        # Run inference
        wav2lip_main(args)
        return True
        
    except Exception as e:
        print(f"Error during Wav2Lip inference: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint_path", required=True)
    parser.add_argument("--face", required=True)
    parser.add_argument("--audio", required=True)
    parser.add_argument("--outfile", required=True)
    parser.add_argument("--resize_factor", type=float, default=1.0)
    parser.add_argument("--pads", nargs=4, type=int, default=[0, 10, 0, 0])
    parser.add_argument("--nosmooth", action="store_true")
    
    args = parser.parse_args()
    
    success = run_wav2lip_inference(
        args.checkpoint_path,
        args.face,
        args.audio,
        args.outfile,
        args.resize_factor,
        args.pads,
        args.nosmooth
    )
    
    sys.exit(0 if success else 1)
'''
    
    return script_content

def verify_wav2lip_installation(wav2lip_dir):
    """Verify that Wav2Lip is properly installed and functional"""
    
    # Check if directory exists
    if not os.path.exists(wav2lip_dir):
        return False
    
    # Check for required files
    required_files = [
        "inference.py",
        "models/wav2lip.py",
        "face_detection/api.py"
    ]
    
    for file_path in required_files:
        full_path = os.path.join(wav2lip_dir, file_path)
        if not os.path.exists(full_path):
            rprint(f"[bold red]Missing required file: {file_path}[/bold red]")
            return False
    
    # Check for model files
    model_files = [
        "checkpoints/wav2lip_gan.pth",
        "checkpoints/wav2lip.pth", 
        "face_detection/detection/sfd/s3fd.pth"
    ]
    
    for model_file in model_files:
        full_path = os.path.join(wav2lip_dir, model_file)
        if not os.path.exists(full_path):
            rprint(f"[bold red]Missing model file: {model_file}[/bold red]")
            return False
    
    rprint("[bold green]Wav2Lip installation verified successfully[/bold green]")
    return True 