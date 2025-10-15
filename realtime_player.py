import os
import time
import argparse
import subprocess
import shutil
import platform
import threading

try:
    import cv2  # type: ignore
except Exception as exc:  # pragma: no cover - dependency availability varies per user env
    cv2 = None
    CV2_IMPORT_ERROR = exc
else:
    CV2_IMPORT_ERROR = None

try:
    from pydub import AudioSegment  # type: ignore
except Exception as exc:  # pragma: no cover
    AudioSegment = None
    PYDUB_IMPORT_ERROR = exc
else:
    PYDUB_IMPORT_ERROR = None

try:
    import pyaudio  # type: ignore
except Exception as exc:  # pragma: no cover
    pyaudio = None
    PYAUDIO_IMPORT_ERROR = exc
else:
    PYAUDIO_IMPORT_ERROR = None

INTERNAL_PLAYER_AVAILABLE = cv2 is not None


# ------------
# Utilities
# ------------

def get_os_type():
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    elif system == "linux":
        return "linux"
    elif system == "windows":
        return "windows"
    else:
        return "unknown"


def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


def which(cmd):
    return shutil.which(cmd) is not None


def ffprobe_has_video_stream(path):
    if not which("ffprobe"):
        return os.path.exists(path) and os.path.getsize(path) > 1024
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=duration",
        "-of",
        "csv=p=0",
        path,
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        return False
    return len(proc.stdout.strip()) > 0


def validate_video_file(video_path):
    if not os.path.exists(video_path):
        print(f"❌ Video file does not exist: {video_path}")
        return False
    file_size = os.path.getsize(video_path)
    if file_size == 0:
        print(f"❌ Video file is empty: {video_path}")
        return False
    if file_size < 1024:
        print(f"❌ Video file too small ({file_size} bytes): {video_path}")
        return False
    if not ffprobe_has_video_stream(video_path):
        print(f"❌ Video file appears corrupted (no video stream): {video_path}")
        return False
    print(f"📹 Video validated: {video_path} ({file_size} bytes)")
    return True


class FileStabilityTracker:
    """Track file size over time to determine when writing has quiesced."""

    def __init__(self, min_size=1024, stable_duration=0.25):
        self.min_size = min_size
        self.stable_duration = stable_duration
        self._seen = {}

    def _reset(self, path):
        self._seen.pop(path, None)

    def mark_consumed(self, path):
        self._reset(path)

    def is_stable(self, path):
        if not os.path.exists(path):
            self._reset(path)
            return False

        size = os.path.getsize(path)
        if size < self.min_size:
            self._seen[path] = (size, time.time())
            return False

        now = time.time()
        last = self._seen.get(path)
        if last is None or last[0] != size:
            self._seen[path] = (size, now)
            return False

        if now - last[1] >= self.stable_duration:
            self._reset(path)
            return True

        return False


# ------------
# Session and segment discovery
# ------------

def find_latest_session_dir(base_dir):
    if not os.path.exists(base_dir):
        return None
    names = [n for n in os.listdir(base_dir) if n.startswith("session_")]
    if not names:
        return None
    names.sort()
    latest = names[-1]
    return os.path.join(base_dir, latest)


def segment_video_path(session_dir, index):
    seg_dir = os.path.join(session_dir, f"seg_{index:04d}")
    return os.path.join(seg_dir, "output_dub.mp4")


# ------------
# Playback
# ------------

def play_with_ffplay(video_path):
    cmd = ["ffplay", "-autoexit", video_path]
    print(f"▶️  Playing with ffplay: {' '.join(cmd)}")
    proc = subprocess.Popen(cmd)
    proc.wait()
    return proc.returncode == 0


def play_with_mpv(video_path):
    cmd = ["mpv", "--really-quiet", "--no-terminal", video_path]
    print(f"▶️  Playing with mpv: {' '.join(cmd)}")
    proc = subprocess.Popen(cmd)
    proc.wait()
    return proc.returncode == 0


def play_with_vlc(video_path):
    cmd = ["vlc", "--play-and-exit", video_path]
    print(f"▶️  Playing with vlc: {' '.join(cmd)}")
    proc = subprocess.Popen(cmd)
    proc.wait()
    return proc.returncode == 0


def play_with_default(video_path):
    os_type = get_os_type()
    if os_type == "windows":
        # Try PowerShell Start-Process first; fall back to cmd start if it fails (e.g. UWP handlers).
        escaped_path = video_path.replace("'", "''")
        ps_command = (
            "$ErrorActionPreference='Stop';"
            "try {"
            f"    Start-Process -FilePath '{escaped_path}' -Wait;"
            "    exit 0"
            "} catch {"
            "    try { Start-Process -FilePath '{escaped_path}'; exit 0 }"
            "    catch { exit 1 }"
            "}"
        )
        cmd = [
            "powershell",
            "-NoProfile",
            "-Command",
            ps_command,
        ]
        print(f"▶️  Playing with default (Windows): {' '.join(cmd)}")
        proc = subprocess.Popen(cmd)
        proc.wait()
        if proc.returncode == 0:
            return True

        # Fall back to cmd /c start /wait to leverage default associations when Start-Process fails.
        fallback_cmd = ["cmd", "/c", "start", "", "/wait", video_path]
        print(f"▶️  Fallback with cmd.exe: {' '.join(fallback_cmd)}")
        proc = subprocess.Popen(fallback_cmd)
        proc.wait()
        return proc.returncode == 0
    elif os_type == "macos":
        cmd = ["open", "-W", video_path]
        print(f"▶️  Playing with default (macOS): {' '.join(cmd)}")
        proc = subprocess.Popen(cmd)
        proc.wait()
        return proc.returncode == 0
    elif os_type == "linux":
        # xdg-open does not block; use only as last resort
        if which("xdg-open"):
            cmd = ["xdg-open", video_path]
            print(f"▶️  Opening with default (Linux, non-blocking): {' '.join(cmd)}")
            proc = subprocess.Popen(cmd)
            proc.wait()
            return True
        print("No blocking default player available on Linux. Install ffplay/mpv/vlc.")
        return False
    else:
        print("Unknown OS. Install ffplay/mpv/vlc for blocking playback.")
        return False


def play_video(video_path, player):
    if player == "ffplay" and which("ffplay"):
        return play_with_ffplay(video_path)
    if player == "mpv" and which("mpv"):
        return play_with_mpv(video_path)
    if player == "vlc" and which("vlc"):
        return play_with_vlc(video_path)
    if player == "default":
        return play_with_default(video_path)
    # auto fallback chain
    if which("ffplay"):
        return play_with_ffplay(video_path)
    if which("mpv"):
        return play_with_mpv(video_path)
    if which("vlc"):
        return play_with_vlc(video_path)
    return play_with_default(video_path)


# ------------
# Internal continuous player
# ------------

if INTERNAL_PLAYER_AVAILABLE:
    class SegmentPlayer:
        """Simple OpenCV window + optional PyAudio playback for sequential segments."""

        QUIT_KEYS = {ord("q"), ord("Q"), 27}

        def __init__(self, window_name="VideoLingo Player"):
            self.window_name = window_name
            self._window_created = False
            self._should_stop = False
            self._audio_available = False
            self._audio_warnings = set()
            self._last_frame = None
            self.pa = None
            if pyaudio is not None:
                try:
                    self.pa = pyaudio.PyAudio()
                    self._audio_available = True
                except Exception as exc:
                    print(f"⚠️  Audio output unavailable ({exc}); continuing without sound.")
            else:
                if PYAUDIO_IMPORT_ERROR is not None:
                    print(f"⚠️  PyAudio not available ({PYAUDIO_IMPORT_ERROR}); playback will be silent.")
            if AudioSegment is None:
                if PYDUB_IMPORT_ERROR is not None:
                    print(f"⚠️  Audio decoding via pydub unavailable ({PYDUB_IMPORT_ERROR}); playback will be silent.")
                self._audio_available = False

        def close(self):
            if self._window_created:
                try:
                    cv2.destroyWindow(self.window_name)
                except cv2.error:
                    pass
                self._window_created = False
            self._last_frame = None
            if self.pa is not None:
                try:
                    self.pa.terminate()
                except Exception:
                    pass
                self.pa = None

        def should_stop(self):
            return self._should_stop

        def _create_window(self):
            if not self._window_created:
                cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
                cv2.resizeWindow(self.window_name, 960, 540)
                self._window_created = True
                cv2.waitKey(1)

        def _handle_keypress(self, key_code):
            key = key_code & 0xFF
            if key in self.QUIT_KEYS:
                self._should_stop = True

        def _handle_window_events(self, wait_ms):
            if self._should_stop:
                return True
            if not self._window_created:
                time.sleep(wait_ms / 1000.0)
                return self._should_stop
            wait_ms = max(wait_ms, 1)
            key = cv2.waitKey(wait_ms)
            if key != -1:
                self._handle_keypress(key)
            try:
                visible = cv2.getWindowProperty(self.window_name, cv2.WND_PROP_VISIBLE)
            except cv2.error:
                visible = -1
            if visible < 0:
                self._should_stop = True
            return self._should_stop

        def _load_audio(self, video_path):
            if not self._audio_available or AudioSegment is None:
                return None
            try:
                segment = AudioSegment.from_file(video_path)
            except Exception as exc:
                signature = str(exc)
                if signature not in self._audio_warnings:
                    print(f"⚠️  Skipping audio for {os.path.basename(video_path)}: {exc}")
                    self._audio_warnings.add(signature)
                return None
            if segment.channels == 0 or segment.frame_rate == 0:
                return None
            return segment

        def _play_audio_stream(self, audio_segment, stop_event):
            if not self._audio_available or self.pa is None:
                return
            stream = None
            try:
                stream = self.pa.open(
                    format=self.pa.get_format_from_width(audio_segment.sample_width),
                    channels=audio_segment.channels,
                    rate=audio_segment.frame_rate,
                    output=True,
                )
                raw = audio_segment.raw_data
                frame_width = audio_segment.frame_width or (audio_segment.sample_width * max(audio_segment.channels, 1))
                chunk_frames = 1024
                chunk_bytes = max(chunk_frames * frame_width, frame_width)
                for offset in range(0, len(raw), chunk_bytes):
                    if stop_event.is_set() or self._should_stop:
                        break
                    chunk = raw[offset : offset + chunk_bytes]
                    if not chunk:
                        break
                    stream.write(chunk)
            except Exception as exc:
                signature = str(exc)
                if signature not in self._audio_warnings:
                    print(f"⚠️  Audio playback error: {exc}")
                    self._audio_warnings.add(signature)
            finally:
                if stream is not None:
                    try:
                        stream.stop_stream()
                    except Exception:
                        pass
                    try:
                        stream.close()
                    except Exception:
                        pass

        def play_segment(self, video_path):
            if self._should_stop:
                return False
            self._create_window()
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                print(f"❌ Unable to open video segment: {video_path}")
                return False

            fps = cap.get(cv2.CAP_PROP_FPS)
            if fps <= 0:
                fps = 25.0
            frame_delay = 1.0 / fps

            self._last_frame = None
            stop_event = threading.Event()
            audio_thread = None
            audio_segment = self._load_audio(video_path)
            audio_start_time = None
            
            if audio_segment is not None:
                audio_thread = threading.Thread(
                    target=self._play_audio_stream,
                    args=(audio_segment, stop_event),
                    daemon=True,
                )
                audio_thread.start()
                audio_start_time = time.time()

            frames_played = 0
            last_frame = None
            video_start_time = time.time()
            try:
                while True:
                    frame_start_time = time.time()
                    ret, frame = cap.read()
                    if not ret:
                        break
                    
                    cv2.imshow(self.window_name, frame)
                    last_frame = frame
                    frames_played += 1
                    
                    # Calculate precise timing for sync
                    if audio_start_time is not None:
                        # Sync video to audio timing
                        expected_frame_time = audio_start_time + (frames_played * frame_delay)
                        current_time = time.time()
                        sleep_time = expected_frame_time - current_time
                        if sleep_time > 0:
                            time.sleep(sleep_time)
                    else:
                        # Fallback to FPS-based timing
                        wait_ms = max(int(round(1000.0 * frame_delay)), 1)
                        if self._handle_window_events(wait_ms):
                            stop_event.set()
                            break
                        continue
                    
                    if self._handle_window_events(1):
                        stop_event.set()
                        break
            finally:
                cap.release()

            stop_event.set()
            if audio_thread is not None:
                audio_thread.join()

            if self._should_stop:
                return False
            if frames_played == 0:
                print(f"⚠️  Segment contained no frames: {video_path}")
                return False
            if last_frame is not None:
                self._last_frame = last_frame.copy()
                cv2.imshow(self.window_name, self._last_frame)
                self._handle_window_events(1)
            return True

        def process_events(self, wait_seconds):
            deadline = time.time() + max(wait_seconds, 0.0)
            while time.time() < deadline and not self._should_stop:
                remaining = deadline - time.time()
                if not self._window_created:
                    time.sleep(min(remaining, 0.05))
                    continue
                if self._last_frame is not None:
                    cv2.imshow(self.window_name, self._last_frame)
                wait_ms = int(min(remaining, 0.05) * 1000)
                if wait_ms <= 0:
                    wait_ms = 1
                self._handle_window_events(wait_ms)
            return self._should_stop

else:
    SegmentPlayer = None  # type: ignore


# ------------
# Main loop
# ------------

def watch_and_play(shared_base, session_dir, start_index, poll_interval, player):
    if not session_dir:
        print("Detecting latest session directory under base share...")
        while True:
            session_dir = find_latest_session_dir(shared_base)
            if session_dir is not None:
                break
            print("Waiting for session_* directory...")
            time.sleep(1.0)
    else:
        if not os.path.isabs(session_dir):
            session_dir = os.path.abspath(session_dir)
    print(f"Session dir: {session_dir}")

    use_internal = False
    selected_player = player
    segment_player = None

    if player == "internal":
        if not INTERNAL_PLAYER_AVAILABLE or SegmentPlayer is None:
            reason = (
                str(CV2_IMPORT_ERROR)
                if CV2_IMPORT_ERROR is not None
                else "OpenCV windowing unavailable"
            )
            print(f"❌ Internal player unavailable ({reason}). Falling back to external players.")
            selected_player = "auto"
        else:
            use_internal = True
    elif player == "auto":
        if INTERNAL_PLAYER_AVAILABLE and SegmentPlayer is not None:
            use_internal = True
        else:
            selected_player = "auto"
    else:
        selected_player = player

    if use_internal:
        try:
            segment_player = SegmentPlayer()
        except Exception as exc:
            print(f"❌ Failed to initialize internal player: {exc}")
            use_internal = False
            segment_player = None
            selected_player = "auto"

    stable_duration = 0.2 if use_internal else max(0.25, min(poll_interval, 1.0))
    stability_tracker = FileStabilityTracker(stable_duration=stable_duration)

    wait_step = poll_interval
    if use_internal:
        wait_step = min(poll_interval, 0.1)
        if wait_step <= 0:
            wait_step = 0.05
    else:
        wait_step = poll_interval if poll_interval > 0 else 0.2

    index = start_index
    try:
        while True:
            video_path = segment_video_path(session_dir, index)
            played = False

            if stability_tracker.is_stable(video_path):
                if validate_video_file(video_path):
                    if use_internal and segment_player is not None:
                        played = segment_player.play_segment(video_path)
                        if segment_player.should_stop():
                            print("🛑 Playback stopped by user. Exiting.")
                            break
                        if played:
                            stability_tracker.mark_consumed(video_path)
                            print(f"✅ Played segment {index:04d}")
                            index += 1
                            continue
                        else:
                            print("❌ Internal player failed, retrying...")
                    else:
                        ok = play_video(video_path, selected_player)
                        if ok:
                            stability_tracker.mark_consumed(video_path)
                            print(f"✅ Played segment {index:04d}")
                            index += 1
                            continue
                        else:
                            print("❌ Player failed, retry in a moment...")

            if use_internal and segment_player is not None:
                if segment_player.process_events(wait_step):
                    print("🛑 Playback stopped by user. Exiting.")
                    break
            else:
                time.sleep(wait_step)
    finally:
        if segment_player is not None:
            segment_player.close()


# ------------
# CLI
# ------------

def main():
    parser = argparse.ArgumentParser(description="Cross-platform watcher to play new dubbed segments in real time")
    parser.add_argument("--shared-base", type=str, default="output", help="Base shared output directory containing session_* folders")
    parser.add_argument("--session-dir", type=str, default="", help="Specific session directory to watch; if empty, auto-detect latest")
    parser.add_argument("--start-index", type=int, default=0, help="Segment index to start from")
    parser.add_argument("--poll-interval", type=float, default=1.0, help="Polling interval in seconds")
    parser.add_argument(
        "--player",
        type=str,
        default="auto",
        choices=["auto", "internal", "ffplay", "mpv", "vlc", "default"],
        help="Preferred player (internal uses the built-in OpenCV viewer)",
    )

    args = parser.parse_args()

    shared_base = os.path.abspath(args.shared_base)
    if not os.path.exists(shared_base):
        print("Shared base directory does not exist")
        return 1

    watch_and_play(shared_base, args.session_dir, args.start_index, args.poll_interval, args.player)
    return 0


if __name__ == "__main__":
    code = main()
    raise SystemExit(code)
