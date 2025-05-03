import os
import io
import base64
import streamlit as st
import pandas as pd
import openai
from PIL import Image
from datetime import date

# --- Streamlit 페이지 설정 ---
st.set_page_config(page_title="공사일보 자동화 프로그램", layout="wide")
st.title("📋 공사일보 자동화 프로그램 (v3.0)")
# 여백 추가
st.markdown("<div style='height: 60px;'></div>", unsafe_allow_html=True)
# 고정 푸터
footer_html = """
<style>
.footer {
    position: fixed;
    left: 0;
    bottom: 0;
    width: 100%;
    background-color: #fafafa;
    color: #888;
    text-align: center;
    padding: 10px 0;
    font-size: 13px;
    border-top: 1px solid #eaeaea;
    z-index: 100;
}
</style>
<div class="footer">
    © 2025 공사일보 자동화. Designed & Developed by MinWonGyu.
</div>
"""
st.markdown(footer_html, unsafe_allow_html=True)

# --- OpenAI API 키 설정 ---
openai.api_key = (
    st.secrets.get("openai", {}).get("api_key")
    or os.getenv("OPENAI_API_KEY")
)

# --- GPT 기반 OCR 추출 함수 정의 ---
def gpt_extract_report(pil_img: Image.Image) -> str:
    # 이미지 -> base64 인코딩
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    img_b64 = base64.b64encode(buf.getvalue()).decode()

    # System & User 프롬프트
    system_prompt = """
당신은 건설현장 “공사일보” 양식 전용 OCR 전문가입니다.
– 입력된 이미지를 보고, 문서 상단의 공종명, 업체명, 날짜를 정확히 추출하세요.  
– 이어서 No·직종·성명·작업구역·작업내용·비고 6개 필드를 표 형식으로 반환하세요.  
– 절대 다른 설명이나 부가 텍스트를 추가하지 말고, 지정한 형식 그대로만 응답해야 합니다.  
– 필드가 비어 있으면 빈 문자열("")로 표기하세요.  
– **추가 규칙**: 작업내용이 같더라도 작업구역이 다르면 반드시 별도의 행으로 분리하여 입력하세요.  
– **괄호(⎡⎤)·화살표(↓)** 표시는 연결된 모든 행에 앞서 쓰인 텍스트를 복제하라는 의미입니다.
""".strip()
    user_prompt = f"""```image-base64
{img_b64}
```"""

    resp = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        temperature=0,
    )
    return resp.choices[0].message.content

# --- 세션 상태 초기화 ---
if "images" not in st.session_state:
    st.session_state.images = []
if "previews" not in st.session_state:
    st.session_state.previews = []
if "current" not in st.session_state:
    st.session_state.current = 0
if "data" not in st.session_state:
    st.session_state.data = []
if "completed" not in st.session_state:
    st.session_state.completed = False
if "default_date" not in st.session_state:
    st.session_state.default_date = date.today()
if "initialized" not in st.session_state:
    st.session_state.initialized = False

# --- 파일 업로드 ---
st.markdown(
    '파일 첨부하기 (png, jpg, jpeg 등) ‼️PDF 업로드 불가‼️ *PDF->이미지변환 사이트주소 [https://www.ilovepdf.com/ko/pdf_to_jpg](https://www.ilovepdf.com/ko/pdf_to_jpg)*'
)
uploaded_files = st.file_uploader(
    "",
    type=["png", "jpg", "jpeg"],
    accept_multiple_files=True
)

if uploaded_files and not st.session_state.initialized:
    st.session_state.initialized = True
    st.session_state.images = uploaded_files
    st.session_state.previews = [Image.open(f) for f in uploaded_files]
    st.session_state.data = [{"날짜": "", "공종": "", "인원": 0, "장비": "", "내용": ""} for _ in uploaded_files]
    st.session_state.current = 0
    st.session_state.completed = False

# --- 업로드된 이미지 썸네일 & 삭제 기능 ---
if st.session_state.previews:
    st.markdown("### 🖼 업로드한 파일들")
    delete_idx = None
    thumbs = st.columns(len(st.session_state.previews))
    for i, col in enumerate(thumbs):
        with col:
            st.image(st.session_state.previews[i], caption=f"Page {i+1}", width=100)
            if st.button("❌", key=f"delete_{i}"):
                delete_idx = i
    if delete_idx is not None:
        del st.session_state.images[delete_idx]
        del st.session_state.previews[delete_idx]
        del st.session_state.data[delete_idx]
        if st.session_state.current >= len(st.session_state.previews):
            st.session_state.current = max(0, len(st.session_state.previews) - 1)
        st.rerun()

# --- 공사일보 입력폼 & GPT OCR 버튼 ---
if st.session_state.previews and st.session_state.current < len(st.session_state.previews):
    idx = st.session_state.current
    total = len(st.session_state.previews)
    col1, col2 = st.columns([1, 2])

    with col1:
        st.image(st.session_state.previews[idx], caption=f"이미지 {idx+1} / {total}", use_container_width=True)

    with col2:
        st.subheader("📝 공사일보 입력")
        saved_data = st.session_state.data[idx]
        # GPT OCR 실행 버튼
        if st.button("🤖 GPT OCR 실행", use_container_width=True):
            raw = gpt_extract_report(st.session_state.previews[idx])
            st.markdown("#### GPT 추출 결과")
            st.markdown(raw)
        with st.form(key=f"entry_form_{idx}"):
            날짜 = st.date_input("날짜", value=saved_data["날짜"] or st.session_state.default_date)
            공종 = st.text_input("공종명", value=saved_data["공종"])
            col_in, col_equ = st.columns(2)
            with col_in:
                인원 = st.number_input("인원", min_value=0, step=1, value=saved_data["인원"])
            with col_equ:
                장비 = st.text_input("장비", value=saved_data.get("장비", ""))
            내용 = st.text_area("공사일보 내용", value=saved_data["내용"], height=200)
            action = st.radio("동작 선택", options=["이전", "저장 & 다음"], index=1)
            submitted = st.form_submit_button("확인")
            if submitted:
                st.session_state.data[idx] = {
                    "날짜": 날짜,
                    "공종": 공종,
                    "인원": 인원,
                    "장비": 장비,
                    "내용": 내용
                }
                if idx == 0:
                    st.session_state.default_date = 날짜
                if action == "이전":
                    st.session_state.current = max(0, idx - 1)
                else:
                    if idx < total - 1:
                        st.session_state.current = idx + 1
                    else:
                        st.session_state.completed = True
                st.rerun()

# --- 취합 및 결과 표시 ---
if st.session_state.previews:
    formatted_lines = []
    for entry in st.session_state.data:
        if entry["공종"] or entry["내용"]:
            line = f"{entry['공종']} ({entry['인원']} / 장비: {entry['장비']})\n{entry['내용']}"
            formatted_lines.append(line)
    total_personnel = sum(entry["인원"] for entry in st.session_state.data)
    equipment_entries = [entry["장비"] for entry in st.session_state.data if entry["장비"]]
    equipment_line = ", ".join(equipment_entries)
    output_text = (
        f"날짜: {str(st.session_state.default_date)}\n\n"
        + "\n\n".join(formatted_lines)
        + f"\n\n총인원 : {total_personnel}"
        + f"\n\n장비: {equipment_line}"
    )
    st.markdown("### 📄 공사일보 취합 (수정가능)")
    st.text_area("복사 가능한 최종 텍스트", value=output_text, height=400)

    st.markdown("### 📊 전체 공사일보 결과")
    df = pd.DataFrame(st.session_state.data)
    st.dataframe(df)
