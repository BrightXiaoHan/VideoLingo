#!/usr/bin/env python3
"""
Manual download script for Wav2Lip model
Use this if the automatic download in install_lip_sync.py fails
"""

import os
import sys
import subprocess
import requests
from pathlib import Path

def download_with_requests(url, output_path, description):
    """Download file using requests with progress bar"""
    print(f"Downloading {description}...")
    
    response = requests.get(url, stream=True)
    if response.status_code != 200:
        print(f"Failed to download: HTTP {response.status_code}")
        return False
    
    total_size = int(response.headers.get('content-length', 0))
    downloaded = 0
    
    with open(output_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                if total_size > 0:
                    percent = (downloaded / total_size) * 100
                    print(f"\rProgress: {percent:.1f}% ({downloaded}/{total_size} bytes)", end='')
    
    print(f"\n✅ Downloaded {description} successfully!")
    return True

def download_wav2lip_model():
    """Download Wav2Lip model using multiple methods"""
    
    # Check if we're in the right directory
    if not Path("core").exists():
        print("Error: Please run this script from the VideoLingo root directory")
        return False
    
    # Create directories
    model_dir = Path("_model_cache/Wav2Lip/checkpoints")
    model_dir.mkdir(parents=True, exist_ok=True)
    
    model_path = model_dir / "wav2lip_gan.pth"
    
    if model_path.exists():
        print("✅ Wav2Lip model already exists!")
        return True
    
    print("Attempting to download Wav2Lip model...")
    
    # Method 1: Direct download from working mirror
    urls = [
        "https://github.com/justinjohn0306/Wav2Lip/releases/download/models/wav2lip_gan.pth",
        "https://huggingface.co/spaces/CVPR/Wav2Lip/resolve/main/checkpoints/wav2lip_gan.pth",
        "https://www.dropbox.com/s/hdzik6q8fyh9mqx/wav2lip_gan.pth?dl=1"
    ]
    
    for i, url in enumerate(urls, 1):
        print(f"\n--- Attempt {i}: Trying {url} ---")
        
        # Try with requests
        if download_with_requests(url, model_path, f"Wav2Lip model (method {i})"):
            return True
        
        # Clean up partial download
        if model_path.exists():
            model_path.unlink()
    
    # Method 2: Try with wget
    print("\n--- Trying with wget ---")
    for url in urls:
        cmd = ["wget", "-c", "--timeout=300", "-O", str(model_path), url]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and model_path.exists():
            print("✅ Downloaded with wget successfully!")
            return True
        if model_path.exists():
            model_path.unlink()
    
    # Method 3: Try with curl
    print("\n--- Trying with curl ---")
    for url in urls:
        cmd = ["curl", "-L", "--connect-timeout", "300", "-o", str(model_path), url]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and model_path.exists():
            print("✅ Downloaded with curl successfully!")
            return True
        if model_path.exists():
            model_path.unlink()
    
    print("\n❌ All download methods failed.")
    print("\nManual download instructions:")
    print("1. Go to: https://github.com/Rudrabha/Wav2Lip")
    print("2. Look for model download links in the README")
    print("3. Download wav2lip_gan.pth")
    print(f"4. Save it as: {model_path}")
    print("\nAlternatively, search for 'wav2lip_gan.pth' on:")
    print("- Hugging Face: https://huggingface.co/")
    print("- GitHub releases of Wav2Lip forks")
    
    return False

def main():
    """Main function"""
    print("=" * 60)
    print("Wav2Lip Model Manual Download")
    print("=" * 60)
    
    success = download_wav2lip_model()
    
    if success:
        print("\n" + "=" * 60)
        print("✅ Wav2Lip model download completed!")
        print("You can now use lip sync functionality in VideoLingo.")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("❌ Automatic download failed.")
        print("Please follow the manual download instructions above.")
        print("=" * 60)
        sys.exit(1)

if __name__ == "__main__":
    main() 