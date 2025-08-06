import spacy
from spacy.cli import download
from core.utils import rprint, load_key, except_handler

SPACY_MODEL_MAP = load_key("spacy_model_map")

def get_spacy_model(language: str):
    model = SPACY_MODEL_MAP.get(language.lower(), "en_core_web_md")
    if language not in SPACY_MODEL_MAP:
        rprint(f"[yellow]Spacy model does not support '{language}', using en_core_web_md model as fallback...[/yellow]")
    return model

@except_handler("Failed to load NLP Spacy model")
def init_nlp():
    whisper_language = load_key("whisper.language")
    if whisper_language == "auto":
        language = load_key("whisper.detected_language")
    else:
        language = whisper_language
    model = get_spacy_model(language)
    rprint(f"[blue]⏳ Loading NLP Spacy model: <{model}> ...[/blue]")
    try:
        nlp = spacy.load(model)
    except:
        rprint(f"[yellow]Downloading {model} model...[/yellow]")
        rprint("[yellow]If download failed, please check your network and try again.[/yellow]")
        download(model)
        nlp = spacy.load(model)
    rprint("[green]✅ NLP Spacy model loaded successfully![/green]")
    return nlp

# --------------------
# define the intermediate files
# --------------------
from core.utils.models import get_output_dir

def get_split_files():
    """Get dynamic split file paths"""
    base_dir = get_output_dir()
    return {
        'comma': f"{base_dir}/log/split_by_comma.txt",
        'connector': f"{base_dir}/log/split_by_connector.txt", 
        'mark': f"{base_dir}/log/split_by_mark.txt"
    }

# ------------
# 向后兼容的函数式常量 (动态路径)
# ------------
def get_comma_file():
    return f"{get_output_dir()}/log/split_by_comma.txt"

def get_connector_file():
    return f"{get_output_dir()}/log/split_by_connector.txt"

def get_mark_file():
    return f"{get_output_dir()}/log/split_by_mark.txt"

# 为了向后兼容，保留原始常量名作为函数
SPLIT_BY_COMMA_FILE = get_comma_file
SPLIT_BY_CONNECTOR_FILE = get_connector_file  
SPLIT_BY_MARK_FILE = get_mark_file
