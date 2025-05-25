import os
import pandas as pd
import warnings
from core.spacy_utils.load_nlp_model import init_nlp, SPLIT_BY_MARK_FILE
from core.utils.config_utils import load_key, get_joiner
from rich import print as rprint

warnings.filterwarnings("ignore", category=FutureWarning)

def process_text_in_chunks(text, nlp, max_bytes=45000):
    """Process text in chunks to avoid tokenizer limits, especially for Japanese."""
    if nlp.lang == "ja":
        # For Japanese, we need to be careful about byte limits
        chunks = []
        current_chunk = ""
        current_bytes = 0
        
        # Split by sentences first if possible
        temp_sentences = text.split('。')
        
        for sent in temp_sentences:
            sent_with_period = sent + '。' if sent else ''
            sent_bytes = len(sent_with_period.encode('utf-8'))
            
            if current_bytes + sent_bytes > max_bytes and current_chunk:
                chunks.append(current_chunk.rstrip('。') + '。')
                current_chunk = sent_with_period
                current_bytes = sent_bytes
            else:
                current_chunk += sent_with_period
                current_bytes += sent_bytes
        
        if current_chunk:
            chunks.append(current_chunk)
        
        # Process each chunk
        all_sentences = []
        for chunk in chunks:
            if chunk.strip():
                doc = nlp(chunk)
                all_sentences.extend([sent.text.strip() for sent in doc.sents])
        
        return all_sentences
    else:
        # For other languages, process normally
        doc = nlp(text)
        return [sent.text.strip() for sent in doc.sents]

def split_by_mark(nlp):
    whisper_language = load_key("whisper.language")
    language = load_key("whisper.detected_language") if whisper_language == 'auto' else whisper_language # consider force english case
    joiner = get_joiner(language)
    rprint(f"[blue]🔍 Using {language} language joiner: '{joiner}'[/blue]")
    chunks = pd.read_excel("output/log/cleaned_chunks.xlsx")
    chunks.text = chunks.text.apply(lambda x: x.strip('"').strip(""))
    
    # join with joiner
    input_text = joiner.join(chunks.text.to_list())
    
    # Check text size and process accordingly
    text_bytes = len(input_text.encode('utf-8'))
    if nlp.lang == "ja" and text_bytes > 45000:
        rprint(f"[yellow]⚠️ Large Japanese text detected ({text_bytes} bytes), processing in chunks...[/yellow]")
        sentences_list = process_text_in_chunks(input_text, nlp)
    else:
        doc = nlp(input_text)
        assert doc.has_annotation("SENT_START")
        sentences_list = [sent.text.strip() for sent in doc.sents]

    # skip - and ...
    sentences_by_mark = []
    current_sentence = []
    
    # iterate all sentences
    for text in sentences_list:
        # check if the current sentence ends with - or ...
        if current_sentence and (
            text.startswith('-') or 
            text.startswith('...') or
            current_sentence[-1].endswith('-') or
            current_sentence[-1].endswith('...')
        ):
            current_sentence.append(text)
        else:
            if current_sentence:
                sentences_by_mark.append(joiner.join(current_sentence))
                current_sentence = []
            current_sentence.append(text)
    
    # add the last sentence
    if current_sentence:
        sentences_by_mark.append(joiner.join(current_sentence))

    with open(SPLIT_BY_MARK_FILE, "w", encoding="utf-8") as output_file:
        for i, sentence in enumerate(sentences_by_mark):
            if i > 0 and sentence.strip() in [',', '.', '，', '。', '？', '！']:
                # ! If the current line contains only punctuation, merge it with the previous line, this happens in Chinese, Japanese, etc.
                output_file.seek(output_file.tell() - 1, os.SEEK_SET)  # Move to the end of the previous line
                output_file.write(sentence)  # Add the punctuation
            else:
                output_file.write(sentence + "\n")
    
    rprint(f"[green]💾 Sentences split by punctuation marks saved to →  `{SPLIT_BY_MARK_FILE}`[/green]")

if __name__ == "__main__":
    nlp = init_nlp()
    split_by_mark(nlp)
