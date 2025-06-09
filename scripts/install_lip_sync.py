#!/usr/bin/env python3
"""
Installation script for VideoLingo Lip Sync functionality
This script sets up Wav2Lip in a dedicated virtual environment to avoid dependency conflicts
"""

import os
import subprocess
import sys
import time
from pathlib import Path

def run_command(cmd, description="", cwd=None, retries=3):
    """Run a command and handle errors with retry mechanism"""
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    
    for attempt in range(retries):
        if attempt > 0:
            print(f"Retry attempt {attempt + 1}/{retries}")
            time.sleep(2)  # Wait before retry
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
        
        if result.returncode == 0:
            print(f"Success: {description} completed")
            return True
        
        print(f"Attempt {attempt + 1} failed: {result.stderr}")
        
        # Check if it's a network-related error that might benefit from retry
        if "network" in result.stderr.lower() or "download" in result.stderr.lower() or "incomplete-download" in result.stderr.lower():
            if attempt < retries - 1:
                print("Network error detected, will retry...")
                continue
    
    print(f"Error: {description} failed after {retries} attempts")
    print(f"Final error output: {result.stderr}")
    return False

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
                      "Creating virtual environment", retries=1):
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
                      "Upgrading pip in virtual environment", retries=1):
        return False
    
    # Configure pip for better network handling
    pip_config_cmd = [
        pip_exe, "config", "set", "global.timeout", "300"
    ]
    run_command(pip_config_cmd, "Configuring pip timeout", retries=1)
    
    # Install dependencies with specific strategies for problematic packages
    print("Installing PyTorch (this may take a while)...")
    
    # Install torch and torchvision separately for better control
    torch_packages = ["torch>=1.9.0", "torchvision>=0.10.0"]
    
    for package in torch_packages:
        torch_cmd = [
            pip_exe, "install", 
            "--timeout", "600",
            "--retries", "5",
            package
        ]
        
        if not run_command(torch_cmd, f"Installing {package}", retries=3):
            print(f"Failed to install {package} with pip, trying alternative approach...")
            # Try installing from PyTorch official index
            package_name = package.split(">=")[0]  # Get package name without version
            torch_alt_cmd = [
                pip_exe, "install", 
                "--timeout", "600",
                "--retries", "5",
                "--index-url", "https://download.pytorch.org/whl/cpu",
                package_name
            ]
            if not run_command(torch_alt_cmd, f"Installing {package_name} from official index", retries=2):
                print(f"Warning: {package} installation failed. You may need to install it manually.")
                print(f"Try: pip install {package_name} --index-url https://download.pytorch.org/whl/cpu")
    
    # Install other dependencies
    other_dependencies = [
        "face-alignment>=1.3.5",
        "scipy>=1.7.0",
        "gdown>=4.6.0",
        "opencv-python>=4.5.0",
        "librosa>=0.8.0,<0.11.0",  # Pin librosa version for compatibility
        "numpy>=1.19.0",
        "Pillow>=8.0.0",
        "tqdm>=4.60.0",
        "soundfile>=0.10.0"  # For audio file I/O
    ]
    
    for dep in other_dependencies:
        cmd = [pip_exe, "install", "--timeout", "300", "--retries", "3", dep]
        if not run_command(cmd, f"Installing {dep} in virtual environment", retries=2):
            print(f"Warning: Failed to install {dep}, continuing with other packages...")
    
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
        ], "Cloning Wav2Lip repository", retries=2):
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
        
        # Try multiple download methods
        download_success = False
        
        # Method 1: Using gdown with correct Google Drive URL
        if not download_success:
            gdown_cmd = [
                str(python_exe), "-c", 
                f"import gdown; gdown.download('https://drive.google.com/uc?id=1JYb65kQA079KBeHbsb_06h-cdQzfuv5R', '{wav2lip_model}', quiet=False)"
            ]
            if run_command(gdown_cmd, "Downloading Wav2Lip model using gdown", retries=3):
                download_success = True
        
        # Method 2: Direct gdown with file ID
        if not download_success:
            gdown_id_cmd = [
                str(python_exe), "-c", 
                f"import gdown; gdown.download(id='1JYb65kQA079KBeHbsb_06h-cdQzfuv5R', output='{wav2lip_model}', quiet=False)"
            ]
            if run_command(gdown_id_cmd, "Downloading Wav2Lip model using gdown with ID", retries=2):
                download_success = True
        
        # Method 3: Using wget with working mirror
        if not download_success:
            wget_cmd = [
                "wget", "-c", "--timeout=300", "--tries=3",
                "-O", str(wav2lip_model),
                "https://iiitaphyd-my.sharepoint.com/personal/radrabha_m_research_iiit_ac_in/_layouts/15/download.aspx?share=EdjI7bZlgApMqsVoEUUXpLsBxqXbn5z8VTmoxp55YNDcIA"
            ]
            if run_command(wget_cmd, "Downloading Wav2Lip model using SharePoint link", retries=2):
                download_success = True
        
        # Method 4: Using curl with working mirror
        if not download_success:
            curl_cmd = [
                "curl", "-L", "--connect-timeout", "300", "--max-time", "1800",
                "-o", str(wav2lip_model),
                "https://iiitaphyd-my.sharepoint.com/personal/radrabha_m_research_iiit_ac_in/_layouts/15/download.aspx?share=EdjI7bZlgApMqsVoEUUXpLsBxqXbn5z8VTmoxp55YNDcIA"
            ]
            if run_command(curl_cmd, "Downloading Wav2Lip model using SharePoint with curl", retries=2):
                download_success = True
        
        if not download_success:
            print("Warning: Could not download Wav2Lip model automatically.")
            print("Please download manually from: https://github.com/Rudrabha/Wav2Lip")
            print(f"Save the model as: {wav2lip_model}")
    
    # Download face detection model
    face_detection_dir = wav2lip_dir / "face_detection" / "detection" / "sfd"
    face_detection_dir.mkdir(parents=True, exist_ok=True)
    
    face_model = face_detection_dir / "s3fd.pth"
    if not face_model.exists():
        print("Downloading face detection model...")
        
        # Try multiple methods for face detection model too
        face_download_success = False
        
        # Method 1: wget
        if not face_download_success:
            wget_cmd = [
                "wget", "-c", "--timeout=300", "--tries=3",
                "-O", str(face_model),
                "https://www.adrianbulat.com/downloads/python-fan/s3fd-619a316812.pth"
            ]
            if run_command(wget_cmd, "Downloading face detection model using wget", retries=2):
                face_download_success = True
        
        # Method 2: curl
        if not face_download_success:
            curl_cmd = [
                "curl", "-L", "--connect-timeout", "300", "--max-time", "1800",
                "-o", str(face_model),
                "https://www.adrianbulat.com/downloads/python-fan/s3fd-619a316812.pth"
            ]
            if run_command(curl_cmd, "Downloading face detection model using curl", retries=2):
                face_download_success = True
        
        if not face_download_success:
            print("Warning: Could not download face detection model.")
            print(f"Please download manually and save as: {face_model}")
    
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
    abs_path = os.path.dirname(os.path.abspath(__file__))
    
    # Get virtual environment python path
    venv_path = Path(abs_path, "_model_cache/wav2lip_env")
    if os.name == 'nt':  # Windows
        python_exe = venv_path / "Scripts" / "python.exe"
    else:  # Unix/Linux/macOS
        python_exe = venv_path / "bin" / "python"
    
    if not python_exe.exists():
        print("Error: Virtual environment not found. Please run install_lip_sync.py first.")
        return False
    
    # Change to Wav2Lip directory
    wav2lip_dir = Path(abs_path, "_model_cache/Wav2Lip")
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

def verify_installation():
    """Verify that the installation was successful"""
    print("Verifying installation...")
    
    # Check virtual environment
    venv_path = Path("_model_cache/wav2lip_env")
    if os.name == 'nt':
        python_exe = venv_path / "Scripts" / "python.exe"
    else:
        python_exe = venv_path / "bin" / "python"
    
    if not python_exe.exists():
        print("❌ Virtual environment not found")
        return False
    
    # Check Wav2Lip directory
    wav2lip_dir = Path("_model_cache/Wav2Lip")
    if not wav2lip_dir.exists():
        print("❌ Wav2Lip directory not found")
        return False
    
    # Check model files
    wav2lip_model = Path("_model_cache/Wav2Lip/checkpoints/wav2lip_gan.pth")
    if wav2lip_model.exists():
        print("✅ Wav2Lip model found")
    else:
        print("⚠️  Wav2Lip model not found - you may need to download it manually")
    
    # Check runner script
    runner_script = Path("_model_cache/run_wav2lip.py")
    if runner_script.exists():
        print("✅ Runner script created")
    else:
        print("❌ Runner script not found")
        return False
    
    print("✅ Installation verification completed")
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
        print("Warning: Some dependencies failed to install, but continuing...")
    
    # Setup Wav2Lip
    if not setup_wav2lip():
        print("Failed to setup Wav2Lip")
        sys.exit(1)
    
    # Create activation script
    if not create_activation_script():
        print("Failed to create activation script")
        sys.exit(1)
    
    # Verify installation
    verify_installation()
    
    print("=" * 60)
    print("Lip Sync installation completed!")
    print("Wav2Lip is now installed in a dedicated virtual environment.")
    print("")
    
    # Check if model was downloaded successfully
    wav2lip_model = Path("_model_cache/Wav2Lip/checkpoints/wav2lip_gan.pth")
    if not wav2lip_model.exists():
        print("⚠️  Wav2Lip model was not downloaded automatically.")
        print("Please run the manual download script:")
        print("   python scripts/download_wav2lip_model.py")
        print("")
        print("Or download manually:")
        print("1. Download wav2lip_gan.pth from https://github.com/Rudrabha/Wav2Lip")
        print("2. Save it to: _model_cache/Wav2Lip/checkpoints/wav2lip_gan.pth")
        print("")
    else:
        print("✅ All components installed successfully!")
        print("")
    
    print("You can now enable lip sync in the VideoLingo interface.")
    print("=" * 60)

if __name__ == "__main__":
    main() 