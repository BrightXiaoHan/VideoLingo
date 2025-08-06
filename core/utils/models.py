# ------------------------------------------
# 默认输出目录基础路径
# ------------------------------------------
import os
_BASE_OUTPUT_DIR = os.environ.get('VIDEOLINGO_OUTPUT_DIR', "output")

# ------------------------------------------
# 动态路径生成函数
# ------------------------------------------

def get_output_dir():
    """Get current output directory"""
    return _BASE_OUTPUT_DIR

def set_output_dir(new_dir):
    """Set new output directory and update all paths"""
    global _BASE_OUTPUT_DIR
    _BASE_OUTPUT_DIR = new_dir
    _update_all_paths()

def _update_all_paths():
    """Update all path constants with current output directory"""
    global _2_CLEANED_CHUNKS, _3_1_SPLIT_BY_NLP, _3_2_SPLIT_BY_MEANING
    global _4_1_TERMINOLOGY, _4_2_TRANSLATION, _5_SPLIT_SUB, _5_REMERGED
    global _8_1_AUDIO_TASK, _OUTPUT_DIR, _AUDIO_DIR, _RAW_AUDIO_FILE
    global _VOCAL_AUDIO_FILE, _BACKGROUND_AUDIO_FILE, _AUDIO_REFERS_DIR
    global _AUDIO_SEGS_DIR, _AUDIO_TMP_DIR
    
    base = _BASE_OUTPUT_DIR
    
    # Update all path constants
    _OUTPUT_DIR = base
    _AUDIO_DIR = f"{base}/audio"
    
    # Log files
    _2_CLEANED_CHUNKS = f"{base}/log/cleaned_chunks.xlsx"
    _3_1_SPLIT_BY_NLP = f"{base}/log/split_by_nlp.txt"
    _3_2_SPLIT_BY_MEANING = f"{base}/log/split_by_meaning.txt"
    _4_1_TERMINOLOGY = f"{base}/log/terminology.json"
    _4_2_TRANSLATION = f"{base}/log/translation_results.xlsx"
    _5_SPLIT_SUB = f"{base}/log/translation_results_for_subtitles.xlsx"
    _5_REMERGED = f"{base}/log/translation_results_remerged.xlsx"
    
    # Audio files
    _8_1_AUDIO_TASK = f"{base}/audio/tts_tasks.xlsx"
    _RAW_AUDIO_FILE = f"{base}/audio/raw.mp3"
    _VOCAL_AUDIO_FILE = f"{base}/audio/vocal.mp3"
    _BACKGROUND_AUDIO_FILE = f"{base}/audio/background.mp3"
    _AUDIO_REFERS_DIR = f"{base}/audio/refers"
    _AUDIO_SEGS_DIR = f"{base}/audio/segs"
    _AUDIO_TMP_DIR = f"{base}/audio/tmp"

# ------------------------------------------
# 初始化默认路径常量
# ------------------------------------------

# Initialize with default paths
_2_CLEANED_CHUNKS = f"{_BASE_OUTPUT_DIR}/log/cleaned_chunks.xlsx"
_3_1_SPLIT_BY_NLP = f"{_BASE_OUTPUT_DIR}/log/split_by_nlp.txt"
_3_2_SPLIT_BY_MEANING = f"{_BASE_OUTPUT_DIR}/log/split_by_meaning.txt"
_4_1_TERMINOLOGY = f"{_BASE_OUTPUT_DIR}/log/terminology.json"
_4_2_TRANSLATION = f"{_BASE_OUTPUT_DIR}/log/translation_results.xlsx"
_5_SPLIT_SUB = f"{_BASE_OUTPUT_DIR}/log/translation_results_for_subtitles.xlsx"
_5_REMERGED = f"{_BASE_OUTPUT_DIR}/log/translation_results_remerged.xlsx"

_8_1_AUDIO_TASK = f"{_BASE_OUTPUT_DIR}/audio/tts_tasks.xlsx"

_OUTPUT_DIR = _BASE_OUTPUT_DIR
_AUDIO_DIR = f"{_BASE_OUTPUT_DIR}/audio"
_RAW_AUDIO_FILE = f"{_BASE_OUTPUT_DIR}/audio/raw.mp3"
_VOCAL_AUDIO_FILE = f"{_BASE_OUTPUT_DIR}/audio/vocal.mp3"
_BACKGROUND_AUDIO_FILE = f"{_BASE_OUTPUT_DIR}/audio/background.mp3"
_AUDIO_REFERS_DIR = f"{_BASE_OUTPUT_DIR}/audio/refers"
_AUDIO_SEGS_DIR = f"{_BASE_OUTPUT_DIR}/audio/segs"
_AUDIO_TMP_DIR = f"{_BASE_OUTPUT_DIR}/audio/tmp"

# ------------------------------------------
# 导出
# ------------------------------------------

__all__ = [
    "_2_CLEANED_CHUNKS",
    "_3_1_SPLIT_BY_NLP", 
    "_3_2_SPLIT_BY_MEANING",
    "_4_1_TERMINOLOGY",
    "_4_2_TRANSLATION",
    "_5_SPLIT_SUB",
    "_5_REMERGED",
    "_8_1_AUDIO_TASK",
    "_OUTPUT_DIR",
    "_AUDIO_DIR",
    "_RAW_AUDIO_FILE",
    "_VOCAL_AUDIO_FILE",
    "_BACKGROUND_AUDIO_FILE",
    "_AUDIO_REFERS_DIR",
    "_AUDIO_SEGS_DIR",
    "_AUDIO_TMP_DIR",
    "get_output_dir",
    "set_output_dir"
]
