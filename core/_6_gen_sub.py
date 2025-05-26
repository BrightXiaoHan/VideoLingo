import pandas as pd
import os
import re
from rich.panel import Panel
from rich.console import Console
import autocorrect_py as autocorrect
from core.utils import *
from core.utils.models import *
console = Console()

SUBTITLE_OUTPUT_CONFIGS = [ 
    ('src.srt', ['Source']),
    ('trans.srt', ['Translation']),
    ('src_trans.srt', ['Source', 'Translation']),
    ('trans_src.srt', ['Translation', 'Source'])
]

AUDIO_SUBTITLE_OUTPUT_CONFIGS = [
    ('src_subs_for_audio.srt', ['Source']),
    ('trans_subs_for_audio.srt', ['Translation'])
]

def convert_to_srt_format(start_time, end_time):
    """Convert time (in seconds) to the format: hours:minutes:seconds,milliseconds"""
    def seconds_to_hmsm(seconds):
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = seconds % 60
        milliseconds = int(seconds * 1000) % 1000
        return f"{hours:02d}:{minutes:02d}:{int(seconds):02d},{milliseconds:03d}"

    start_srt = seconds_to_hmsm(start_time)
    end_srt = seconds_to_hmsm(end_time)
    return f"{start_srt} --> {end_srt}"

def remove_punctuation(text):
    text = re.sub(r'\s+', ' ', text)
    # For Japanese, Chinese, etc., don't remove all punctuation as it might be important for matching
    # Only remove common punctuation that doesn't affect word boundaries
    text = re.sub(r'[。、，．,!?！？\"\'\-\—\–]', '', text)
    return text.strip()

def show_difference(str1, str2):
    """Show the difference positions between two strings"""
    min_len = min(len(str1), len(str2))
    diff_positions = []
    
    for i in range(min_len):
        if str1[i] != str2[i]:
            diff_positions.append(i)
    
    if len(str1) != len(str2):
        diff_positions.extend(range(min_len, max(len(str1), len(str2))))
    
    print("Difference positions:")
    print(f"Expected sentence: {str1}")
    print(f"Actual match: {str2}")
    print("Position markers: " + "".join("^" if i in diff_positions else " " for i in range(max(len(str1), len(str2)))))
    print(f"Difference indices: {diff_positions}")

def get_sentence_timestamps(df_words, df_sentences):
    time_stamp_list = []
    
    # Detect if we're dealing with Japanese/Chinese text
    sample_text = str(df_sentences['Source'].iloc[0]) if not df_sentences.empty else ""
    is_cjk = any('\u4e00' <= char <= '\u9fff' or '\u3040' <= char <= '\u309f' or '\u30a0' <= char <= '\u30ff' for char in sample_text)
    
    # Build complete string and position mapping
    full_words_str = ''
    position_to_word_idx = {}
    word_boundaries = []  # Store word boundaries for better matching
    
    # For CJK languages, also build a version without any spaces
    full_words_str_no_space = ''
    position_to_word_idx_no_space = {}
    
    for idx, word in enumerate(df_words['text']):
        clean_word = remove_punctuation(word.lower())
        
        # Regular version
        start_pos = len(full_words_str)
        full_words_str += clean_word
        word_boundaries.append((start_pos, len(full_words_str), idx))
        for pos in range(start_pos, len(full_words_str)):
            position_to_word_idx[pos] = idx
        
        # No-space version for CJK
        if is_cjk:
            clean_word_no_space = clean_word.replace(' ', '')
            start_pos_no_space = len(full_words_str_no_space)
            full_words_str_no_space += clean_word_no_space
            for pos in range(start_pos_no_space, len(full_words_str_no_space)):
                position_to_word_idx_no_space[pos] = idx
    
    current_pos = 0
    current_pos_no_space = 0
    
    for idx, sentence in df_sentences['Source'].items():
        clean_sentence = remove_punctuation(sentence.lower()).replace(" ", "")
        sentence_len = len(clean_sentence)
        
        match_found = False
        
        # For CJK, try matching in the no-space version first
        if is_cjk and full_words_str_no_space:
            search_text = full_words_str_no_space
            search_pos = current_pos_no_space
            pos_to_idx = position_to_word_idx_no_space
        else:
            search_text = full_words_str
            search_pos = current_pos
            pos_to_idx = position_to_word_idx
        
        # Try exact match first
        while search_pos <= len(search_text) - sentence_len:
            if search_text[search_pos:search_pos+sentence_len] == clean_sentence:
                start_word_idx = pos_to_idx[search_pos]
                end_word_idx = pos_to_idx[min(search_pos + sentence_len - 1, len(search_text) - 1)]
                
                time_stamp_list.append((
                    float(df_words['start'][start_word_idx]),
                    float(df_words['end'][end_word_idx])
                ))
                
                if is_cjk:
                    current_pos_no_space = search_pos + sentence_len
                else:
                    current_pos = search_pos + sentence_len
                match_found = True
                break
            search_pos += 1
        
        # If no exact match found, try fuzzy matching
        if not match_found and search_pos > 0:
            # Reset position and try with more flexible matching
            search_pos = max(0, search_pos - sentence_len)
            best_match_score = 0
            best_match_pos = -1
            
            # Search in a window around the expected position
            search_window = min(len(search_text) - sentence_len, search_pos + sentence_len * 2)
            for pos in range(search_pos, search_window + 1):
                if pos + sentence_len <= len(search_text):
                    candidate = search_text[pos:pos+sentence_len]
                    # Calculate similarity
                    matches = sum(1 for a, b in zip(clean_sentence, candidate) if a == b)
                    score = matches / sentence_len
                    
                    if score > best_match_score and score > 0.75:  # Lower threshold for CJK
                        best_match_score = score
                        best_match_pos = pos
            
            if best_match_pos >= 0:
                start_word_idx = pos_to_idx[best_match_pos]
                end_word_idx = pos_to_idx[min(best_match_pos + sentence_len - 1, len(search_text) - 1)]
                
                time_stamp_list.append((
                    float(df_words['start'][start_word_idx]),
                    float(df_words['end'][end_word_idx])
                ))
                
                if is_cjk:
                    current_pos_no_space = best_match_pos + sentence_len
                else:
                    current_pos = best_match_pos + sentence_len
                match_found = True
                console.print(f"[yellow]⚠️ Fuzzy match found for sentence with {best_match_score:.1%} similarity: {sentence[:30]}...[/yellow]")
            
        if not match_found:
            print(f"\n⚠️ Warning: No match found for sentence: {sentence}")
            show_difference(clean_sentence, 
                          full_words_str[current_pos:current_pos+len(clean_sentence)] if current_pos < len(full_words_str) else "")
            print("\nOriginal sentence:", df_sentences['Source'][idx])
            print(f"Clean sentence to match: {clean_sentence}")
            print(f"Search position: {current_pos}, Total length: {len(full_words_str)}")
            
            # Instead of raising error, use approximate timing
            console.print(f"[yellow]Using approximate timing for unmatched sentence[/yellow]")
            if time_stamp_list:
                # Use the end time of the last sentence plus a gap
                last_end = time_stamp_list[-1][1]
                approx_duration = 2.0  # Default 2 seconds per sentence
                time_stamp_list.append((last_end + 0.1, last_end + approx_duration))
            else:
                # First sentence, start from beginning
                time_stamp_list.append((0.0, 2.0))
            
            # Continue with next sentence instead of raising error
            # raise ValueError("❎ No match found for sentence.")
    
    return time_stamp_list

def align_timestamp(df_text, df_translate, subtitle_output_configs: list, output_dir: str, for_display: bool = True):
    """Align timestamps and add a new timestamp column to df_translate"""
    df_trans_time = df_translate.copy()

    # Assign an ID to each word in df_text['text'] and create a new DataFrame
    words = df_text['text'].str.split(expand=True).stack().reset_index(level=1, drop=True).reset_index()
    words.columns = ['id', 'word']
    words['id'] = words['id'].astype(int)

    # Process timestamps ⏰
    time_stamp_list = get_sentence_timestamps(df_text, df_translate)
    df_trans_time['timestamp'] = time_stamp_list
    df_trans_time['duration'] = df_trans_time['timestamp'].apply(lambda x: x[1] - x[0])

    # Remove gaps 🕳️
    for i in range(len(df_trans_time)-1):
        delta_time = df_trans_time.loc[i+1, 'timestamp'][0] - df_trans_time.loc[i, 'timestamp'][1]
        if 0 < delta_time < 1:
            df_trans_time.at[i, 'timestamp'] = (df_trans_time.loc[i, 'timestamp'][0], df_trans_time.loc[i+1, 'timestamp'][0])

    # Convert start and end timestamps to SRT format
    df_trans_time['timestamp'] = df_trans_time['timestamp'].apply(lambda x: convert_to_srt_format(x[0], x[1]))

    # Polish subtitles: replace punctuation in Translation if for_display
    if for_display:
        df_trans_time['Translation'] = df_trans_time['Translation'].apply(lambda x: re.sub(r'[，。]', ' ', x).strip())

    # Output subtitles 📜
    def generate_subtitle_string(df, columns):
        return ''.join([f"{i+1}\n{row['timestamp']}\n{row[columns[0]].strip()}\n{row[columns[1]].strip() if len(columns) > 1 else ''}\n\n" for i, row in df.iterrows()]).strip()

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        for filename, columns in subtitle_output_configs:
            subtitle_str = generate_subtitle_string(df_trans_time, columns)
            with open(os.path.join(output_dir, filename), 'w', encoding='utf-8') as f:
                f.write(subtitle_str)
    
    return df_trans_time

# ✨ Beautify the translation
def clean_translation(x):
    if pd.isna(x):
        return ''
    cleaned = str(x).strip('。').strip('，')
    return autocorrect.format(cleaned)

def align_timestamp_main():
    df_text = pd.read_excel(_2_CLEANED_CHUNKS)
    df_text['text'] = df_text['text'].str.strip('"').str.strip()
    df_translate = pd.read_excel(_5_SPLIT_SUB)
    df_translate['Translation'] = df_translate['Translation'].apply(clean_translation)
    
    align_timestamp(df_text, df_translate, SUBTITLE_OUTPUT_CONFIGS, _OUTPUT_DIR)
    console.print(Panel("[bold green]🎉📝 Subtitles generation completed! Please check in the `output` folder 👀[/bold green]"))

    # for audio
    df_translate_for_audio = pd.read_excel(_5_REMERGED) # use remerged file to avoid unmatched lines when dubbing
    df_translate_for_audio['Translation'] = df_translate_for_audio['Translation'].apply(clean_translation)
    
    align_timestamp(df_text, df_translate_for_audio, AUDIO_SUBTITLE_OUTPUT_CONFIGS, _AUDIO_DIR)
    console.print(Panel(f"[bold green]🎉📝 Audio subtitles generation completed! Please check in the `{_AUDIO_DIR}` folder 👀[/bold green]"))
    

if __name__ == '__main__':
    align_timestamp_main()