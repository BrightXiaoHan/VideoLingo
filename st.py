import streamlit as st
import os, sys
from core.st_utils.imports_and_utils import *
from core import *

# SET PATH
current_dir = os.path.dirname(os.path.abspath(__file__))
os.environ['PATH'] += os.pathsep + current_dir
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

st.set_page_config(page_title="VideoLingo", page_icon="docs/logo.svg")

SUB_VIDEO = "output/output_sub.mp4"
DUB_VIDEO = "output/output_dub.mp4"
LIP_SYNC_VIDEO = "output/output_lip_sync.mp4"

def text_processing_section():
    st.header(t("b. Translate and Generate Subtitles"))
    with st.container(border=True):
        st.markdown(f"""
        <p style='font-size: 20px;'>
        {t("This stage includes the following steps:")}
        <p style='font-size: 20px;'>
            1. {t("WhisperX word-level transcription")}<br>
            2. {t("Sentence segmentation using NLP and LLM")}<br>
            3. {t("Summarization and multi-step translation")}<br>
            4. {t("Cutting and aligning long subtitles")}<br>
            5. {t("Generating timeline and subtitles")}<br>
            6. {t("Merging subtitles into the video")}
        """, unsafe_allow_html=True)

        if not os.path.exists(SUB_VIDEO):
            if st.button(t("Start Processing Subtitles"), key="text_processing_button"):
                process_text()
                st.rerun()
        else:
            if load_key("burn_subtitles"):
                st.video(SUB_VIDEO)
            download_subtitle_zip_button(text=t("Download All Srt Files"))
            
            if st.button(t("Archive to 'history'"), key="cleanup_in_text_processing"):
                cleanup()
                st.rerun()
            return True

def process_text():
    with st.spinner(t("Using Whisper for transcription...")):
        _2_asr.transcribe()
    with st.spinner(t("Splitting long sentences...")):  
        _3_1_split_nlp.split_by_spacy()
        _3_2_split_meaning.split_sentences_by_meaning()
    with st.spinner(t("Summarizing and translating...")):
        _4_1_summarize.get_summary()
        if load_key("pause_before_translate"):
            input(t("⚠️ PAUSE_BEFORE_TRANSLATE. Go to `output/log/terminology.json` to edit terminology. Then press ENTER to continue..."))
        _4_2_translate.translate_all()
    with st.spinner(t("Processing and aligning subtitles...")): 
        _5_split_sub.split_for_sub_main()
        _6_gen_sub.align_timestamp_main()
    with st.spinner(t("Merging subtitles to video...")):
        _7_sub_into_vid.merge_subtitles_to_video()
    
    st.success(t("Subtitle processing complete! 🎉"))
    st.balloons()

def audio_processing_section():
    st.header(t("c. Dubbing"))
    with st.container(border=True):
        st.markdown(f"""
        <p style='font-size: 20px;'>
        {t("This stage includes the following steps:")}
        <p style='font-size: 20px;'>
            1. {t("Generate audio tasks and chunks")}<br>
            2. {t("Extract reference audio")}<br>
            3. {t("Generate and merge audio files")}<br>
            4. {t("Merge final audio into video")}
        """, unsafe_allow_html=True)
        if not os.path.exists(DUB_VIDEO):
            if st.button(t("Start Audio Processing"), key="audio_processing_button"):
                process_audio()
                st.rerun()
        else:
            st.success(t("Audio processing is complete! You can check the audio files in the `output` folder."))
            if load_key("burn_subtitles"):
                st.video(DUB_VIDEO) 
            if st.button(t("Delete dubbing files"), key="delete_dubbing_files"):
                delete_dubbing_files()
                st.rerun()
            if st.button(t("Archive to 'history'"), key="cleanup_in_audio_processing"):
                cleanup()
                st.rerun()
            return True

def process_audio():
    with st.spinner(t("Generate audio tasks")): 
        _8_1_audio_task.gen_audio_task_main()
        _8_2_dub_chunks.gen_dub_chunks()
    with st.spinner(t("Extract refer audio")):
        _9_refer_audio.extract_refer_audio_main()
    with st.spinner(t("Generate all audio")):
        _10_gen_audio.gen_audio()
    with st.spinner(t("Merge full audio")):
        _11_merge_audio.merge_full_audio()
    with st.spinner(t("Merge dubbing to the video")):
        _12_dub_to_vid.merge_video_audio()
    
    st.success(t("Audio processing complete! 🎇"))
    st.balloons()

def lip_sync_section():
    st.header(t("d. Lip Synchronization"))
    with st.container(border=True):
        st.markdown(f"""
        <p style='font-size: 20px;'>
        {t("This stage applies lip synchronization to match mouth movements with the dubbed audio:")}
        <p style='font-size: 20px;'>
            1. {t("Setup Wav2Lip model and dependencies")}<br>
            2. {t("Detect faces in video frames")}<br>
            3. {t("Generate lip-synced mouth movements")}<br>
            4. {t("Blend synchronized lips back to original video")}
        """, unsafe_allow_html=True)
        
        # Show lip sync settings
        col1, col2 = st.columns(2)
        with col1:
            enable_lip_sync = st.checkbox(
                t("Enable Lip Synchronization"), 
                value=load_key("enable_lip_sync"),
                help=t("Apply lip sync to match mouth movements with dubbed audio")
            )
            update_key("enable_lip_sync", enable_lip_sync)
        
        with col2:
            if enable_lip_sync:
                resize_factor = st.slider(
                    t("Quality vs Speed"), 
                    min_value=0.5, 
                    max_value=2.0, 
                    value=load_key("lip_sync_resize_factor"),
                    step=0.1,
                    help=t("Lower values = better quality but slower processing")
                )
                update_key("lip_sync_resize_factor", resize_factor)
        
        if not os.path.exists(LIP_SYNC_VIDEO):
            if not os.path.exists(DUB_VIDEO):
                st.warning(t("⚠️ Please complete audio processing first before applying lip sync."))
            elif enable_lip_sync:
                if st.button(t("Start Lip Synchronization"), key="lip_sync_button"):
                    process_lip_sync()
                    st.rerun()
            else:
                st.info(t("💡 Enable lip synchronization above to start processing."))
        else:
            st.success(t("Lip synchronization is complete! 🎭"))
            if load_key("burn_subtitles"):
                st.video(LIP_SYNC_VIDEO)
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button(t("Regenerate Lip Sync"), key="regenerate_lip_sync"):
                    if os.path.exists(LIP_SYNC_VIDEO):
                        os.remove(LIP_SYNC_VIDEO)
                    process_lip_sync()
                    st.rerun()
            
            with col2:
                if st.button(t("Archive to 'history'"), key="cleanup_in_lip_sync"):
                    cleanup()
                    st.rerun()

def process_lip_sync():
    with st.spinner(t("Setting up Wav2Lip models...")):
        _13_lip_sync.apply_lip_sync()
    
    if os.path.exists(LIP_SYNC_VIDEO):
        st.success(t("Lip synchronization complete! 🎭"))
        st.balloons()
    else:
        st.error(t("Lip synchronization failed. Please check the logs."))

def main():
    logo_col, _ = st.columns([1,1])
    with logo_col:
        st.image("docs/logo.png", use_column_width=True)
    st.markdown(button_style, unsafe_allow_html=True)
    welcome_text = t("Hello, welcome to VideoLingo. If you encounter any issues, feel free to get instant answers with our Free QA Agent <a href=\"https://share.fastgpt.in/chat/share?shareId=066w11n3r9aq6879r4z0v9rh\" target=\"_blank\">here</a>! You can also try out our SaaS website at <a href=\"https://videolingo.io\" target=\"_blank\">videolingo.io</a> for free!")
    st.markdown(f"<p style='font-size: 20px; color: #808080;'>{welcome_text}</p>", unsafe_allow_html=True)
    # add settings
    with st.sidebar:
        page_setting()
        st.markdown(give_star_button, unsafe_allow_html=True)
    
    download_video_section()
    text_completed = text_processing_section()
    audio_completed = audio_processing_section()
    
    # Only show lip sync section if audio processing is complete
    if audio_completed:
        lip_sync_section()

if __name__ == "__main__":
    main()
