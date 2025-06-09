import os
import subprocess
import cv2
import numpy as np
from pathlib import Path
import shutil
import tempfile
from rich.console import Console

from core._1_ytdlp import find_video_files
from core.utils import *
from core.lip_sync_utils.wav2lip_setup import setup_wav2lip_environment, verify_wav2lip_installation

console = Console()

# ------------
# Constants
# ------------
LIPSYNC_OUTPUT = "output/output_lipsync.mp4"
TEMP_DIR = "output/temp_lipsync"
MAX_SEGMENT_DURATION = 30  # seconds
FACE_DETECTION_THRESHOLD = 0.5

def apply_lip_sync(resize_factor=1.0):
    """Apply lip synchronization to the dubbed video using Easy-Wav2Lip"""
    
    if not load_key("enable_lip_sync"):
        rprint("[bold yellow]Lip sync is disabled in config. Skipping...[/bold yellow]")
        return
    
    # Check if dubbed video exists
    dub_video = "output/output_dub.mp4"
    if not os.path.exists(dub_video):
        rprint("[bold red]Error: Dubbed video not found. Please run audio processing first.[/bold red]")
        return
    
    # Check if dubbed audio exists
    dub_audio = "output/dub.mp3"
    if not os.path.exists(dub_audio):
        rprint("[bold red]Error: Dubbed audio not found. Please run audio processing first.[/bold red]")
        return
    
    rprint("[bold green]Starting lip synchronization process...[/bold green]")
    
    # Create temporary directory
    os.makedirs(TEMP_DIR, exist_ok=True)
    
    # Get video duration and check if segmentation is needed
    video_duration = get_video_duration(dub_video)
    
    if video_duration > MAX_SEGMENT_DURATION:
        rprint(f"[bold yellow]Video duration ({video_duration:.1f}s) exceeds {MAX_SEGMENT_DURATION}s. Segmenting video...[/bold yellow]")
        segments = segment_video_with_face_check(dub_video, dub_audio)
        
        # Process each segment
        processed_segments = []
        for i, (video_segment, audio_segment) in enumerate(segments):
            rprint(f"[bold blue]Processing segment {i+1}/{len(segments)}...[/bold blue]")
            processed_segment = process_lipsync_segment(video_segment, audio_segment, resize_factor, i)
            if processed_segment:
                processed_segments.append(processed_segment)
        
        # Merge processed segments
        if processed_segments:
            merge_video_segments(processed_segments, LIPSYNC_OUTPUT)
            rprint(f"[bold green]Lip sync completed! Output saved to {LIPSYNC_OUTPUT}[/bold green]")
        else:
            rprint("[bold red]Error: No segments were successfully processed.[/bold red]")
    else:
        # Process entire video if under 30 seconds
        if check_video_has_faces(dub_video):
            processed_video = process_lipsync_segment(dub_video, dub_audio, resize_factor, 0)
            if processed_video:
                shutil.move(processed_video, LIPSYNC_OUTPUT)
                rprint(f"[bold green]Lip sync completed! Output saved to {LIPSYNC_OUTPUT}[/bold green]")
            else:
                rprint("[bold red]Error: Lip sync processing failed.[/bold red]")
        else:
            rprint("[bold red]Error: No faces detected in video. Lip sync requires faces in all frames.[/bold red]")
    
    # Cleanup temporary files
    cleanup_temp_files()

def get_video_duration(video_path):
    """Get video duration in seconds"""
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    cap.release()
    return frame_count / fps if fps > 0 else 0

def check_video_has_faces(video_path):
    """Check if video has faces in all frames using OpenCV face detection"""
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    cap = cv2.VideoCapture(video_path)
    
    frame_count = 0
    faces_detected = 0
    sample_rate = 10  # Check every 10th frame for efficiency
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        if frame_count % sample_rate == 0:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, 1.1, 4)
            if len(faces) > 0:
                faces_detected += 1
        
        frame_count += 1
    
    cap.release()
    
    # Require faces in at least 80% of sampled frames
    sampled_frames = (frame_count // sample_rate) + 1
    face_ratio = faces_detected / sampled_frames if sampled_frames > 0 else 0
    
    rprint(f"[bold blue]Face detection: {faces_detected}/{sampled_frames} frames ({face_ratio:.1%})[/bold blue]")
    return face_ratio >= 0.8

def segment_video_with_face_check(video_path, audio_path):
    """Segment video into chunks with face validation"""
    segments = []
    video_duration = get_video_duration(video_path)
    num_segments = int(np.ceil(video_duration / MAX_SEGMENT_DURATION))
    
    for i in range(num_segments):
        start_time = i * MAX_SEGMENT_DURATION
        end_time = min((i + 1) * MAX_SEGMENT_DURATION, video_duration)
        
        # Create video segment
        video_segment = os.path.join(TEMP_DIR, f"video_segment_{i}.mp4")
        audio_segment = os.path.join(TEMP_DIR, f"audio_segment_{i}.wav")
        
        # Extract video segment
        cmd_video = [
            'ffmpeg', '-y', '-i', video_path,
            '-ss', str(start_time), '-t', str(end_time - start_time),
            '-c:v', 'libx264', '-c:a', 'aac',
            video_segment
        ]
        subprocess.run(cmd_video, capture_output=True)
        
        # Extract audio segment
        cmd_audio = [
            'ffmpeg', '-y', '-i', audio_path,
            '-ss', str(start_time), '-t', str(end_time - start_time),
            '-acodec', 'pcm_s16le', '-ar', '16000',
            audio_segment
        ]
        subprocess.run(cmd_audio, capture_output=True)
        
        # Check if segment has faces
        if check_video_has_faces(video_segment):
            segments.append((video_segment, audio_segment))
            rprint(f"[bold green]Segment {i+1}: Valid (has faces)[/bold green]")
        else:
            rprint(f"[bold yellow]Segment {i+1}: Skipped (no faces detected)[/bold yellow]")
            # Keep original segment for merging
            segments.append((video_segment, None))
    
    return segments

def process_lipsync_segment(video_path, audio_path, resize_factor, segment_id):
    """Process a single video segment with Easy-Wav2Lip"""
    
    if audio_path is None:
        # Return original video if no audio (no faces detected)
        return video_path
    
    output_path = os.path.join(TEMP_DIR, f"lipsync_segment_{segment_id}.mp4")
    
    # Setup Easy-Wav2Lip environment
    wav2lip_dir = setup_wav2lip_environment()
    if not wav2lip_dir:
        rprint("[bold red]Error: Failed to setup Easy-Wav2Lip environment[/bold red]")
        return None
    
    # Run Easy-Wav2Lip inference
    checkpoint_path = os.path.join(wav2lip_dir, "checkpoints", "wav2lip_gan.pth")
    if not os.path.exists(checkpoint_path):
        checkpoint_path = os.path.join(wav2lip_dir, "checkpoints", "wav2lip.pth")
    
    if not os.path.exists(checkpoint_path):
        rprint("[bold red]Error: Wav2Lip checkpoint not found[/bold red]")
        return None
    
    # Prepare inference command
    inference_script = os.path.join(wav2lip_dir, "inference.py")
    cmd = [
        'python', inference_script,
        '--checkpoint_path', checkpoint_path,
        '--face', video_path,
        '--audio', audio_path,
        '--outfile', output_path,
        '--resize_factor', str(resize_factor),
        '--nosmooth'  # Better for segmented videos
    ]
    
    # Add padding for better results
    cmd.extend(['--pads', '0', '10', '0', '0'])
    
    try:
        result = subprocess.run(cmd, cwd=wav2lip_dir, capture_output=True, text=True)
        if result.returncode == 0 and os.path.exists(output_path):
            rprint(f"[bold green]Successfully processed segment {segment_id}[/bold green]")
            return output_path
        else:
            rprint(f"[bold red]Error processing segment {segment_id}: {result.stderr}[/bold red]")
            return video_path  # Return original on failure
    except Exception as e:
        rprint(f"[bold red]Exception during lip sync: {str(e)}[/bold red]")
        return video_path



def merge_video_segments(segment_paths, output_path):
    """Merge processed video segments back together"""
    
    # Create file list for ffmpeg concat
    concat_file = os.path.join(TEMP_DIR, "concat_list.txt")
    with open(concat_file, 'w') as f:
        for segment_path in segment_paths:
            f.write(f"file '{os.path.abspath(segment_path)}'\n")
    
    # Merge segments
    cmd = [
        'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
        '-i', concat_file,
        '-c', 'copy',
        output_path
    ]
    
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode == 0:
        rprint("[bold green]Successfully merged video segments[/bold green]")
    else:
        rprint(f"[bold red]Error merging segments: {result.stderr.decode()}[/bold red]")

def cleanup_temp_files():
    """Clean up temporary files"""
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR)
        rprint("[bold blue]Cleaned up temporary files[/bold blue]")

if __name__ == '__main__':
    apply_lip_sync() 