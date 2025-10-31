import argparse
import os
import sys
import subprocess
import time
import datetime
import platform
import shutil


# ------------
# Utilities
# ------------

def timestamp_now():
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


def sanitize_identifier(name):
    cleaned = []
    for ch in name:
        if ch.isalnum():
            cleaned.append(ch.lower())
        elif ch in ("-", "_"):
            cleaned.append(ch)
        else:
            cleaned.append("-")
    result = "".join(cleaned).strip("-_")
    if not result:
        result = "config"
    return result


def prepare_config_infos(config_paths, base_output):
    if not config_paths:
        config_paths = ["config.yaml"]
    timestamp = timestamp_now()
    multiple = len(config_paths) > 1
    used_names = set()
    infos = []
    for idx, config_path in enumerate(config_paths):
        base_name = os.path.splitext(os.path.basename(config_path))[0]
        if not base_name:
            base_name = f"config{idx + 1}"
        identifier_base = sanitize_identifier(base_name)
        identifier = identifier_base
        suffix = 2
        while identifier in used_names:
            identifier = f"{identifier_base}_{suffix}"
            suffix += 1
        used_names.add(identifier)
        if multiple:
            session_name = f"session_{timestamp}_{identifier}"
        else:
            session_name = f"session_{timestamp}"
        session_dir = os.path.join(base_output, session_name)
        ensure_dir(session_dir)
        infos.append(
            {
                "config_path": config_path,
                "identifier": identifier,
                "session_dir": session_dir,
                "timestamp": timestamp,
                "jobs": [],
                "finished_map": {},
                "playback_state": {"current": None, "next_index": 0},
            }
        )
    return infos


def print_session_overview(config_infos):
    if len(config_infos) == 1:
        print(f"Session dir: {config_infos[0]['session_dir']}")
    else:
        print("Session dirs:")
        for info in config_infos:
            print(f"  [{info['identifier']}] {info['session_dir']}")


def replicate_segment_source(src_path, dest_path):
    if os.path.exists(dest_path):
        os.remove(dest_path)
    try:
        os.link(src_path, dest_path)
    except Exception:
        shutil.copy2(src_path, dest_path)


def run_cmd(cmd, cwd=None, env=None, out_path=None, err_path=None):
    print(f"Run: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    print(result.stdout)
    if len(result.stderr) > 0:
        print(result.stderr)
    if out_path is not None:
        ensure_dir(os.path.dirname(out_path))
        with open(out_path, "a", encoding="utf-8") as f:
            f.write(result.stdout)
    if err_path is not None:
        ensure_dir(os.path.dirname(err_path))
        with open(err_path, "a", encoding="utf-8") as f:
            f.write(result.stderr)
    return result.returncode, result.stdout, result.stderr


def ffprobe_duration_seconds(source_path, out_path=None, err_path=None):
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        source_path,
    ]
    code, out, _ = run_cmd(cmd, out_path=out_path, err_path=err_path)
    if code == 0 and len(out.strip()) > 0:
        try:
            return float(out.strip())
        except Exception:
            return 0.0
    return 0.0


def parse_silencedetect_times(stderr_text):
    lines = stderr_text.splitlines()
    times = []
    for line in lines:
        if "silence_start:" in line:
            parts = line.strip().split("silence_start:")
            if len(parts) > 1:
                val = parts[1].strip().split()[0]
                try:
                    times.append(float(val))
                except Exception:
                    pass
        if "silence_end:" in line:
            parts = line.strip().split("silence_end:")
            if len(parts) > 1:
                val = parts[1].strip().split()[0]
                try:
                    times.append(float(val))
                except Exception:
                    pass
    return times


def find_nearest_silence_time(source_path, target_time_sec, window_sec, silence_db, silence_min_dur, err_log_path=None):
    duration = ffprobe_duration_seconds(source_path)
    if duration <= 0:
        return target_time_sec

    start = max(0.0, target_time_sec - window_sec)
    end = min(duration, target_time_sec + window_sec)
    search_dur = max(0.0, end - start)
    if search_dur <= 0.0:
        return target_time_sec

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-nostats",
        "-ss",
        str(start),
        "-t",
        str(search_dur),
        "-i",
        source_path,
        "-af",
        f"silencedetect=n={silence_db}dB:d={silence_min_dur}",
        "-vn",
        "-f",
        "null",
        "-",
    ]
    code, _, err = run_cmd(cmd, err_path=err_log_path)
    if code != 0:
        return target_time_sec

    rel_times = parse_silencedetect_times(err)
    if len(rel_times) == 0:
        return target_time_sec

    abs_times = [start + t for t in rel_times]
    best = target_time_sec
    best_dist = 1e18
    for t in abs_times:
        dist = abs(t - target_time_sec)
        if dist < best_dist:
            best_dist = dist
            best = t
    return best


def extract_segment(source_path, start_sec, end_sec, out_path, log_dir=None):
    ensure_dir(os.path.dirname(out_path))
    if os.path.exists(out_path):
        os.remove(out_path)
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        str(start_sec),
        "-to",
        str(end_sec),
        "-i",
        source_path,
        "-c",
        "copy",
        out_path,
    ]
    out_log = os.path.join(log_dir, "extract.out") if log_dir else None
    err_log = os.path.join(log_dir, "extract.err") if log_dir else None
    code, _, _ = run_cmd(cmd, out_path=out_log, err_path=err_log)
    
    # Basic file existence and size check
    if code != 0 or not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
        print(f"❌ Segment extraction failed: {out_path}")
        return False
    
    # Validate the extracted segment
    if not validate_video_file(out_path):
        print(f"❌ Extracted segment is corrupted: {out_path}")
        return False
        
    print(f"✅ Segment extracted and validated: {out_path}")
    return True


def start_segment_pipeline_async(segment_dir, config_path):
    print(f"Start pipeline (async) for {segment_dir}")
    cmd = [sys.executable, "main.py", "--config", config_path, "--output", segment_dir, "all"]
    log_out = open(os.path.join(segment_dir, "run_all.out"), "w", encoding="utf-8")
    log_err = open(os.path.join(segment_dir, "run_all.err"), "w", encoding="utf-8")
    proc = subprocess.Popen(cmd, stdout=log_out, stderr=log_err, text=True)
    return {"proc": proc, "dir": segment_dir, "out": log_out, "err": log_err, "done": False}


def poll_jobs_and_collect(jobs, finished_map, prefix=None):
    label = f"[{prefix}] " if prefix else ""
    for job in jobs:
        if job["done"]:
            continue
        ret = job["proc"].poll()
        if ret is None:
            continue
        job["done"] = True
        if job["out"] is not None:
            job["out"].close()
        if job["err"] is not None:
            job["err"].close()
        seg_dir = job["dir"]
        out_video = os.path.join(seg_dir, "output_dub.mp4")
        index = int(os.path.basename(seg_dir).split("_")[-1])
        if os.path.exists(out_video) and os.path.getsize(out_video) > 0 and ret == 0:
            finished_map[index] = out_video
            print(f"{label}Done: {out_video}")
        else:
            print(f"{label}Pipeline failed for segment {index}")


def try_close(fh):
    if fh is None:
        return
    try:
        fh.close()
    except Exception:
        pass


def concat_segments(final_output, list_of_videos, log_dir=None):
    if len(list_of_videos) == 0:
        print("No dubbed videos to merge")
        return False

    list_file = final_output + ".txt"
    lines = []
    for v in list_of_videos:
        abs_v = os.path.abspath(v)
        lines.append(f"file '{abs_v}'\n")
    with open(list_file, "w", encoding="utf-8") as f:
        f.writelines(lines)

    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        list_file,
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        final_output,
    ]
    out_log = os.path.join(log_dir, "final_concat.out") if log_dir else None
    err_log = os.path.join(log_dir, "final_concat.err") if log_dir else None
    code, _, _ = run_cmd(cmd, out_path=out_log, err_path=err_log)
    if code == 0 and os.path.exists(final_output) and os.path.getsize(final_output) > 0:
        print(f"Final merged video: {final_output}")
        return True
    print("Failed to merge final video")
    return False


def start_playback(video_path):
    if not os.path.exists(video_path):
        return None
    return subprocess.Popen(["ffplay", "-autoexit", video_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def handle_sequential_playback(finished_map, playback_state, prefix=None):
    # playback_state: {"current": Popen or None, "next_index": int}
    label = f"[{prefix}] " if prefix else ""
    current = playback_state.get("current")
    if current is not None:
        if current.poll() is None:
            return
        playback_state["current"] = None
    next_idx = playback_state.get("next_index", 0)
    if next_idx in finished_map and playback_state.get("current") is None:
        video_path = finished_map[next_idx]
        print(f"▶️  {label}Playing {video_path}")
        proc = start_playback(video_path)
        playback_state["current"] = proc
        playback_state["next_index"] = next_idx + 1


# ------------
# Cross-platform camera support
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


def list_camera_devices():
    os_type = get_os_type()
    if os_type == "linux":
        # List V4L2 devices and get their names
        devices = []
        for i in range(10):
            device_path = f"/dev/video{i}"
            if os.path.exists(device_path):
                # Try to get device name from v4l2-ctl if available
                device_info = f"video{i} ({device_path})"
                try:
                    result = subprocess.run(
                        ["v4l2-ctl", "--device", device_path, "--info"],
                        capture_output=True, text=True, timeout=2
                    )
                    if result.returncode == 0:
                        for line in result.stdout.split('\n'):
                            if 'Card type' in line:
                                card_type = line.split(':', 1)[1].strip()
                                device_info = f"video{i} - {card_type} ({device_path})"
                                break
                except Exception:
                    pass
                devices.append(device_info)
        return devices
    elif os_type == "macos":
        # For macOS, we could list avfoundation devices, but keep simple for now
        return ["0:0 - Video:Audio device 0", "1:0 - Video device 1", "0:1 - Audio device 1"]
    elif os_type == "windows":
        # For Windows, we could list dshow devices, but keep simple for now
        return ["USB2.0 Camera - Example camera name"]
    else:
        return []


def test_audio_device(audio_device):
    # Test if audio device is available by trying a short capture
    test_cmd = [
        "ffmpeg", "-y", "-f", "alsa", "-i", audio_device, "-t", "0.1", 
        "-f", "null", "-"
    ]
    result = subprocess.run(test_cmd, capture_output=True, text=True)
    return result.returncode == 0


def build_camera_capture_cmd(camera_spec, segment_pattern, segment_seconds, session_dir, audio_device="default"):
    os_type = get_os_type()
    
    if os_type == "linux":
        # Use V4L2 for Linux with ALSA for audio
        if ":" in camera_spec:
            # Convert macOS-style spec to Linux device
            video_idx = camera_spec.split(":")[0]
            video_device = f"/dev/video{video_idx}"
        else:
            # Assume it's already a Linux device path or index
            if camera_spec.startswith("/dev/"):
                video_device = camera_spec
            else:
                video_device = f"/dev/video{camera_spec}"
        
        # Test if audio device works, fallback to video-only if not
        has_audio = test_audio_device(audio_device)
        if has_audio:
            print(f"Using audio device: {audio_device}")
            cmd = [
                "ffmpeg",
                "-y",
                "-f", "v4l2",
                "-i", video_device,
                "-f", "alsa",
                "-i", audio_device,
                "-c:v", "libx264",
                "-c:a", "aac",
                "-f", "segment",
                "-segment_time", str(segment_seconds),
                "-reset_timestamps", "1",
                segment_pattern,
            ]
        else:
            print(f"Warning: Audio device {audio_device} not available, using video-only capture")
            cmd = [
                "ffmpeg",
                "-y",
                "-f", "v4l2",
                "-i", video_device,
                "-c:v", "libx264",
                "-f", "segment",
                "-segment_time", str(segment_seconds),
                "-reset_timestamps", "1",
                segment_pattern,
            ]
    elif os_type == "macos":
        # Use avfoundation for macOS with proper framerate
        cmd = [
            "ffmpeg",
            "-y",
            "-f", "avfoundation",
            "-framerate", "30",  # Set explicit framerate
            "-video_size", "1280x720",  # Set reasonable resolution
            "-i", camera_spec,
            "-c:v", "libx264",
            "-c:a", "aac",
            "-f", "segment",
            "-segment_time", str(segment_seconds),
            "-reset_timestamps", "1",
            segment_pattern,
        ]
    elif os_type == "windows":
        # Use dshow for Windows
        cmd = [
            "ffmpeg",
            "-y",
            "-f", "dshow",
            "-i", f"video={camera_spec}",
            "-c:v", "libx264",
            "-f", "segment",
            "-segment_time", str(segment_seconds),
            "-reset_timestamps", "1",
            segment_pattern,
        ]
    else:
        raise Exception(f"Unsupported operating system: {os_type}")
    
    return cmd


# ------------
# File source pipeline
# ------------

def process_file_source(
    source_path,
    base_output,
    config_paths,
    segment_seconds,
    silence_window,
    silence_db,
    silence_min_dur,
    play_after_each,
    max_concurrency,
):
    config_infos = prepare_config_infos(config_paths, base_output)
    print_session_overview(config_infos)
    use_labels = len(config_infos) > 1

    primary_info = config_infos[0]
    total = ffprobe_duration_seconds(
        source_path,
        out_path=os.path.join(primary_info["session_dir"], "ffprobe_duration.out"),
        err_path=os.path.join(primary_info["session_dir"], "ffprobe_duration.err"),
    )
    print(f"Source duration: {total:.2f}s")
    if total <= 0.0:
        print("Invalid source duration")
        return 1

    # Generate diagnostic logs for additional configs
    for extra in config_infos[1:]:
        ffprobe_duration_seconds(
            source_path,
            out_path=os.path.join(extra["session_dir"], "ffprobe_duration.out"),
            err_path=os.path.join(extra["session_dir"], "ffprobe_duration.err"),
        )

    def poll_all():
        for info in config_infos:
            prefix = info["identifier"] if use_labels else None
            poll_jobs_and_collect(info["jobs"], info["finished_map"], prefix=prefix)
            if play_after_each:
                handle_sequential_playback(info["finished_map"], info["playback_state"], prefix=prefix)

    def wait_for_capacity(target_info):
        while sum(1 for j in target_info["jobs"] if not j["done"]) >= max_concurrency:
            poll_all()
            time.sleep(0.5)

    current_start = 0.0
    seg_index = 0

    while current_start < total:
        seg_dirs = {}
        for info in config_infos:
            seg_dir = os.path.join(info["session_dir"], f"seg_{seg_index:04d}")
            ensure_dir(seg_dir)
            seg_dirs[info["identifier"]] = seg_dir

        proposed_end = min(total, current_start + segment_seconds)
        adjusted_end = proposed_end
        if silence_window > 0.0 and proposed_end < total:
            adjusted_end = find_nearest_silence_time(
                source_path,
                proposed_end,
                silence_window,
                silence_db,
                silence_min_dur,
                err_log_path=os.path.join(seg_dirs[primary_info["identifier"]], "silence.err"),
            )
            if adjusted_end <= current_start + 1.0:
                adjusted_end = proposed_end

        seg_src_primary = os.path.join(seg_dirs[primary_info["identifier"]], "source.mp4")
        ok = extract_segment(
            source_path,
            current_start,
            adjusted_end,
            seg_src_primary,
            log_dir=seg_dirs[primary_info["identifier"]],
        )
        if not ok:
            print(f"Failed to extract segment {seg_index}")
            return 2

        for info in config_infos[1:]:
            dest = os.path.join(seg_dirs[info["identifier"]], "source.mp4")
            replicate_segment_source(seg_src_primary, dest)

        for info in config_infos:
            wait_for_capacity(info)
            seg_dir = seg_dirs[info["identifier"]]
            job = start_segment_pipeline_async(seg_dir, info["config_path"])
            info["jobs"].append(job)

        poll_all()

        seg_index += 1
        current_start = adjusted_end
        if current_start >= total:
            break

    while any(not job["done"] for info in config_infos for job in info["jobs"]):
        poll_all()
        time.sleep(0.5)

    if play_after_each:
        for info in config_infos:
            prefix = info["identifier"] if use_labels else None
            while info["playback_state"].get("next_index", 0) < seg_index:
                handle_sequential_playback(info["finished_map"], info["playback_state"], prefix=prefix)
                time.sleep(0.5)
            current = info["playback_state"].get("current")
            if current is not None and current.poll() is None:
                current.wait()

    for info in config_infos:
        indices = sorted(info["finished_map"].keys())
        dubbed_videos = [info["finished_map"][i] for i in indices]
        final_out = os.path.join(info["session_dir"], "final_dub.mp4")
        concat_segments(final_out, dubbed_videos, log_dir=info["session_dir"])

    return 0


# ------------
# Camera source pipeline (macOS avfoundation)
# ------------

def list_dir_sorted_by_index(dir_path, prefix):
    files = []
    for name in os.listdir(dir_path):
        if name.startswith(prefix) and name.endswith(".mp4"):
            files.append(name)
    files.sort()
    return [os.path.join(dir_path, n) for n in files]


def is_file_stable(path, checks=5, interval=1.0):
    """Check if file is stable and properly written by FFmpeg."""
    if not os.path.exists(path):
        return False
    
    # Wait for file to have reasonable size
    for _ in range(10):  # Wait up to 10 seconds
        if os.path.getsize(path) > 1024:  # At least 1KB
            break
        time.sleep(1)
    else:
        return False
    
    # Check size stability  
    last = os.path.getsize(path)
    for _ in range(checks):
        time.sleep(interval)
        now = os.path.getsize(path)
        if now != last:
            last = now
            continue
    
    # Additional check: verify MP4 structure is complete
    test_cmd = ["ffprobe", "-v", "error", "-show_format", path]
    test_result = subprocess.run(test_cmd, capture_output=True, text=True, timeout=5)
    
    return test_result.returncode == 0


def validate_video_file(video_path):
    """Validate that a video file is not corrupted and can be processed."""
    if not os.path.exists(video_path):
        print(f"❌ Video file does not exist: {video_path}")
        return False
        
    file_size = os.path.getsize(video_path)
    if file_size == 0:
        print(f"❌ Video file is empty: {video_path}")
        return False
        
    if file_size < 1024:  # Less than 1KB is likely corrupted
        print(f"❌ Video file too small ({file_size} bytes): {video_path}")
        return False
    
    # Test with ffprobe to see if file is readable
    test_cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=duration", "-of", "csv=p=0", video_path]
    test_result = subprocess.run(test_cmd, capture_output=True, text=True)
    
    if test_result.returncode != 0:
        print(f"❌ Video file appears corrupted (ffprobe failed): {video_path}")
        print(f"   FFprobe error: {test_result.stderr.strip()}")
        return False
    
    if not test_result.stdout.strip():
        print(f"❌ Video file has no video streams: {video_path}")
        return False
        
    # Get basic video info for logging
    info_cmd = ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", video_path]
    info_result = subprocess.run(info_cmd, capture_output=True, text=True)
    
    if info_result.returncode == 0:
        try:
            import json
            info = json.loads(info_result.stdout)
            duration = float(info.get("format", {}).get("duration", 0))
            if duration <= 0:
                print(f"⚠️  Video file has zero duration: {video_path}")
                return False
            print(f"📹 Video validated: {video_path} ({file_size} bytes, {duration:.2f}s)")
        except Exception:
            # JSON parsing failed, but ffprobe worked, so file is probably OK
            print(f"📹 Video validated: {video_path} ({file_size} bytes)")
    
    return True


def process_camera_source(
    camera_spec,
    base_output,
    config_paths,
    segment_seconds,
    play_after_each,
    max_segments,
    max_concurrency,
    audio_device="default",
):
    config_infos = prepare_config_infos(config_paths, base_output)
    print_session_overview(config_infos)
    use_labels = len(config_infos) > 1

    primary_info = config_infos[0]
    seg_pattern = os.path.join(primary_info["session_dir"], "live_%04d.mp4")
    cmd = build_camera_capture_cmd(camera_spec, seg_pattern, segment_seconds, primary_info["session_dir"], audio_device)
    print("Starting live capture...")
    print(f"Capture command: {' '.join(cmd)}")
    capture_out = open(os.path.join(primary_info["session_dir"], "capture.out"), "w", encoding="utf-8")
    capture_err = open(os.path.join(primary_info["session_dir"], "capture.err"), "w", encoding="utf-8")
    proc = subprocess.Popen(cmd, stdout=capture_out, stderr=capture_err, text=True)

    time.sleep(2)
    if proc.poll() is not None:
        capture_out.close()
        capture_err.close()
        with open(os.path.join(primary_info["session_dir"], "capture.err"), "r", encoding="utf-8") as fh:
            err_content = fh.read()
        print("❌ FFmpeg capture failed immediately:")
        print(f"Exit code: {proc.returncode}")
        print(f"Error output: {err_content}")
        return proc.returncode

    def poll_all():
        for info in config_infos:
            prefix = info["identifier"] if use_labels else None
            poll_jobs_and_collect(info["jobs"], info["finished_map"], prefix=prefix)
            if play_after_each:
                handle_sequential_playback(info["finished_map"], info["playback_state"], prefix=prefix)

    def wait_for_capacity(target_info):
        while sum(1 for j in target_info["jobs"] if not j["done"]) >= max_concurrency:
            poll_all()
            time.sleep(0.5)

    processed = 0
    seen = set()

    while True:
        time.sleep(2.0)
        files = list_dir_sorted_by_index(primary_info["session_dir"], "live_")
        for f in files:
            if f in seen:
                continue
            if not is_file_stable(f):
                continue
            seen.add(f)

            seg_dirs = {}
            for info in config_infos:
                seg_dir = os.path.join(info["session_dir"], f"seg_{processed:04d}")
                ensure_dir(seg_dir)
                seg_dirs[info["identifier"]] = seg_dir

            seg_src_primary = os.path.join(seg_dirs[primary_info["identifier"]], "source.mp4")
            os.replace(f, seg_src_primary)

            if not validate_video_file(seg_src_primary):
                print(f"⚠️  Warning: Captured file {seg_src_primary} may have issues, but continuing...")
            else:
                print(f"✅ Valid segment captured: {seg_src_primary} ({os.path.getsize(seg_src_primary)} bytes)")

            for info in config_infos[1:]:
                dest = os.path.join(seg_dirs[info["identifier"]], "source.mp4")
                replicate_segment_source(seg_src_primary, dest)

            for info in config_infos:
                wait_for_capacity(info)
                seg_dir = seg_dirs[info["identifier"]]
                job = start_segment_pipeline_async(seg_dir, info["config_path"])
                info["jobs"].append(job)

            poll_all()

            processed += 1
            if max_segments > 0 and processed >= max_segments:
                break

        poll_all()

        if max_segments > 0 and processed >= max_segments:
            break

    if proc.poll() is None:
        proc.terminate()
        proc.wait()
    capture_out.close()
    capture_err.close()

    while any(not job["done"] for info in config_infos for job in info["jobs"]):
        poll_all()
        time.sleep(0.5)

    if play_after_each:
        for info in config_infos:
            prefix = info["identifier"] if use_labels else None
            while info["playback_state"].get("next_index", 0) < processed:
                handle_sequential_playback(info["finished_map"], info["playback_state"], prefix=prefix)
                time.sleep(0.5)
            current = info["playback_state"].get("current")
            if current is not None and current.poll() is None:
                current.wait()

    for info in config_infos:
        indices = sorted(info["finished_map"].keys())
        dubbed_videos = [info["finished_map"][i] for i in indices]
        final_out = os.path.join(info["session_dir"], "final_dub.mp4")
        concat_segments(final_out, dubbed_videos, log_dir=info["session_dir"])

    return 0


def test_camera_setup(camera_spec, audio_device="default"):
    """Test camera and audio setup to help debug issues."""
    os_type = get_os_type()
    print(f"=== Camera Setup Test ===")
    print(f"Operating system: {os_type}")
    print(f"Camera spec: {camera_spec}")
    print(f"Audio device: {audio_device}")
    print()
    
    # Test camera device
    if os_type == "linux":
        if ":" in camera_spec:
            video_device = f"/dev/video{camera_spec.split(':')[0]}"
        elif camera_spec.startswith("/dev/"):
            video_device = camera_spec
        else:
            video_device = f"/dev/video{camera_spec}"
            
        print(f"Testing video device: {video_device}")
        if os.path.exists(video_device):
            print("✅ Video device exists")
            # Test device capabilities
            v4l_cmd = ["v4l2-ctl", "--device", video_device, "--list-formats-ext"]
            v4l_result = subprocess.run(v4l_cmd, capture_output=True, text=True)
            if v4l_result.returncode == 0:
                print("✅ Video device formats:")
                print(v4l_result.stdout)
            else:
                print(f"⚠️  Could not query video formats: {v4l_result.stderr}")
        else:
            print("❌ Video device does not exist")
            return 1
    
    # Test audio device
    if os_type == "linux":
        print(f"\nTesting audio device: {audio_device}")
        if test_audio_device(audio_device):
            print("✅ Audio device available")
        else:
            print("❌ Audio device not available")
            
        # List ALSA devices
        aplay_cmd = ["aplay", "-l"]
        aplay_result = subprocess.run(aplay_cmd, capture_output=True, text=True)
        if aplay_result.returncode == 0:
            print("\n📊 Available ALSA playback devices:")
            print(aplay_result.stdout)
        
        arecord_cmd = ["arecord", "-l"]
        arecord_result = subprocess.run(arecord_cmd, capture_output=True, text=True)
        if arecord_result.returncode == 0:
            print("\n🎤 Available ALSA capture devices:")
            print(arecord_result.stdout)
    
    # Test short capture
    print(f"\n=== Testing 5-second capture ===")
    temp_dir = "/tmp/videolingo_test"
    os.makedirs(temp_dir, exist_ok=True)
    test_output = os.path.join(temp_dir, "test_capture.mp4")
    
    cmd = build_camera_capture_cmd(camera_spec, test_output.replace(".mp4", "_%04d.mp4"), 5, temp_dir, audio_device)
    print(f"Test command: {' '.join(cmd)}")
    
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    time.sleep(7)  # Let it capture for 5+ seconds
    
    if proc.poll() is None:
        proc.terminate()
        proc.wait()
    
    stdout, stderr = proc.communicate()
    print(f"FFmpeg exit code: {proc.returncode}")
    if stderr:
        print(f"FFmpeg stderr:\n{stderr}")
    
    # Check captured files
    import glob
    captured_files = glob.glob(os.path.join(temp_dir, "test_capture_*.mp4"))
    if captured_files:
        for f in captured_files:
            if validate_video_file(f):
                print(f"✅ Successfully captured: {f}")
            else:
                print(f"❌ Captured file is invalid: {f}")
    else:
        print("❌ No files were captured")
    
    # Cleanup
    for f in captured_files:
        try:
            os.remove(f)
        except Exception:
            pass
    try:
        os.rmdir(temp_dir)
    except Exception:
        pass
    
    return 0


# ------------
# CLI
# ------------

def main():
    parser = argparse.ArgumentParser(description="VideoLingo realtime segmenter")
    parser.add_argument("mode", choices=["file", "camera", "list-cameras", "test-camera"], help="Input source mode, list cameras, or test camera setup")
    parser.add_argument("--source", type=str, default="", help="Path to input video when mode=file")
    parser.add_argument("--camera-spec", type=str, default="0", help="Camera device spec: '0:0' for macOS avfoundation, '0' or '/dev/video0' for Linux v4l2 (audio from default ALSA), 'USB2.0 Camera' for Windows dshow")
    parser.add_argument("--audio-device", type=str, default="default", help="Audio device for Linux (ALSA device name, e.g., 'default', 'hw:0', 'plughw:1,0')")
    parser.add_argument("--output", type=str, default="output", help="Base output directory")
    parser.add_argument(
        "--config",
        action="append",
        dest="config",
        default=None,
        help="Config YAML path for main.py (repeat for multiple outputs)",
    )
    parser.add_argument("--segment-seconds", type=int, default=300, help="Segment length in seconds")
    parser.add_argument("--silence-window", type=float, default=10.0, help="Search window around cut (seconds), file mode only")
    parser.add_argument("--silence-db", type=int, default=-35, help="Silence threshold in dB for ffmpeg silencedetect")
    parser.add_argument("--silence-min-dur", type=float, default=0.3, help="Min silence duration in seconds")
    parser.add_argument("--play", action="store_true", help="Play each dubbed segment after finishing")
    parser.add_argument("--max-segments", type=int, default=0, help="Camera mode: stop after N segments (0 means infinite)")
    parser.add_argument("--max-concurrency", type=int, default=2, help="Max concurrent translation jobs")

    args = parser.parse_args()
    config_paths = args.config if args.config else ["config.yaml"]

    if args.mode == "list-cameras":
        os_type = get_os_type()
        print(f"Operating system: {os_type}")
        devices = list_camera_devices()
        if devices:
            print("Available camera devices:")
            for device in devices:
                print(f"  {device}")
        else:
            print("No camera devices found or OS not supported")
        return 0

    if args.mode == "test-camera":
        return test_camera_setup(args.camera_spec, args.audio_device)

    if args.mode == "file":
        if not os.path.exists(args.source):
            print("Source file does not exist")
            return 1
        return process_file_source(
            args.source,
            args.output,
            config_paths,
            args.segment_seconds,
            args.silence_window,
            args.silence_db,
            args.silence_min_dur,
            args.play,
            args.max_concurrency,
        )

    if args.mode == "camera":
        return process_camera_source(
            args.camera_spec,
            args.output,
            config_paths,
            args.segment_seconds,
            args.play,
            args.max_segments,
            args.max_concurrency,
            args.audio_device,
        )

    return 0


if __name__ == "__main__":
    code = main()
    sys.exit(code)
