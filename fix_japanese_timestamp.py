#!/usr/bin/env python3
"""
Fix for Japanese text timestamp matching issue in VideoLingo
This patch improves the sentence matching algorithm for CJK languages
"""

import re

def patch_gen_sub():
    """Patch the _6_gen_sub.py file to better handle Japanese text"""
    
    # Read the original file
    with open('core/_6_gen_sub.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # New get_sentence_timestamps function
    new_function = '''def get_sentence_timestamps(df_words, df_sentences):
    time_stamp_list = []
    
    # Detect if we're dealing with Japanese/Chinese text
    sample_text = str(df_sentences['Source'].iloc[0]) if not df_sentences.empty else ""
    is_cjk = any('\\u4e00' <= char <= '\\u9fff' or '\\u3040' <= char <= '\\u309f' or '\\u30a0' <= char <= '\\u30ff' for char in sample_text)
    
    # Build complete string and position mapping
    full_words_str = ''
    position_to_word_idx = {}
    
    # For CJK, concatenate without spaces
    for idx, word in enumerate(df_words['text']):
        clean_word = remove_punctuation(word.lower())
        if is_cjk:
            clean_word = clean_word.replace(' ', '')
        
        start_pos = len(full_words_str)
        full_words_str += clean_word
        for pos in range(start_pos, len(full_words_str)):
            position_to_word_idx[pos] = idx
    
    current_pos = 0
    for idx, sentence in df_sentences['Source'].items():
        clean_sentence = remove_punctuation(sentence.lower()).replace(" ", "")
        sentence_len = len(clean_sentence)
        
        if sentence_len == 0:
            console.print(f"[yellow]Warning: Empty sentence at index {idx}[/yellow]")
            time_stamp_list.append((0.0, 0.1))
            continue
        
        match_found = False
        # Try exact match with sliding window
        max_search_pos = min(len(full_words_str) - sentence_len + 1, current_pos + sentence_len * 3)
        
        for search_pos in range(current_pos, max_search_pos):
            if search_pos + sentence_len <= len(full_words_str):
                if full_words_str[search_pos:search_pos+sentence_len] == clean_sentence:
                    start_word_idx = position_to_word_idx[search_pos]
                    end_word_idx = position_to_word_idx[search_pos + sentence_len - 1]
                    
                    time_stamp_list.append((
                        float(df_words['start'][start_word_idx]),
                        float(df_words['end'][end_word_idx])
                    ))
                    
                    current_pos = search_pos + sentence_len
                    match_found = True
                    break
        
        # If no exact match, try fuzzy match
        if not match_found:
            best_score = 0
            best_pos = -1
            
            for search_pos in range(max(0, current_pos - 10), max_search_pos):
                if search_pos + sentence_len <= len(full_words_str):
                    candidate = full_words_str[search_pos:search_pos+sentence_len]
                    score = sum(1 for a, b in zip(clean_sentence, candidate) if a == b) / sentence_len
                    
                    if score > best_score and score > 0.7:
                        best_score = score
                        best_pos = search_pos
            
            if best_pos >= 0:
                start_word_idx = position_to_word_idx[best_pos]
                end_word_idx = position_to_word_idx[best_pos + sentence_len - 1]
                
                time_stamp_list.append((
                    float(df_words['start'][start_word_idx]),
                    float(df_words['end'][end_word_idx])
                ))
                
                current_pos = best_pos + sentence_len
                match_found = True
                console.print(f"[yellow]Fuzzy match ({best_score:.0%}): {sentence[:30]}...[/yellow]")
        
        if not match_found:
            console.print(f"[red]No match found for: {sentence}[/red]")
            console.print(f"[red]Clean version: {clean_sentence}[/red]")
            # Use approximate timing based on position
            if time_stamp_list:
                last_end = time_stamp_list[-1][1]
                time_stamp_list.append((last_end, last_end + 2.0))
            else:
                time_stamp_list.append((0.0, 2.0))
            console.print(f"[yellow]Using approximate timing[/yellow]")
    
    return time_stamp_list'''
    
    # Find and replace the function
    pattern = r'def get_sentence_timestamps\(df_words, df_sentences\):.*?return time_stamp_list'
    
    # Use re.DOTALL to match across multiple lines
    content = re.sub(pattern, new_function, content, flags=re.DOTALL)
    
    # Write back
    with open('core/_6_gen_sub.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ Patched _6_gen_sub.py successfully!")

if __name__ == "__main__":
    patch_gen_sub() 