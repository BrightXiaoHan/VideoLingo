import argparse
import os
import sys
import subprocess
import time
import datetime


# ------------
# Utilities
# ------------

def timestamp_now():
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


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
    return code == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 0


def start_segment_pipeline_async(segment_dir, config_path):
    print(f"Start pipeline (async) for {segment_dir}")
    cmd = [sys.executable, "main.py", "--config", config_path, "--output", segment_dir, "all"]
    log_out = open(os.path.join(segment_dir, "run_all.out"), "w", encoding="utf-8")
    log_err = open(os.path.join(segment_dir, "run_all.err"), "w", encoding="utf-8")
    proc = subprocess.Popen(cmd, stdout=log_out, stderr=log_err, text=True)
    return {"proc": proc, "dir": segment_dir, "out": log_out, "err": log_err, "done": False}


def poll_jobs_and_collect(jobs, finished_map):
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
            print(f"Done: {out_video}")
        else:
            print(f"Pipeline failed for segment {index}")


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


def handle_sequential_playback(finished_map, playback_state):
    # playback_state: {"current": Popen or None, "next_index": int}
    current = playback_state.get("current")
    if current is not None:
        if current.poll() is None:
            return
        playback_state["current"] = None
    next_idx = playback_state.get("next_index", 0)
    if next_idx in finished_map and playback_state.get("current") is None:
        proc = start_playback(finished_map[next_idx])
        playback_state["current"] = proc
        playback_state["next_index"] = next_idx + 1


# ------------
# File source pipeline
# ------------

def process_file_source(source_path, base_output, config_path, segment_seconds, silence_window, silence_db, silence_min_dur, play_after_each, max_concurrency):
    session_dir = os.path.join(base_output, f"session_{timestamp_now()}")
    ensure_dir(session_dir)
    print(f"Session dir: {session_dir}")

    total = ffprobe_duration_seconds(
        source_path,
        out_path=os.path.join(session_dir, "ffprobe_duration.out"),
        err_path=os.path.join(session_dir, "ffprobe_duration.err"),
    )
    print(f"Source duration: {total:.2f}s")
    if total <= 0.0:
        print("Invalid source duration")
        return 1

    current_start = 0.0
    seg_index = 0
    jobs = []
    finished_map = {}
    playback_state = {"current": None, "next_index": 0}

    while current_start < total:
        proposed_end = min(total, current_start + segment_seconds)
        adjusted_end = proposed_end
        if silence_window > 0.0 and proposed_end < total:
            adjusted_end = find_nearest_silence_time(
                source_path,
                proposed_end,
                silence_window,
                silence_db,
                silence_min_dur,
                err_log_path=os.path.join(seg_dir, "silence.err"),
            )
            if adjusted_end <= current_start + 1.0:
                adjusted_end = proposed_end

        seg_dir = os.path.join(session_dir, f"seg_{seg_index:04d}")
        ensure_dir(seg_dir)
        seg_src = os.path.join(seg_dir, "source.mp4")
        ok = extract_segment(source_path, current_start, adjusted_end, seg_src, log_dir=seg_dir)
        if not ok:
            print(f"Failed to extract segment {seg_index}")
            return 2

        # throttle concurrency
        while sum(1 for j in jobs if not j["done"]) >= max_concurrency:
            poll_jobs_and_collect(jobs, finished_map)
            if play_after_each:
                handle_sequential_playback(finished_map, playback_state)
            time.sleep(0.5)

        job = start_segment_pipeline_async(seg_dir, config_path)
        jobs.append(job)

        # brief poll to handle any completed jobs
        poll_jobs_and_collect(jobs, finished_map)
        if play_after_each:
            handle_sequential_playback(finished_map, playback_state)

        seg_index += 1
        current_start = adjusted_end
        if current_start >= total:
            break

    # wait for all jobs to finish
    while any(not j["done"] for j in jobs):
        poll_jobs_and_collect(jobs, finished_map)
        if play_after_each:
            handle_sequential_playback(finished_map, playback_state)
        time.sleep(0.5)

    # stop any ongoing playback
    if playback_state.get("current") is not None and playback_state["current"].poll() is None:
        playback_state["current"].wait()

    # collect dubbed videos in order
    indices = sorted(finished_map.keys())
    dubbed_videos = [finished_map[i] for i in indices]
    final_out = os.path.join(session_dir, "final_dub.mp4")
    concat_segments(final_out, dubbed_videos, log_dir=session_dir)
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


def is_file_stable(path, checks=3, interval=0.5):
    if not os.path.exists(path):
        return False
    last = os.path.getsize(path)
    for _ in range(checks):
        time.sleep(interval)
        now = os.path.getsize(path)
        if now != last:
            last = now
            continue
    return True


def process_camera_source(avfoundation_spec, base_output, config_path, segment_seconds, play_after_each, max_segments, max_concurrency):
    session_dir = os.path.join(base_output, f"session_{timestamp_now()}")
    ensure_dir(session_dir)
    print(f"Session dir: {session_dir}")

    seg_pattern = os.path.join(session_dir, "live_%04d.mp4")
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "avfoundation",
        "-i",
        avfoundation_spec,
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        "-f",
        "segment",
        "-segment_time",
        str(segment_seconds),
        "-reset_timestamps",
        "1",
        seg_pattern,
    ]
    print("Starting live capture...")
    capture_out = open(os.path.join(session_dir, "capture.out"), "w", encoding="utf-8")
    capture_err = open(os.path.join(session_dir, "capture.err"), "w", encoding="utf-8")
    proc = subprocess.Popen(cmd, stdout=capture_out, stderr=capture_err, text=True)

    processed = 0
    seen = set()
    jobs = []
    finished_map = {}
    playback_state = {"current": None, "next_index": 0}

    while True:
        time.sleep(0.5)
        files = list_dir_sorted_by_index(session_dir, "live_")
        for f in files:
            if f in seen:
                continue
            if not is_file_stable(f):
                continue
            seen.add(f)

            seg_dir = os.path.join(session_dir, f"seg_{processed:04d}")
            ensure_dir(seg_dir)
            seg_src = os.path.join(seg_dir, "source.mp4")
            os.replace(f, seg_src)

            # throttle concurrency
            while sum(1 for j in jobs if not j["done"]) >= max_concurrency:
                poll_jobs_and_collect(jobs, finished_map)
                if play_after_each:
                    handle_sequential_playback(finished_map, playback_state)
                time.sleep(0.5)

            job = start_segment_pipeline_async(seg_dir, config_path)
            jobs.append(job)

            poll_jobs_and_collect(jobs, finished_map)
            if play_after_each:
                handle_sequential_playback(finished_map, playback_state)

            processed += 1
            if max_segments > 0 and processed >= max_segments:
                break

        poll_jobs_and_collect(jobs, finished_map)
        if play_after_each:
            handle_sequential_playback(finished_map, playback_state)

        if max_segments > 0 and processed >= max_segments:
            break

    if proc.poll() is None:
        proc.terminate()
        proc.wait()
    capture_out.close()
    capture_err.close()

    while any(not j["done"] for j in jobs):
        poll_jobs_and_collect(jobs, finished_map)
        if play_after_each:
            handle_sequential_playback(finished_map, playback_state)
        time.sleep(0.5)

    if playback_state.get("current") is not None and playback_state["current"].poll() is None:
        playback_state["current"].wait()

    indices = sorted(finished_map.keys())
    dubbed_videos = [finished_map[i] for i in indices]
    final_out = os.path.join(session_dir, "final_dub.mp4")
    concat_segments(final_out, dubbed_videos, log_dir=session_dir)
    return 0


# ------------
# CLI
# ------------

def main():
    parser = argparse.ArgumentParser(description="VideoLingo realtime segmenter")
    parser.add_argument("mode", choices=["file", "camera"], help="Input source mode")
    parser.add_argument("--source", type=str, default="", help="Path to input video when mode=file")
    parser.add_argument("--camera-spec", type=str, default="0:0", help="avfoundation spec like '0:0' when mode=camera (macOS)")
    parser.add_argument("--output", type=str, default="output", help="Base output directory")
    parser.add_argument("--config", type=str, default="config.yaml", help="Config YAML path for main.py")
    parser.add_argument("--segment-seconds", type=int, default=300, help="Segment length in seconds")
    parser.add_argument("--silence-window", type=float, default=10.0, help="Search window around cut (seconds), file mode only")
    parser.add_argument("--silence-db", type=int, default=-35, help="Silence threshold in dB for ffmpeg silencedetect")
    parser.add_argument("--silence-min-dur", type=float, default=0.3, help="Min silence duration in seconds")
    parser.add_argument("--play", action="store_true", help="Play each dubbed segment after finishing")
    parser.add_argument("--max-segments", type=int, default=0, help="Camera mode: stop after N segments (0 means infinite)")
    parser.add_argument("--max-concurrency", type=int, default=2, help="Max concurrent translation jobs")

    args = parser.parse_args()

    if args.mode == "file":
        if not os.path.exists(args.source):
            print("Source file does not exist")
            return 1
        return process_file_source(
            args.source,
            args.output,
            args.config,
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
            args.config,
            args.segment_seconds,
            args.play,
            args.max_segments,
            args.max_concurrency,
        )

    return 0


if __name__ == "__main__":
    code = main()
    sys.exit(code)

