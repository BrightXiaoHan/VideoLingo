import os, subprocess
import pandas as pd
from typing import Dict, List, Tuple
from pydub import AudioSegment
from core.utils import *
from core.utils.models import *
from pydub import AudioSegment
from pydub.silence import detect_silence
from pydub.utils import mediainfo
from rich import print as rprint

def normalize_audio_volume(audio_path, output_path, target_db = -20.0, format = "wav"):
    audio = AudioSegment.from_file(audio_path)
    change_in_dBFS = target_db - audio.dBFS
    normalized_audio = audio.apply_gain(change_in_dBFS)
    normalized_audio.export(output_path, format=format)
    rprint(f"[green]✅ Audio normalized from {audio.dBFS:.1f}dB to {target_db:.1f}dB[/green]")
    return output_path

def validate_video_file(video_file: str) -> bool:
    """Validate that a video file exists and is readable."""
    if not os.path.exists(video_file):
        rprint(f"[red]❌ Video file not found: {video_file}[/red]")
        return False
        
    file_size = os.path.getsize(video_file)
    if file_size == 0:
        rprint(f"[red]❌ Video file is empty (0 bytes): {video_file}[/red]")
        return False
        
    if file_size < 1024:  # Less than 1KB is likely corrupted
        rprint(f"[red]❌ Video file too small ({file_size} bytes): {video_file}[/red]")
        return False
    
    # Test basic video readability
    test_cmd = ['ffprobe', '-v', 'error', '-show_format', '-show_streams', video_file]
    test_result = subprocess.run(test_cmd, capture_output=True, text=True)
    
    if test_result.returncode != 0:
        rprint(f"[red]❌ Video file appears corrupted:[/red]")
        rprint(f"[red]File: {video_file}[/red]")
        rprint(f"[red]Size: {file_size} bytes[/red]")
        rprint(f"[red]FFprobe error: {test_result.stderr.strip()}[/red]")
        return False
    
    rprint(f"[green]✅ Video file validated: {video_file} ({file_size} bytes)[/green]")
    return True


def convert_video_to_audio(video_file: str):
    os.makedirs(_AUDIO_DIR, exist_ok=True)
    if not os.path.exists(_RAW_AUDIO_FILE):
        rprint(f"[blue]🎬➡️🎵 Converting to high quality audio with FFmpeg ......[/blue]")
        
        # First validate the video file
        if not validate_video_file(video_file):
            raise Exception(f"Video file validation failed: {video_file}")
        
        # Check if video has audio track
        probe_cmd = ['ffprobe', '-v', 'error', '-select_streams', 'a:0', '-count_packets', '-show_entries', 'stream=nb_read_packets', '-of', 'csv=p=0', video_file]
        probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
        
        if probe_result.returncode != 0 or not probe_result.stdout.strip():
            rprint(f"[yellow]⚠️ Warning: Video file has no audio track, creating silent audio track[/yellow]")
            # Create a silent audio track with same duration as video
            duration_cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', video_file]
            duration_result = subprocess.run(duration_cmd, capture_output=True, text=True)
            
            if duration_result.returncode == 0 and duration_result.stdout.strip():
                try:
                    duration = float(duration_result.stdout.strip())
                    if duration <= 0:
                        raise ValueError(f"Invalid duration: {duration}")
                except ValueError as e:
                    rprint(f"[red]❌ Invalid video duration: {duration_result.stdout.strip()}[/red]")
                    raise Exception(f"Could not parse video duration for {video_file}: {e}")
                
                # Generate silent audio
                silent_cmd = [
                    'ffmpeg', '-y', '-f', 'lavfi', '-i', f'anullsrc=channel_layout=mono:sample_rate=16000', 
                    '-t', str(duration), '-c:a', 'libmp3lame', '-b:a', '32k', _RAW_AUDIO_FILE
                ]
                result = subprocess.run(silent_cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    rprint(f"[red]❌ Error creating silent audio: {result.stderr}[/red]")
                    raise subprocess.CalledProcessError(result.returncode, silent_cmd, result.stderr)
                rprint(f"[yellow]🔇 Created silent audio track ({duration:.2f}s) for video without audio[/yellow]")
            else:
                rprint(f"[red]❌ Could not determine video duration:[/red]")
                rprint(f"[red]FFprobe command: {' '.join(duration_cmd)}[/red]")
                rprint(f"[red]Exit code: {duration_result.returncode}[/red]")
                rprint(f"[red]Stderr: {duration_result.stderr}[/red]")
                rprint(f"[red]Stdout: {duration_result.stdout}[/red]")
                raise Exception(f"Could not determine video duration for {video_file}")
        else:
            # Normal audio extraction
            result = subprocess.run([
                'ffmpeg', '-y', '-i', video_file, '-vn',
                '-c:a', 'libmp3lame', '-b:a', '32k',
                '-ar', '16000',
                '-ac', '1', 
                '-metadata', 'encoding=UTF-8', _RAW_AUDIO_FILE
            ], capture_output=True, text=True)
            
            if result.returncode != 0:
                rprint(f"[red]❌ FFmpeg error during audio conversion:[/red]")
                rprint(f"[red]{result.stderr}[/red]")
                rprint(f"[blue]Video file info:[/blue]")
                info_cmd = ['ffprobe', '-v', 'error', '-show_format', '-show_streams', video_file]
                info_result = subprocess.run(info_cmd, capture_output=True, text=True)
                if info_result.returncode == 0:
                    rprint(f"[blue]{info_result.stdout}[/blue]")
                raise subprocess.CalledProcessError(result.returncode, ['ffmpeg', '...'], result.stderr)
            
        rprint(f"[green]🎬➡️🎵 Converted <{video_file}> to <{_RAW_AUDIO_FILE}> with FFmpeg\n[/green]")

def get_audio_duration(audio_file: str) -> float:
    """Get the duration of an audio file using ffmpeg."""
    cmd = ['ffmpeg', '-i', audio_file]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    _, stderr = process.communicate()
    output = stderr.decode('utf-8', errors='ignore')
    
    try:
        duration_str = [line for line in output.split('\n') if 'Duration' in line][0]
        duration_parts = duration_str.split('Duration: ')[1].split(',')[0].split(':')
        duration = float(duration_parts[0])*3600 + float(duration_parts[1])*60 + float(duration_parts[2])
    except Exception as e:
        print(f"[red]❌ Error: Failed to get audio duration: {e}[/red]")
        duration = 0
    return duration

def split_audio(audio_file: str, target_len: float = 30*60, win: float = 60) -> List[Tuple[float, float]]:
    ## 在 [target_len-win, target_len+win] 区间内用 pydub 检测静默，切分音频
    rprint(f"[blue]🎙️ Starting audio segmentation {audio_file} {target_len} {win}[/blue]")
    audio = AudioSegment.from_file(audio_file)
    duration = float(mediainfo(audio_file)["duration"])
    if duration <= target_len + win:
        return [(0, duration)]
    segments, pos = [], 0.0
    safe_margin = 0.5  # 静默点前后安全边界，单位秒

    while pos < duration:
        if duration - pos <= target_len:
            segments.append((pos, duration)); break

        threshold = pos + target_len
        ws, we = int((threshold - win) * 1000), int((threshold + win) * 1000)
        
        # 获取完整的静默区域
        silence_regions = detect_silence(audio[ws:we], min_silence_len=int(safe_margin*1000), silence_thresh=-30)
        silence_regions = [(s/1000 + (threshold - win), e/1000 + (threshold - win)) for s, e in silence_regions]
        # 筛选长度足够（至少1秒）且位置适合的静默区域
        valid_regions = [
            (start, end) for start, end in silence_regions 
            if (end - start) >= (safe_margin * 2) and threshold <= start + safe_margin <= threshold + win
        ]
        
        if valid_regions:
            start, end = valid_regions[0]
            split_at = start + safe_margin  # 在静默区域起始点后0.5秒处切分
        else:
            rprint(f"[yellow]⚠️ No valid silence regions found for {audio_file} at {threshold}s, using threshold[/yellow]")
            split_at = threshold
            
        segments.append((pos, split_at)); pos = split_at

    rprint(f"[green]🎙️ Audio split completed {len(segments)} segments[/green]")
    return segments

def process_transcription(result: Dict) -> pd.DataFrame:
    all_words = []
    for segment in result['segments']:
        # Get speaker_id, if not exists, set to None
        speaker_id = segment.get('speaker_id', None)
        
        for word in segment['words']:
            # Check word length
            if len(word["word"]) > 30:
                rprint(f"[yellow]⚠️ Warning: Detected word longer than 30 characters, skipping: {word['word']}[/yellow]")
                continue
                
            # ! For French, we need to convert guillemets to empty strings
            word["word"] = word["word"].replace('»', '').replace('«', '')
            
            if 'start' not in word and 'end' not in word:
                if all_words:
                    # Assign the end time of the previous word as the start and end time of the current word
                    word_dict = {
                        'text': word["word"],
                        'start': all_words[-1]['end'],
                        'end': all_words[-1]['end'],
                        'speaker_id': speaker_id
                    }
                    all_words.append(word_dict)
                else:
                    # If it's the first word, look next for a timestamp then assign it to the current word
                    next_word = next((w for w in segment['words'] if 'start' in w and 'end' in w), None)
                    if next_word:
                        word_dict = {
                            'text': word["word"],
                            'start': next_word["start"],
                            'end': next_word["end"],
                            'speaker_id': speaker_id
                        }
                        all_words.append(word_dict)
                    else:
                        raise Exception(f"No next word with timestamp found for the current word : {word}")
            else:
                # Normal case, with start and end times
                word_dict = {
                    'text': f'{word["word"]}',
                    'start': word.get('start', all_words[-1]['end'] if all_words else 0),
                    'end': word['end'],
                    'speaker_id': speaker_id
                }
                
                all_words.append(word_dict)
    
    return pd.DataFrame(all_words)

def save_results(df: pd.DataFrame):
    from core.utils.models import get_output_dir
    os.makedirs(f'{get_output_dir()}/log', exist_ok=True)

    # Remove rows where 'text' is empty
    initial_rows = len(df)
    df = df[df['text'].str.len() > 0]
    removed_rows = initial_rows - len(df)
    if removed_rows > 0:
        rprint(f"[blue]ℹ️ Removed {removed_rows} row(s) with empty text.[/blue]")
    
    # Check for and remove words longer than 20 characters
    long_words = df[df['text'].str.len() > 30]
    if not long_words.empty:
        rprint(f"[yellow]⚠️ Warning: Detected {len(long_words)} word(s) longer than 30 characters. These will be removed.[/yellow]")
        df = df[df['text'].str.len() <= 30]
    
    df['text'] = df['text'].apply(lambda x: f'"{x}"')
    df.to_excel(_2_CLEANED_CHUNKS, index=False)
    rprint(f"[green]📊 Excel file saved to {_2_CLEANED_CHUNKS}[/green]")

def save_language(language: str):
    update_key("whisper.detected_language", language)