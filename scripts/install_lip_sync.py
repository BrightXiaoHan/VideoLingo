#!/usr/bin/env python3
"""
Installation script for VideoLingo Lip Sync functionality
This script sets up Wav2Lip and downloads required models
"""

import os
import subprocess
import sys
from pathlib import Path

def run_command(cmd, description=""):
    """Run a command and handle errors"""
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"Error: {description} failed")
        print(f"Error output: {result.stderr}")
        return False
    
    print(f"Success: {description} completed")
    return True

def install_dependencies():
    """Install required Python packages for lip sync"""
    print("Installing lip sync dependencies...")
    
    dependencies = [
        "torch>=1.9.0",
        "torchvision>=0.10.0", 
        "face-alignment>=1.3.5",
        "scipy>=1.7.0",
        "gdown>=4.6.0"
    ]
    
    for dep in dependencies:
        if not run_command([sys.executable, "-m", "pip", "install", dep], 
                          f"Installing {dep}"):
            return False
    
    return True

def setup_wav2lip():
    """Setup Wav2Lip repository and models"""
    print("Setting up Wav2Lip...")
    
    model_dir = Path("_model_cache")
    wav2lip_dir = model_dir / "Wav2Lip"
    
    # Create model directory
    model_dir.mkdir(exist_ok=True)
    
    # Clone Wav2Lip if not exists
    if not wav2lip_dir.exists():
        if not run_command([
            "git", "clone", 
            "https://github.com/Rudrabha/Wav2Lip.git", 
            str(wav2lip_dir)
        ], "Cloning Wav2Lip repository"):
            return False
    
    # Create checkpoints directory
    checkpoints_dir = wav2lip_dir / "checkpoints"
    checkpoints_dir.mkdir(exist_ok=True)
    
    # Download Wav2Lip GAN model
    wav2lip_model = checkpoints_dir / "wav2lip_gan.pth"
    if not wav2lip_model.exists():
        print("Downloading Wav2Lip GAN model...")
        if not run_command([
            "gdown", "1JYb65kQA079KBeHbsb_06h-cdQzfuv5R", 
            "-O", str(wav2lip_model)
        ], "Downloading Wav2Lip model"):
            # Try alternative download method
            print("Trying alternative download method...")
            if not run_command([
                "wget", "-O", str(wav2lip_model),
                "https://github.com/Rudrabha/Wav2Lip/releases/download/v1.0.0/wav2lip_gan.pth"
            ], "Alternative Wav2Lip model download"):
                print("Warning: Could not download Wav2Lip model automatically.")
                print("Please download manually from: https://github.com/Rudrabha/Wav2Lip")
    
    # Download face detection model
    face_detection_dir = wav2lip_dir / "face_detection" / "detection" / "sfd"
    face_detection_dir.mkdir(parents=True, exist_ok=True)
    
    face_model = face_detection_dir / "s3fd.pth"
    if not face_model.exists():
        print("Downloading face detection model...")
        if not run_command([
            "wget", "-O", str(face_model),
            "https://www.adrianbulat.com/downloads/python-fan/s3fd-619a316812.pth"
        ], "Downloading face detection model"):
            print("Warning: Could not download face detection model.")
    
    # Install Wav2Lip requirements
    requirements_file = wav2lip_dir / "requirements.txt"
    if requirements_file.exists():
        run_command([
            sys.executable, "-m", "pip", "install", "-r", str(requirements_file)
        ], "Installing Wav2Lip requirements")
    
    return True

def main():
    """Main installation function"""
    print("=" * 60)
    print("VideoLingo Lip Sync Installation")
    print("=" * 60)
    
    # Check if we're in the right directory
    if not Path("core").exists():
        print("Error: Please run this script from the VideoLingo root directory")
        sys.exit(1)
    
    # Install dependencies
    if not install_dependencies():
        print("Failed to install dependencies")
        sys.exit(1)
    
    # Setup Wav2Lip
    if not setup_wav2lip():
        print("Failed to setup Wav2Lip")
        sys.exit(1)
    
    print("=" * 60)
    print("Lip Sync installation completed successfully!")
    print("You can now enable lip sync in the VideoLingo interface.")
    print("=" * 60)

if __name__ == "__main__":
    main() 