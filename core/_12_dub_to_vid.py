import platform
import subprocess

import cv2
import numpy as np
from rich.console import Console

from core._1_ytdlp import find_video_files
from core.asr_backend.audio_preprocess import normalize_audio_volume
from core.utils import *
from core.utils.models import *

console = Console()

from core.utils.models import get_output_dir

def _get_dub_paths():
    """Get dynamic dub file paths"""
    base_dir = get_output_dir()
    return {
        'video': f"{base_dir}/output_dub.mp4",
        'video_nosub': f"{base_dir}/output_dub_nosub.mp4",
        'sub': f"{base_dir}/dub.srt", 
        'audio': f"{base_dir}/dub.mp3"
    }

TRANS_FONT_SIZE = 17
TRANS_FONT_NAME = 'Arial'
if platform.system() == 'Linux':
    TRANS_FONT_NAME = 'NotoSansCJK-Regular'
if platform.system() == 'Darwin':
    TRANS_FONT_NAME = 'Arial Unicode MS'

TRANS_FONT_COLOR = '&H00FFFF'
TRANS_OUTLINE_COLOR = '&H000000'
TRANS_OUTLINE_WIDTH = 1 
TRANS_BACK_COLOR = '&H33000000'

def merge_video_audio():
    """Merge video and audio, and reduce video volume"""
    VIDEO_FILE = find_video_files()
    background_file = _BACKGROUND_AUDIO_FILE

    # Normalize dub audio
    dub_paths = _get_dub_paths()
    normalized_dub_audio = f"{get_output_dir()}/normalized_dub.wav"
    normalize_audio_volume(dub_paths['audio'], normalized_dub_audio)
    
    # Merge video and audio with translated subtitles
    video = cv2.VideoCapture(VIDEO_FILE)
    TARGET_WIDTH = int(video.get(cv2.CAP_PROP_FRAME_WIDTH))
    TARGET_HEIGHT = int(video.get(cv2.CAP_PROP_FRAME_HEIGHT))
    video.release()
    rprint(f"[bold green]Video resolution: {TARGET_WIDTH}x{TARGET_HEIGHT}[/bold green]")
    
    base_video_filter = (
        f"[0:v]scale={TARGET_WIDTH}:{TARGET_HEIGHT}:force_original_aspect_ratio=decrease,"
        f"pad={TARGET_WIDTH}:{TARGET_HEIGHT}:(ow-iw)/2:(oh-ih)/2"
    )
    audio_filter = "[1:a][2:a]amix=inputs=2:duration=first:dropout_transition=3[a]"

    def run_merge(filter_complex, output_path):
        cmd = [
            'ffmpeg', '-y', '-i', VIDEO_FILE, '-i', background_file, '-i', normalized_dub_audio,
            '-filter_complex', filter_complex
        ]
        if load_key("ffmpeg_gpu"):
            rprint("[bold green]Using GPU acceleration...[/bold green]")
            cmd.extend(['-map', '[v]', '-map', '[a]', '-c:v', 'h264_nvenc'])
        else:
            cmd.extend(['-map', '[v]', '-map', '[a]'])
        cmd.extend(['-c:a', 'aac', '-b:a', '96k', output_path])
        subprocess.run(cmd)

    if not load_key("burn_subtitles"):
        rprint("[bold yellow]Warning: A 0-second black video will be generated as a placeholder as subtitles are not burned in.[/bold yellow]")

        # Create a black frame
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(dub_paths['video'], fourcc, 1, (1920, 1080))
        out.write(frame)
        out.release()

        rprint("[bold green]Placeholder video has been generated.[/bold green]")
        no_sub_filter = f"{base_video_filter}[v];{audio_filter}"
        run_merge(no_sub_filter, dub_paths['video_nosub'])
        rprint(f"[bold green]Video without subtitles successfully merged into {dub_paths['video_nosub']}[/bold green]")
        return

    subtitle_filter = (
        f"subtitles={dub_paths['sub']}:force_style='FontSize={TRANS_FONT_SIZE},"
        f"FontName={TRANS_FONT_NAME},PrimaryColour={TRANS_FONT_COLOR},"
        f"OutlineColour={TRANS_OUTLINE_COLOR},OutlineWidth={TRANS_OUTLINE_WIDTH},"
        f"BackColour={TRANS_BACK_COLOR},Alignment=2,MarginV=27,BorderStyle=4'"
    )
    sub_filter = f"{base_video_filter},{subtitle_filter}[v];{audio_filter}"
    no_sub_filter = f"{base_video_filter}[v];{audio_filter}"

    run_merge(sub_filter, dub_paths['video'])
    rprint(f"[bold green]Video and audio successfully merged into {dub_paths['video']}[/bold green]")
    run_merge(no_sub_filter, dub_paths['video_nosub'])
    rprint(f"[bold green]Video without subtitles successfully merged into {dub_paths['video_nosub']}[/bold green]")

if __name__ == '__main__':
    merge_video_audio()
