import streamlit as st
import os
import nltk
import json
from dotenv import load_dotenv
from modules.text_gen import TextGenerator
from modules.audio_gen import AudioGenerator
from modules.evaluation import Evaluator

import re

# Helper for Highlighting
def highlight_text_html(text, error_words):
    if not error_words:
        return text
    
    highlighted_text = text
    # Sort error words by length descending to avoid partial replacement issues
    # Filter out empty strings or very short noise
    error_words = sorted(list(set([w for w in error_words if len(w) > 1])), key=len, reverse=True)
    
    for word in error_words:
        # Use regex word boundaries \b to match whole words only, case insensitive
        try:
            pattern = re.compile(r'\b' + re.escape(word) + r'\b', re.IGNORECASE)
            highlighted_text = pattern.sub(
                lambda m: f'<span style="background-color: #ffcccc; color: #cc0000; padding: 0 2px; border-radius: 3px; font-weight: bold;">{m.group(0)}</span>', 
                highlighted_text
            )
        except:
            continue
            
    return highlighted_text

# Load environment variables
load_dotenv()

# Streamlit Cloud Secrets Integration
# If running on Streamlit Cloud, secrets are in st.secrets.
# We inject them into os.environ so downstream modules (using os.getenv) work transparently.
if hasattr(st, "secrets"):
    for key, value in st.secrets.items():
        # Only inject if not already set (preserve local .env preference or override? usually secrets override)
        # But st.secrets are usually flat for simple keys. 
        # Let's handle specific known keys to avoid polluting env with nested dicts if secrets.toml is complex.
        if key in ["DASHSCOPE_API_KEY", "ALIYUN_APP_KEY", "ALIYUN_AK_ID", "ALIYUN_AK_SECRET"]:
             os.environ[key] = value

# Set page config
st.set_page_config(page_title="英语个性化跟读工具 Ver 0.1", layout="wide", initial_sidebar_state="expanded")

# Ensure NLTK data
def ensure_nltk_data():
    pass 
    # Skip auto-download to prevent blocking. 
    # If punkt is missing, process_imported_text will fallback to plain text.
    # try:
    #     nltk.data.find('tokenizers/punkt')
    # except LookupError:
    #     with st.spinner("Downloading NLTK data (punkt)..."):
    #         try:
    #             nltk.download('punkt', quiet=True)
    #         except Exception as e:
    #             st.error(f"Failed to download NLTK data: {e}")

ensure_nltk_data()

# Library Logic
LIBRARY_FILE = "library.json"
if not os.path.exists(LIBRARY_FILE):
    with open(LIBRARY_FILE, "w") as f:
        json.dump([], f)

def load_library():
    try:
        with open(LIBRARY_FILE, "r", encoding='utf-8') as f:
            return json.load(f)
    except:
        return []

def save_to_library(item):
    lib = load_library()
    # Check duplicate by title
    for i in lib:
        if i.get('title') == item.get('title'):
            lib.remove(i)
            break
    lib.append(item)
    with open(LIBRARY_FILE, "w", encoding='utf-8') as f:
        json.dump(lib, f, indent=2, ensure_ascii=False)

# Custom CSS - UI/UX Pro Max
st.markdown("""
<style>
    /* Global Font */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', system-ui, -apple-system, sans-serif;
    }

    /* Main Background */
    .stApp {
        background-color: #F8FAFC;
        background-image: radial-gradient(#E2E8F0 1px, transparent 1px);
        background-size: 24px 24px;
    }

    /* Sidebar Glassmorphism */
    section[data-testid="stSidebar"] {
        background-color: rgba(255, 255, 255, 0.9);
        backdrop-filter: blur(12px);
        border-right: 1px solid rgba(226, 232, 240, 0.8);
    }

    /* Headings */
    h1, h2, h3 {
        color: #1E293B;
        font-weight: 700;
        letter-spacing: -0.025em;
    }
    
    h1 {
        background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        padding-bottom: 0.2em;
    }

    /* Primary Buttons */
    .stButton > button {
        background: linear-gradient(135deg, #3B82F6 0%, #2563EB 100%);
        color: white;
        border: none;
        border-radius: 12px;
        padding: 12px 24px;
        font-weight: 600;
        letter-spacing: 0.01em;
        box-shadow: 0 4px 6px -1px rgba(37, 99, 235, 0.2), 0 2px 4px -1px rgba(37, 99, 235, 0.1);
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    }

    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 8px 12px -1px rgba(37, 99, 235, 0.3);
        background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%);
    }

    /* Card Style (Glassmorphism) */
    .content-card {
        background: rgba(255, 255, 255, 0.95);
        backdrop-filter: blur(16px);
        padding: 32px;
        border-radius: 20px;
        border: 1px solid rgba(255, 255, 255, 0.6);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05), 0 4px 6px -2px rgba(0, 0, 0, 0.025);
        margin-bottom: 24px;
        transition: transform 0.2s ease;
    }
    
    .content-card:hover {
        transform: translateY(-2px);
    }

    /* Tags */
    .el-tag {
        display: inline-flex;
        align-items: center;
        padding: 6px 12px;
        height: 28px;
        font-size: 13px;
        font-weight: 600;
        color: #0284C7;
        background-color: #E0F2FE;
        border: 1px solid #BAE6FD;
        border-radius: 9999px;
        margin-left: 10px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
        background-color: transparent;
        border-bottom: 2px solid #E2E8F0;
        padding-bottom: 2px;
    }

    .stTabs [data-baseweb="tab"] {
        height: 48px;
        border: none;
        background-color: transparent;
        color: #64748B;
        font-weight: 600;
        font-size: 16px;
        padding: 0 4px;
    }

    .stTabs [aria-selected="true"] {
        background-color: transparent !important;
        color: #2563EB !important;
        border-bottom: 3px solid #2563EB;
        margin-bottom: -2px; /* Overlap border */
    }
    
    /* Inputs */
    .stTextInput > div > div > input {
        border-radius: 10px;
        border-color: #E2E8F0;
        padding: 10px 12px;
    }
    .stTextInput > div > div > input:focus {
        border-color: #3B82F6;
        box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
    }
</style>
""", unsafe_allow_html=True)

st.title("📘 英语个性化跟读工具 Pro")

# Sidebar
with st.sidebar:
    st.header("⚙️ 设置 (Settings)")
    
    # Mode Selection
    mode = st.radio("选择模式 (Mode)", ["✨ AI 生成 (Generate)", "📥 自定义导入 (Import)", "📚 我的书库 (Library)"])
    st.markdown("---")

    # API Key Handling (Hidden from UI)
    api_key = os.getenv("DASHSCOPE_API_KEY")
    
    with st.expander("🛠️ 评测设置 (Evaluation Settings)", expanded=False):
        st.caption("默认使用本地引擎 (Local)。如需高级评测 (Aliyun)，请配置以下信息。")
        aliyun_app_key = st.text_input("Aliyun AppKey", value=os.getenv("ALIYUN_APP_KEY", ""), type="password")
        aliyun_ak_id = st.text_input("AccessKey ID", value=os.getenv("ALIYUN_AK_ID", ""), type="password")
        aliyun_ak_secret = st.text_input("AccessKey Secret", value=os.getenv("ALIYUN_AK_SECRET", ""), type="password")
        
    # Initialize modules
    base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    # Pass api_key explicitly (loaded from env)
    text_gen = TextGenerator(api_key=api_key, base_url=base_url)
    audio_gen = AudioGenerator(api_key=api_key)
    # Pass Aliyun credentials explicitly
    evaluator = Evaluator(app_key=aliyun_app_key, ak_id=aliyun_ak_id, ak_secret=aliyun_ak_secret)

    # Mode specific settings
    if mode == "✨ AI 生成 (Generate)":
        stage = st.selectbox("选择学段 (Stage)", ["小学 (Primary)", "初中 (Junior)", "高中 (Senior)", "成人 (Adult)"])
        grade_options = []
        if stage == "小学 (Primary)":
            grade_options = [f"一年级 (Grade 1)", f"二年级 (Grade 2)", f"三年级 (Grade 3)", f"四年级 (Grade 4)", f"五年级 (Grade 5)", f"六年级 (Grade 6)"]
        elif stage == "初中 (Junior)":
            grade_options = [f"初一 (Grade 7)", f"初二 (Grade 8)", f"初三 (Grade 9)"]
        elif stage == "高中 (Senior)":
            grade_options = [f"高一 (Grade 10)", f"高二 (Grade 11)", f"高三 (Grade 12)"]
        else:
            grade_options = ["通用 (General)", "商务 (Business)", "学术 (Academic)"]
            
        specific_grade = st.selectbox("选择具体年级 (Grade)", grade_options)
        full_grade_info = f"{stage} - {specific_grade}"
        
        st.subheader("💡 兴趣主题 (Topic)")
        interest = st.text_input("输入主题 (e.g. Space, Cars)", value="Space")

# Session State
if 'generated_text' not in st.session_state:
    st.session_state.generated_text = None
if 'audio_path' not in st.session_state:
    st.session_state.audio_path = None
if 'evaluation_result' not in st.session_state:
    st.session_state.evaluation_result = None
if 'active_tab' not in st.session_state:
    st.session_state.active_tab = "📖 阅读 (Read)" # Default tab

# Helper to process imported text
def process_imported_text(text, title="Custom Content"):
    try:
        sentences = nltk.sent_tokenize(text)
        formatted_content = "\n\n".join(sentences)
    except Exception:
        formatted_content = text
    except LookupError: # Fallback if punkt missing
        formatted_content = text

    # Simple keyword extraction (placeholder or simple split)
    keywords = list(set([w for w in text.split() if len(w) > 6]))[:5]
    return {
        "title": title,
        "content": formatted_content,
        "keywords": keywords,
        "chinese_translation": [] # Placeholder
    }

# Main Content
if mode == "✨ AI 生成 (Generate)":
    st.header("1. 定制文本生成 (Text Generation)")
    if st.button("✨ 生成跟读文本 (Generate Text)", use_container_width=True):
        if not api_key:
            st.error("⚠️ 未找到 API Key。请确保 .env 文件中已配置 DASHSCOPE_API_KEY。")
        else:
            with st.spinner("正在生成..."):
                try:
                    data = text_gen.generate_text(full_grade_info, interest)
                    st.session_state.generated_text = data
                    st.session_state.audio_path = None
                    st.session_state.evaluation_result = None
                    st.rerun()
                except Exception as e:
                    st.error(f"生成失败: {e}")

elif mode == "📥 自定义导入 (Import)":
    st.header("1. 自定义导入 (Custom Import)")
    
    import_type = st.radio("导入方式", ["📝 文本输入 (Paste Text)", "📂 文件上传 (Upload File)"], horizontal=True)
    
    imported_content = ""
    imported_title = "My Custom Text"
    
    if import_type == "📝 文本输入 (Paste Text)":
        imported_content = st.text_area("在此粘贴文本", height=200, placeholder="Paste your English text here...")
    else:
        uploaded_file = st.file_uploader("上传 TXT 文件", type=['txt'])
        if uploaded_file:
            imported_content = uploaded_file.read().decode("utf-8")
            imported_title = uploaded_file.name
    
    if st.button("🚀 处理文本 (Process Text)", use_container_width=True):
        if imported_content.strip():
            data = process_imported_text(imported_content, imported_title)
            st.session_state.generated_text = data
            st.session_state.audio_path = None
            st.session_state.evaluation_result = None
            st.success("文本已导入！")
            st.rerun()
        else:
            st.warning("请输入或上传文本")

elif mode == "📚 我的书库 (Library)":
    st.header("📚 我的书库 (Library)")
    lib = load_library()
    if not lib:
        st.info("书库为空，请先生成或导入文本。")
    else:
        # Filter by tag
        all_tags = set()
        for item in lib:
            all_tags.update(item.get('tags', []))
        
        selected_tag = st.selectbox("按标签筛选 (Filter by Tag)", ["All"] + list(all_tags))
        
        filtered_lib = lib
        if selected_tag != "All":
            filtered_lib = [i for i in lib if selected_tag in i.get('tags', [])]
            
        # Display list
        for idx, item in enumerate(filtered_lib):
            with st.expander(f"{item['title']} (Tags: {', '.join(item.get('tags', []))})"):
                st.write(item['content'][:200] + "...")
                col_load, col_del = st.columns([1, 5])
                with col_load:
                    if st.button("Load", key=f"load_{idx}"):
                        st.session_state.generated_text = item
                        st.session_state.audio_path = None
                        st.session_state.evaluation_result = None
                        st.rerun()

# Display Content & Audio (Common for all modes if data loaded)
if st.session_state.generated_text:
    data = st.session_state.generated_text
    
    # Save & Tags
    with st.container():
        col_title, col_save = st.columns([3, 1])
        with col_title:
             st.markdown(f"## {data['title']}")
        with col_save:
             current_tags = data.get('tags', [])
             new_tags = st.multiselect("🏷️ 标签 (Tags)", 
                                      ["Automotive", "Numerology", "Workplace", "General", "Exam", "Fun"], 
                                      default=current_tags)
             if st.button("💾 保存 (Save)", use_container_width=True):
                 data['tags'] = new_tags
                 save_to_library(data)
                 st.success("已保存！")

    # Tabs for organization
    tab1, tab2, tab3 = st.tabs(["📖 阅读 (Read)", "🎧 跟读 (Shadowing)", "📊 评测 (Evaluate)"])

    with tab1:
        # Display Card
        st.markdown(f"""
        <div class="content-card">
            <div style="margin-bottom: 10px;">
                <span style="color: #909399; font-size: 14px;">🔑 Keywords: {', '.join(data.get('keywords', []))}</span>
            </div>
            <div style="margin-bottom: 20px;">
                <span class="el-tag">Level: {full_grade_info if mode == "✨ AI 生成 (Generate)" else "Custom"}</span>
            </div>
            <div style="font-size: 16px; line-height: 1.8; color: #606266; text-align: justify;">
                {data['content'].replace(chr(10), '<br>')}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Educational Analysis Section
        if data.get('analysis'):
            analysis = data['analysis']
            
            # Helper for displaying section
            def display_section(title, icon, content_list, type="list"):
                if not content_list: return
                st.markdown(f"#### {icon} {title}")
                html = ""
                if type == "vocab":
                    for item in content_list:
                        html += f"<p><b>{item.get('word', '')}</b> <i>({item.get('pos', '')})</i>: {item.get('meaning', '')}</p>"
                elif type == "grammar":
                    for item in content_list:
                        html += f"<p><b>{item.get('point', '')}</b><br><span style='color:#666'>Eg: {item.get('example', '')}</span></p>"
                elif type == "expr":
                    for item in content_list:
                        html += f"<p><b>{item.get('phrase', '')}</b> (≈ {item.get('replacement', '')})<br><span style='color:#666'>Scenario: {item.get('scenario', '')}</span></p>"
                elif type == "test":
                    for i, item in enumerate(content_list):
                        html += f"<p><b>{i+1}. {item.get('question', '')}</b><br>"
                        opts = item.get('options', [])
                        html += f"A) {opts[0]} &nbsp; B) {opts[1]} &nbsp; C) {opts[2]} &nbsp; D) {opts[3]}<br>"
                        html += f"<details><summary>View Answer</summary>Answer: {item.get('answer', '')}<br><i>{item.get('explanation', '')}</i></details></p>"
                
                st.markdown(f"""
                <div class="content-card" style="background-color: #f9f9f9; padding: 15px; margin-bottom: 15px; border-left: 4px solid #409EFF;">
                    {html}
                </div>
                """, unsafe_allow_html=True)

            st.markdown("### 📚 学习重点 (Key Points)")
            
            # 1. Vocabulary
            if isinstance(analysis, dict): # Ensure it's the new structured format
                display_section("词汇与短语 (Vocabulary & Phrases)", "📖", analysis.get('vocabulary', []), "vocab")
                display_section("语法要点 (Grammar Points)", "🧩", analysis.get('grammar', []), "grammar")
                display_section("地道表达 (Expressions)", "💬", analysis.get('expressions', []), "expr")
                display_section("小测验 (Easy Test)", "📝", analysis.get('easy_test', []), "test")
            else:
                # Fallback for old string format
                st.markdown(f"""
                <div class="content-card" style="background-color: #f9f9f9; margin-top: 10px;">
                    {analysis.replace(chr(10), '<br>')}
                </div>
                """, unsafe_allow_html=True)

    with tab2:
        # Audio Section
        st.header("2. 标准音频跟读 (Audio Shadowing)")
        
        col1, col2 = st.columns(2)
        with col1:
            speed = st.select_slider(
                "语速 (Speed)", 
                options=[0.85, 1.0, 1.15], 
                value=1.0,
                format_func=lambda x: "正常 (Normal)" if x == 1.0 else str(x)
            )
        with col2:
            source_options = ["Qwen TTS (DashScope)", "Edge TTS (Free)"]
            # Default to Qwen if key exists
            idx = 0 if api_key else 1
            tts_source = st.radio("语音引擎 (Engine)", source_options, index=idx)
        
        # 1. Full Article Audio
        st.subheader("🔊 全文跟读 (Full Text)")
        if st.button("▶️ 生成/播放全文音频", use_container_width=True):
            with st.spinner("正在合成音频..."):
                src_code = "qwen" if "Qwen" in tts_source else "edge"
                audio_path = audio_gen.generate_audio(data['content'], rate=speed, source=src_code)
                st.session_state.audio_path = audio_path
                st.rerun()
                
        if st.session_state.audio_path:
            st.audio(st.session_state.audio_path)
            with open(st.session_state.audio_path, "rb") as f:
                st.download_button("📥 下载音频", f, file_name="shadowing.mp3", mime="audio/mpeg")

        # 2. Sentence-by-Sentence Shadowing (New Feature)
        st.markdown("---")
        st.subheader("🎤 逐句精练 (Sentence Shadowing)")
        
        # Get sentences from analysis or fallback to simple split
        shadow_sentences = []
        if data.get('analysis') and isinstance(data['analysis'], dict) and data['analysis'].get('shadowing_sentences'):
             shadow_sentences = data['analysis']['shadowing_sentences']
        else:
             # Fallback: Split content into sentences and take first 5
             try:
                 shadow_sentences = nltk.sent_tokenize(data['content'])[:5]
             except:
                 shadow_sentences = data['content'].split('.')[:5]
        
        if not shadow_sentences:
            st.info("No sentences available for shadowing.")
        else:
            # Selection
            selected_sent_idx = st.selectbox("选择句子 (Select Sentence)", range(len(shadow_sentences)), format_func=lambda x: f"Sentence {x+1}")
            current_sent = shadow_sentences[selected_sent_idx]
            
            st.markdown(f"""
            <div style="font-size: 20px; font-weight: 500; color: #2c3e50; padding: 20px; background: #f8f9fa; border-radius: 10px; border-left: 5px solid #3B82F6; margin-bottom: 20px;">
                {current_sent}
            </div>
            """, unsafe_allow_html=True)
            
            c_play, c_rec = st.columns([1, 1])
            
            with c_play:
                if st.button("🎧 播放标准音 (Play Standard)", key=f"play_sent_{selected_sent_idx}"):
                     src_code = "qwen" if "Qwen" in tts_source else "edge"
                     # Generate temporary audio for this sentence
                     sent_audio = audio_gen.generate_audio(current_sent, filename=f"sent_{selected_sent_idx}.mp3", rate=speed, source=src_code)
                     st.audio(sent_audio, autoplay=True)
            
            with c_rec:
                # Use audio_input for recording
                sent_audio_input = st.audio_input("🔴 录音跟读 (Record)", key=f"rec_sent_{selected_sent_idx}")
                
            if sent_audio_input:
                if st.button("📝 立即评测 (Evaluate Now)", key=f"eval_sent_{selected_sent_idx}", type="primary"):
                    with st.spinner("Analyzing pronunciation..."):
                         # Save user audio
                         user_sent_path = f"user_sent_{selected_sent_idx}.wav"
                         with open(user_sent_path, "wb") as f:
                             f.write(sent_audio_input.read())
                         
                         # Convert to WAV 16k mono (standard requirement)
                         try:
                             from pydub import AudioSegment
                             sound = AudioSegment.from_file(user_sent_path)
                             sound = sound.set_frame_rate(16000).set_channels(1)
                             sound.export(user_sent_path, format="wav")
                         except Exception as e:
                             st.error(f"Audio conversion error: {e}")

                         # Evaluate
                         eval_method = "aliyun" if (aliyun_app_key and aliyun_ak_id) else "local"
                         sent_res = evaluator.evaluate_audio(user_sent_path, current_sent, method=eval_method)
                         
                         # Display Result
                         st.success(f"Score: {sent_res.get('total_score', 0)}")
                         st.info(sent_res.get('feedback', ''))
                         
                         # Highlighted Result
                         hl_html = highlight_text_html(current_sent, sent_res.get('error_words', []))
                         st.markdown(f"""
                         <div style="margin-top: 10px; padding: 15px; background: white; border: 1px solid #eee; border-radius: 8px;">
                            <strong>Feedback:</strong><br>
                            {hl_html}
                         </div>
                         """, unsafe_allow_html=True)


    with tab3:
        # Evaluation Section (Full Text)
        st.header("3. 全文评测 (Full Text Evaluation)")
        audio_input = st.audio_input("点击录音 (Record)", key="full_rec")
        
        if audio_input:
            if st.button("📝 开始评测 (Evaluate)", use_container_width=True):
                with st.spinner("正在评测..."):
                    with open("user_recording.wav", "wb") as f:
                        f.write(audio_input.read())
                    
                    # Convert to WAV using pydub to ensure compatibility
                    try:
                        from pydub import AudioSegment
                        sound = AudioSegment.from_file("user_recording.wav")
                        sound = sound.set_frame_rate(16000).set_channels(1)
                        sound.export("user_recording.wav", format="wav")
                    except Exception as e:
                        print(f"Audio conversion warning: {e}")

                    # Determine method based on keys or user preference
                    eval_method = "aliyun" if (aliyun_app_key and aliyun_ak_id) else "local"
                    
                    res = evaluator.evaluate_audio("user_recording.wav", data['content'], method=eval_method)
                    st.session_state.evaluation_result = res
                    st.rerun()

        if st.session_state.evaluation_result:
            res = st.session_state.evaluation_result
            st.markdown("---")
            
            # Scores
            col_s1, col_s2, col_s3 = st.columns(3)
            col_s1.metric("总分 (Total)", res.get('total_score', 0))
            col_s2.metric("流利度 (Fluency)", res.get('fluency_score', 0))
            col_s3.metric("完整度 (Integrity)", res.get('integrity_score', 0))
            
            st.info(f"💡 {res.get('feedback', '')}")
            
            # Highlighted Result for Full Text
            st.markdown("### 🔍 详细反馈 (Detailed Feedback)")
            st.caption("🔴 红色高亮单词表示发音需改进 (Red highlights indicate pronunciation issues).")
            
            hl_html = highlight_text_html(data['content'], res.get('error_words', []))
            st.markdown(f"""
            <div class="content-card" style="font-size: 16px; line-height: 2.0;">
                {hl_html.replace(chr(10), '<br>')}
            </div>
            """, unsafe_allow_html=True)
