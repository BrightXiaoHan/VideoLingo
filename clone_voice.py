"""Create a FishTTS clone model from a local audio file and print config snippets.

Usage:
  python clone_voice.py /path/to/ref.wav --name MyVoice

It returns a model_id you can paste into config.yaml.
"""

import argparse
from pathlib import Path
from typing import Tuple

from core.tts_backend.fish_tts import create_voice_model, wait_for_model_ready


def build_snippets(model_id: str, label: str) -> Tuple[str, str]:
    """Return preset-mode and clone-mode YAML snippets for a given model id."""
    preset = (
        "fish_tts:\n"
        "  mode: 'preset'\n"
        f"  character: '{label}'\n"
        "  character_id_dict:\n"
        f"    '{label}': '{model_id}'\n"
    )
    clone_force = (
        "fish_tts:\n"
        "  mode: 'clone'\n"
        f"  force_model_id: '{model_id}'\n"
    )
    return preset, clone_force


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Upload an audio sample to FishTTS, create a clone model, and print config snippets."
    )
    parser.add_argument("audio", help="Path to your reference audio file (wav/mp3/m4a etc).")
    parser.add_argument(
        "--name",
        default=None,
        help="Label to use in the YAML snippet; defaults to the audio filename (without extension).",
    )
    parser.add_argument(
        "--title",
        default=None,
        help="Title for the clone model shown in FishTTS; defaults to VideoLingo_ManualClone_<name>.",
    )
    parser.add_argument(
        "--description",
        default="Voice clone created by VideoLingo helper script.",
        help="Optional description for the model.",
    )
    parser.add_argument(
        "--no-wait",
        action="store_true",
        help="Skip waiting for model training status (advanced; default waits).",
    )
    args = parser.parse_args()

    audio_path = Path(args.audio).expanduser().resolve()
    if not audio_path.exists():
        print(f"❌ Audio file not found: {audio_path}")
        return 1

    label = args.name or audio_path.stem
    title = args.title or f"VideoLingo_ManualClone_{label}"

    print(f"📤 Uploading and creating clone model from {audio_path} ...")
    model_id = create_voice_model(str(audio_path), title=title, description=args.description)
    print(f"✅ Model created with id: {model_id}")

    if not args.no_wait:
        ready = wait_for_model_ready(model_id)
        if not ready:
            print("⚠️  Model not ready yet. You can rerun later with --no-wait once ready.")
            return 1
        print("⏱️  Model reported ready.")

    preset_snippet, clone_snippet = build_snippets(model_id, label)

    print("\nPaste one of the snippets into config.yaml (choose one):\n")
    print("[Option 1] Use as preset voice")
    print(preset_snippet)
    print("[Option 2] Keep clone mode but force this ID")
    print(clone_snippet)
    print("Remember to keep your fish_tts.api_key/base_url configured.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
