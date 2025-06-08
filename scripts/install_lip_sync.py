#!/usr/bin/env python3
"""
Installation script for VideoLingo Lip Sync functionality
This script sets up Wav2Lip in a dedicated virtual environment to avoid dependency conflicts
"""

import os
import subprocess
import sys
from pathlib import Path

def run_command(cmd, description="", cwd=None):
    """Run a command and handle errors"""
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    
    if result.returncode != 0:
        print(f"Error: {description} failed")
        print(f"Error output: {result.stderr}")
        return False
    
    print(f"Success: {description} completed")
    return True

def create_virtual_environment():
    """Create dedicated virtual environment for Wav2Lip"""
    print("Creating virtual environment for Wav2Lip...")
    
    venv_path = Path("_model_cache/wav2lip_env")
    
    # Remove existing environment if it exists
    if venv_path.exists():
        print("Removing existing virtual environment...")
        import shutil
        shutil.rmtree(venv_path)
    
    # Create new virtual environment
    if not run_command([sys.executable, "-m", "venv", str(venv_path)], 
                      "Creating virtual environment"):
        return False, None
    
    # Get python executable path in virtual environment
    if os.name == 'nt':  # Windows
        python_exe = venv_path / "Scripts" / "python.exe"
        pip_exe = venv_path / "Scripts" / "pip.exe"
    else:  # Unix/Linux/macOS
        python_exe = venv_path / "bin" / "python"
        pip_exe = venv_path / "bin" / "pip"
    
    return True, (str(python_exe), str(pip_exe))

def install_dependencies_in_venv(python_exe, pip_exe):
    """Install required Python packages for lip sync in virtual environment"""
    print("Installing lip sync dependencies in virtual environment...")
    
    # Upgrade pip first
    if not run_command([python_exe, "-m", "pip", "install", "--upgrade", "pip"], 
                      "Upgrading pip in virtual environment"):
        return False
    
    dependencies = [
        "torch>=1.9.0",
        "torchvision>=0.10.0", 
        "face-alignment>=1.3.5",
        "scipy>=1.7.0",
        "gdown>=4.6.0",
        "opencv-python>=4.5.0",
        "librosa>=0.8.0",
        "numpy>=1.19.0",
        "Pillow>=8.0.0",
        "tqdm>=4.60.0"
    ]
    
    for dep in dependencies:
        if not run_command([pip_exe, "install", dep, "--resume-retries", "3"], 
                          f"Installing {dep} in virtual environment"):
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
        
        # Get virtual environment python
        venv_path = Path("_model_cache/wav2lip_env")
        if os.name == 'nt':  # Windows
            python_exe = venv_path / "Scripts" / "python.exe"
        else:  # Unix/Linux/macOS
            python_exe = venv_path / "bin" / "python"
        
        if not run_command([
            str(python_exe), "-c", 
            f"import gdown; gdown.download('1JYb65kQA079KBeHbsb_06h-cdQzfuv5R', '{wav2lip_model}', quiet=False)"
        ], "Downloading Wav2Lip model using gdown"):
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
    
    return True

def create_activation_script():
    """Create script to activate virtual environment and run Wav2Lip"""
    print("Creating activation script...")
    
    script_path = Path("_model_cache/run_wav2lip.py")
    
    script_content = '''#!/usr/bin/env python3
"""
Wrapper script to run Wav2Lip in its dedicated virtual environment
"""

import os
import sys
import subprocess
from pathlib import Path

def run_wav2lip_inference(args):
    """Run Wav2Lip inference in virtual environment"""
    
    # Get virtual environment python path
    venv_path = Path("_model_cache/wav2lip_env")
    if os.name == 'nt':  # Windows
        python_exe = venv_path / "Scripts" / "python.exe"
    else:  # Unix/Linux/macOS
        python_exe = venv_path / "bin" / "python"
    
    if not python_exe.exists():
        print("Error: Virtual environment not found. Please run install_lip_sync.py first.")
        return False
    
    # Change to Wav2Lip directory
    wav2lip_dir = Path("_model_cache/Wav2Lip")
    if not wav2lip_dir.exists():
        print("Error: Wav2Lip not found. Please run install_lip_sync.py first.")
        return False
    
    # Prepare command
    cmd = [str(python_exe), "inference.py"] + args
    
    # Run inference
    result = subprocess.run(cmd, cwd=str(wav2lip_dir))
    return result.returncode == 0

if __name__ == "__main__":
    # Pass all arguments to Wav2Lip inference
    success = run_wav2lip_inference(sys.argv[1:])
    sys.exit(0 if success else 1)
'''
    
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(script_content)
    
    # Make script executable on Unix systems
    if os.name != 'nt':
        os.chmod(script_path, 0o755)
    
    return True

def main():
    """Main installation function"""
    print("=" * 60)
    print("VideoLingo Lip Sync Installation (with Virtual Environment)")
    print("=" * 60)
    
    # Check if we're in the right directory
    if not Path("core").exists():
        print("Error: Please run this script from the VideoLingo root directory")
        sys.exit(1)
    
    # Create virtual environment
    success, executables = create_virtual_environment()
    if not success:
        print("Failed to create virtual environment")
        sys.exit(1)
    
    python_exe, pip_exe = executables
    
    # Install dependencies in virtual environment
    if not install_dependencies_in_venv(python_exe, pip_exe):
        print("Failed to install dependencies in virtual environment")
        sys.exit(1)
    
    # Setup Wav2Lip
    if not setup_wav2lip():
        print("Failed to setup Wav2Lip")
        sys.exit(1)
    
    # Create activation script
    if not create_activation_script():
        print("Failed to create activation script")
        sys.exit(1)
    
    print("=" * 60)
    print("Lip Sync installation completed successfully!")
    print("Wav2Lip is now installed in a dedicated virtual environment.")
    print("You can now enable lip sync in the VideoLingo interface.")
    print("=" * 60)

if __name__ == "__main__":
    main() 