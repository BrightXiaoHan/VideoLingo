import argparse
import os
import sys

# ------------
# Early path setup before importing core modules
# ------------
def early_setup_paths(config_path, output_dir):
    """Set up paths before importing core modules"""
    # Import and configure config utils first
    import core.utils.config_utils as config_utils
    config_utils.CONFIG_PATH = config_path
    
    # Import and configure models paths
    import core.utils.models as models
    models.set_output_dir(output_dir)
    
    # Create necessary directories
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(f"{output_dir}/log", exist_ok=True)
    os.makedirs(f"{output_dir}/audio", exist_ok=True)
    os.makedirs(f"{output_dir}/audio/refers", exist_ok=True)
    os.makedirs(f"{output_dir}/audio/segs", exist_ok=True)
    os.makedirs(f"{output_dir}/audio/tmp", exist_ok=True)

# Parse args early to get paths
parser = argparse.ArgumentParser(description='VideoLingo CLI')
parser.add_argument('--config', type=str, default='config.yaml',
                   help='Path to configuration file (default: config.yaml)')
parser.add_argument('--output', type=str, default='output',
                   help='Output directory path (default: output)')
early_args, remaining_args = parser.parse_known_args()

# Set up environment variable and paths before importing core modules  
os.environ['VIDEOLINGO_OUTPUT_DIR'] = early_args.output
early_setup_paths(early_args.config, early_args.output)

# Now import core modules with correct paths
from core import *

# ------------
# CLI Implementation
# ------------

def main():
    # Add subcommands to the existing parser
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Subtitle command
    parser_sub = subparsers.add_parser('subtitle', help='Process subtitles')
    
    # Audio command  
    parser_audio = subparsers.add_parser('audio', help='Process audio dubbing')
    
    # Lipsync command
    parser_lipsync = subparsers.add_parser('lipsync', help='Process lip synchronization')
    parser_lipsync.add_argument('--enable', action='store_true', help='Enable lip sync')
    parser_lipsync.add_argument('--quality', type=float, default=1.0, 
                               help='Quality vs speed (0.5-2.0, default=1.0)')
    
    # Parse all arguments including subcommands
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    print(f"Configuration file: {args.config}")
    print(f"Output directory: {args.output}")
    
    # Execute commands
    if args.command == 'subtitle':
        process_text_cli(args.output)
    elif args.command == 'audio':
        process_audio_cli(args.output)
    elif args.command == 'lipsync':
        process_lip_sync_cli(enable=args.enable, resize_factor=args.quality, output_dir=args.output)

# ------------
# CLI Processing Functions
# ------------

def process_text_cli(output_dir):
    print(f"Using output directory: {output_dir}")
    print("Using Whisper for transcription...")
    _2_asr.transcribe()
    
    print("Splitting long sentences...")
    _3_1_split_nlp.split_by_spacy()
    _3_2_split_meaning.split_sentences_by_meaning()
    
    print("Summarizing and translating...")
    _4_1_summarize.get_summary()
    _4_2_translate.translate_all()
    
    print("Processing and aligning subtitles...")
    _5_split_sub.split_for_sub_main()
    _6_gen_sub.align_timestamp_main()
    
    print("Merging subtitles to video...")
    _7_sub_into_vid.merge_subtitles_to_video()
    
    print("Subtitle processing complete! 🎉")

def process_audio_cli(output_dir):
    print(f"Using output directory: {output_dir}")
    print("Generate audio tasks...")
    _8_1_audio_task.gen_audio_task_main()
    _8_2_dub_chunks.gen_dub_chunks()
    
    print("Extract reference audio...")
    _9_refer_audio.extract_refer_audio_main()
    
    print("Generate all audio...")
    _10_gen_audio.gen_audio()
    
    print("Merge full audio...")
    _11_merge_audio.merge_full_audio()
    
    print("Merge dubbing to the video...")
    _12_dub_to_vid.merge_video_audio()
    
    print("Audio processing complete! 🎇")

def process_lip_sync_cli(enable=True, resize_factor=1.0, output_dir=None):
    if not enable:
        print("Lip sync disabled. Use --enable to activate")
        return
    
    if output_dir:
        print(f"Using output directory: {output_dir}")
        
    print(f"Applying lip sync (Quality: {resize_factor})...")
    # ------------
    # TODO: Implement lip sync functionality
    # ------------
    print("Warning: Lip sync module (_13_lip_sync) not implemented yet")
    print("Lip synchronization complete! 🎭")

if __name__ == "__main__":
    main()
