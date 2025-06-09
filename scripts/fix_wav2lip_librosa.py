#!/usr/bin/env python3
"""
Fix script for Wav2Lip librosa compatibility issues
This script fixes the audio.py file and installs missing dependencies
"""

import os
import sys
import subprocess
from pathlib import Path

def get_venv_python():
    """Get the Python executable path from the virtual environment"""
    venv_path = Path("_model_cache/wav2lip_env")
    
    if os.name == 'nt':  # Windows
        python_exe = venv_path / "Scripts" / "python.exe"
        pip_exe = venv_path / "Scripts" / "pip.exe"
    else:  # Unix/Linux/macOS
        python_exe = venv_path / "bin" / "python"
        pip_exe = venv_path / "bin" / "pip"
    
    if python_exe.exists():
        return str(python_exe), str(pip_exe)
    return None, None

def install_missing_packages():
    """Install missing packages in the virtual environment"""
    python_exe, pip_exe = get_venv_python()
    
    if not python_exe:
        print("❌ Virtual environment not found. Please run install_lip_sync.py first.")
        return False
    
    print("Installing missing packages...")
    
    packages = [
        "soundfile>=0.10.0",
        "librosa>=0.8.0,<0.11.0"  # Reinstall with version constraint
    ]
    
    for package in packages:
        print(f"Installing {package}...")
        cmd = [pip_exe, "install", "--upgrade", package]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ {package} installed successfully")
        else:
            print(f"⚠️  Warning: Failed to install {package}")
            print(f"Error: {result.stderr}")
    
    return True

def fix_audio_py():
    """Fix the audio.py file for librosa compatibility"""
    audio_file = Path("_model_cache/Wav2Lip/audio.py")
    
    if not audio_file.exists():
        print("❌ Wav2Lip audio.py not found. Please run install_lip_sync.py first.")
        return False
    
    print("Fixing audio.py for librosa compatibility...")
    
    # Read the file
    with open(audio_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Fix the mel filter function call
    old_mel_call = "return librosa.filters.mel(hp.sample_rate, hp.n_fft, n_mels=hp.num_mels,"
    new_mel_call = "return librosa.filters.mel(sr=hp.sample_rate, n_fft=hp.n_fft, n_mels=hp.num_mels,"
    
    if old_mel_call in content:
        content = content.replace(old_mel_call, new_mel_call)
        print("✅ Fixed librosa.filters.mel() call")
    else:
        print("ℹ️  librosa.filters.mel() call already fixed or not found")
    
    # Fix the deprecated write_wav function
    old_write_wav = "def save_wavenet_wav(wav, path, sr):\n    librosa.output.write_wav(path, wav, sr=sr)"
    new_write_wav = """def save_wavenet_wav(wav, path, sr):
    # librosa.output.write_wav is deprecated, use soundfile instead
    try:
        import soundfile as sf
        sf.write(path, wav, sr)
    except ImportError:
        # Fallback to scipy if soundfile is not available
        from scipy.io import wavfile
        wav_int = (wav * 32767).astype(np.int16)
        wavfile.write(path, sr, wav_int)"""
    
    if "librosa.output.write_wav" in content:
        content = content.replace(old_write_wav, new_write_wav)
        print("✅ Fixed deprecated librosa.output.write_wav() call")
    else:
        print("ℹ️  librosa.output.write_wav() call already fixed or not found")
    
    # Write the fixed content back
    with open(audio_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ audio.py file updated successfully")
    return True

def main():
    """Main function"""
    print("=" * 60)
    print("Wav2Lip Librosa Compatibility Fix")
    print("=" * 60)
    
    # Check if we're in the right directory
    if not Path("core").exists():
        print("Error: Please run this script from the VideoLingo root directory")
        sys.exit(1)
    
    # Install missing packages
    if not install_missing_packages():
        print("Failed to install missing packages")
        sys.exit(1)
    
    # Fix audio.py file
    if not fix_audio_py():
        print("Failed to fix audio.py file")
        sys.exit(1)
    
    print("=" * 60)
    print("✅ Wav2Lip librosa compatibility fix completed!")
    print("You can now try running lip sync again.")
    print("=" * 60)

if __name__ == "__main__":
    main() 