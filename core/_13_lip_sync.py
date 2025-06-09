import os
import subprocess
import shutil
from rich.console import Console
from pathlib import Path

from core._1_ytdlp import find_video_files
from core.utils import *

console = Console()

abs_root_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ------------
# Lip Sync Configuration
# ------------
LIP_SYNC_VIDEO = os.path.join(abs_root_path, "output/output_lip_sync.mp4")
WAV2LIP_DIR = os.path.join(abs_root_path, "_model_cache/Wav2Lip")
WAV2LIP_CHECKPOINT = os.path.join(abs_root_path, "_model_cache/Wav2Lip/checkpoints/wav2lip_gan.pth")
WAV2LIP_VENV_DIR = os.path.join(abs_root_path, "_model_cache/wav2lip_env")
WAV2LIP_RUNNER = os.path.join(abs_root_path, "_model_cache/run_wav2lip.py")

def get_venv_python():
    """Get the Python executable path from the virtual environment"""
    venv_path = Path(WAV2LIP_VENV_DIR)
    
    if os.name == 'nt':  # Windows
        python_exe = venv_path / "Scripts" / "python.exe"
    else:  # Unix/Linux/macOS
        python_exe = venv_path / "bin" / "python"
    
    return str(python_exe) if python_exe.exists() else None

def check_wav2lip_installation():
    """Check if Wav2Lip is properly installed in virtual environment"""
    
    # Check if virtual environment exists
    venv_python = get_venv_python()
    if not venv_python:
        return False
    
    # Check if Wav2Lip directory exists
    if not os.path.exists(WAV2LIP_DIR):
        return False
    
    # Check if checkpoint exists
    if not os.path.exists(WAV2LIP_CHECKPOINT):
        return False
    
    # Check if runner script exists
    if not os.path.exists(WAV2LIP_RUNNER):
        return False
    
    return True

def setup_wav2lip():
    """Setup Wav2Lip repository and models"""
    if check_wav2lip_installation():
        rprint("[bold green]Wav2Lip already installed in virtual environment.[/bold green]")
        return True
    
    rprint("[bold red]Wav2Lip not properly installed.[/bold red]")
    rprint("[bold yellow]Please run: python scripts/install_lip_sync.py[/bold yellow]")
    return False

def get_video_info(video_path):
    """Get video information using ffprobe"""
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json", 
        "-show_format", "-show_streams", video_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        import json
        info = json.loads(result.stdout)
        
        # Find video stream
        for stream in info.get('streams', []):
            if stream.get('codec_type') == 'video':
                duration = float(stream.get('duration', 0))
                width = int(stream.get('width', 0))
                height = int(stream.get('height', 0))
                return duration, width, height
    
    return 0, 0, 0

def split_video_for_lip_sync(video_path, audio_path, chunk_duration=60):
    """Split long video into smaller chunks for processing"""
    duration, width, height = get_video_info(video_path)
    
    if duration <= chunk_duration:
        return [(video_path, audio_path, 0)]
    
    rprint(f"[bold yellow]Video is {duration:.1f}s long, splitting into {chunk_duration}s chunks...[/bold yellow]")
    
    chunks = []
    chunk_count = int(duration / chunk_duration) + 1
    
    for i in range(chunk_count):
        start_time = i * chunk_duration
        
        # Create chunk paths
        video_chunk = f"output/temp_video_chunk_{i}.mp4"
        audio_chunk = f"output/temp_audio_chunk_{i}.wav"
        
        # Extract video chunk
        cmd_video = [
            "ffmpeg", "-y", "-i", video_path,
            "-ss", str(start_time), "-t", str(chunk_duration),
            "-c", "copy", video_chunk
        ]
        subprocess.run(cmd_video, capture_output=True)
        
        # Extract audio chunk
        cmd_audio = [
            "ffmpeg", "-y", "-i", audio_path,
            "-ss", str(start_time), "-t", str(chunk_duration),
            "-ar", "16000", "-ac", "1", audio_chunk
        ]
        subprocess.run(cmd_audio, capture_output=True)
        
        if os.path.exists(video_chunk) and os.path.exists(audio_chunk):
            chunks.append((video_chunk, audio_chunk, start_time))
    
    return chunks

def run_wav2lip_inference(video_path, audio_path, output_path, resize_factor=1, no_smooth=False, pads=None):
    """Run Wav2Lip inference using the virtual environment"""
    
    # Get virtual environment python
    venv_python = get_venv_python()
    if not venv_python:
        rprint("[bold red]Virtual environment not found. Please run install_lip_sync.py first.[/bold red]")
        return False
    
    # Prepare command arguments
    args = [
        "--checkpoint_path", "checkpoints/wav2lip_gan.pth",
        "--face", os.path.abspath(video_path),
        "--audio", os.path.abspath(audio_path),
        "--outfile", os.path.abspath(output_path),
        "--resize_factor", str(int(resize_factor))
    ]
    
    # Add optional parameters
    if no_smooth:
        args.append("--nosmooth")
    
    if pads:
        args.extend(["--pads"] + [str(p) for p in pads])
    
    # Run inference using the wrapper script
    cmd = [venv_python, WAV2LIP_RUNNER] + args
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        rprint(f"[bold red]Wav2Lip inference failed: {result.stderr}[/bold red]")
        rprint(f"[bold red]Command: {' '.join(cmd)}[/bold red]")
        rprint(f"{result.stdout}")
        return False
    
    return True

def apply_lip_sync(resize_factor=None):
    """Apply lip synchronization to the dubbed video"""
    
    if not load_key("enable_lip_sync"):
        rprint("[bold yellow]Lip sync is disabled. Skipping...[/bold yellow]")
        return
    
    rprint("[bold green]Starting lip synchronization...[/bold green]")
    
    # Setup Wav2Lip if needed
    if not setup_wav2lip():
        rprint("[bold red]Failed to setup Wav2Lip. Please run install_lip_sync.py first.[/bold red]")
        return
    
    # Get input files
    video_file = "output/output_dub.mp4"
    audio_file = "output/dub.mp3"
    
    if not os.path.exists(video_file):
        rprint("[bold red]Error: Dubbed video not found. Please complete dubbing first.[/bold red]")
        return
    
    if not os.path.exists(audio_file):
        rprint("[bold red]Error: Dubbed audio not found. Please complete dubbing first.[/bold red]")
        return
    
    # Convert audio to WAV format for better compatibility
    audio_wav = "output/dub_for_lipsync.wav"
    cmd = [
        "ffmpeg", "-y", "-i", audio_file, 
        "-ar", "16000", "-ac", "1", 
        audio_wav
    ]
    subprocess.run(cmd)
    
    # Get video info and determine processing strategy
    duration, width, height = get_video_info(video_file)
    rprint(f"[bold cyan]Video info: {duration:.1f}s, {width}x{height}[/bold cyan]")
    
    # Determine optimal resize factor based on resolution and duration
    if resize_factor is None:
        resize_factor = load_key("lip_sync_resize_factor") or 1
    
    # Auto-adjust resize factor for high resolution or long videos
    if width > 1920 or height > 1080:
        resize_factor = max(resize_factor, 2)
        rprint(f"[bold yellow]High resolution detected, using resize_factor={resize_factor}[/bold yellow]")
    
    if duration > 300:  # 5 minutes
        resize_factor = max(resize_factor, 2)
        rprint(f"[bold yellow]Long video detected, using resize_factor={resize_factor}[/bold yellow]")
    
    # Determine if we need to split the video
    chunk_duration = 120  # 2 minutes per chunk
    if duration > chunk_duration or (width * height * duration / resize_factor**2) > 100000000:
        chunks = split_video_for_lip_sync(video_file, audio_wav, chunk_duration)
        process_in_chunks = True
    else:
        chunks = [(video_file, audio_wav, 0)]
        process_in_chunks = False
    
    # Process each chunk
    chunk_outputs = []
    
    lip_sync_no_smooth = load_key("lip_sync_no_smooth")
    lip_sync_pads = load_key("lip_sync_pads")

    for i, (video_chunk, audio_chunk, start_time) in enumerate(chunks):
        rprint(f"[bold yellow]Processing chunk {i+1}/{len(chunks)}...[/bold yellow]")
        
        if process_in_chunks:
            output_path = f"output/temp_lip_sync_chunk_{i}.mp4"
        else:
            output_path = LIP_SYNC_VIDEO
        
        # Run inference using virtual environment
        success = run_wav2lip_inference(
            video_chunk, 
            audio_chunk, 
            output_path,
            resize_factor=resize_factor,
            no_smooth=lip_sync_no_smooth,
            pads=lip_sync_pads
        )
        
        if not success:
            rprint(f"[bold red]Chunk {i+1} failed[/bold red]")
            return
        
        if process_in_chunks:
            chunk_outputs.append(output_path)
    
    # Merge chunks if needed
    if process_in_chunks and chunk_outputs:
        rprint("[bold yellow]Merging lip sync chunks...[/bold yellow]")
        
        # Create file list for ffmpeg
        filelist_path = "output/temp_chunks_list.txt"
        with open(filelist_path, 'w') as f:
            for chunk_path in chunk_outputs:
                f.write(f"file '{os.path.basename(chunk_path)}'\n")
        
        # Merge chunks
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", filelist_path, "-c", "copy", LIP_SYNC_VIDEO
        ]
        
        os.chdir("output")
        result = subprocess.run(cmd, capture_output=True, text=True)
        os.chdir("..")
        
        if result.returncode != 0:
            rprint(f"[bold red]Failed to merge chunks: {result.stderr}[/bold red]")
            return
        
        # Clean up chunk files
        for chunk_path in chunk_outputs:
            if os.path.exists(chunk_path):
                os.remove(chunk_path)
        
        # Clean up temp files
        for i in range(len(chunks)):
            temp_files = [
                f"output/temp_video_chunk_{i}.mp4",
                f"output/temp_audio_chunk_{i}.wav"
            ]
            for temp_file in temp_files:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
        
        if os.path.exists(filelist_path):
            os.remove(filelist_path)
    
    # Clean up temporary files
    if os.path.exists(audio_wav):
        os.remove(audio_wav)
    
    if os.path.exists(LIP_SYNC_VIDEO):
        rprint(f"[bold green]Lip synchronization complete! Output saved to {LIP_SYNC_VIDEO}[/bold green]")
    else:
        rprint("[bold red]Lip sync failed - output file not created.[/bold red]")

if __name__ == '__main__':
    apply_lip_sync() 