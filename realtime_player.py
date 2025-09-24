import os
import time
import argparse
import subprocess
import shutil
import platform


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


def is_file_stable(path, checks=3, interval=1.0, min_size=1024):
    if not os.path.exists(path):
        return False
    for _ in range(10):
        if os.path.getsize(path) > min_size:
            break
        time.sleep(0.5)
    last = os.path.getsize(path)
    for _ in range(checks):
        time.sleep(interval)
        now = os.path.getsize(path)
        if now != last:
            last = now
            continue
    return True


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
        # Try powershell Start-Process first; fall back to cmd start if it fails (e.g. UWP handlers).
        escaped_path = video_path.replace("'", "''")
        ps_command = (
            "$ErrorActionPreference='Stop';"
            f"$proc = Start-Process -LiteralPath '{escaped_path}' -PassThru;"
            "if ($proc) { $proc.WaitForExit() }"
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
        escaped_for_cmd = video_path.replace('"', '\\"')
        quoted_path = f'"{escaped_for_cmd}"'
        fallback_cmd = ["cmd", "/c", "start", "", "/wait", quoted_path]
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

    index = start_index
    while True:
        video_path = segment_video_path(session_dir, index)
        if os.path.exists(video_path):
            if is_file_stable(video_path) and validate_video_file(video_path):
                ok = play_video(video_path, player)
                if ok:
                    print(f"✅ Played segment {index:04d}")
                    index += 1
                    continue
                else:
                    print("❌ Player failed, retry in a moment...")
        time.sleep(poll_interval)


# ------------
# CLI
# ------------

def main():
    parser = argparse.ArgumentParser(description="Cross-platform watcher to play new dubbed segments in real time")
    parser.add_argument("--shared-base", type=str, default="output", help="Base shared output directory containing session_* folders")
    parser.add_argument("--session-dir", type=str, default="", help="Specific session directory to watch; if empty, auto-detect latest")
    parser.add_argument("--start-index", type=int, default=0, help="Segment index to start from")
    parser.add_argument("--poll-interval", type=float, default=1.0, help="Polling interval in seconds")
    parser.add_argument("--player", type=str, default="auto", choices=["auto", "ffplay", "mpv", "vlc", "default"], help="Preferred player")

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
