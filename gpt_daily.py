# streamlit_app.py

import streamlit as st
import pandas as pd
from PIL import Image
from datetime import date
import openai
import base64
import json

# 1) 페이지 설정
st.set_page_config(page_title="공사일보 자동화 프로그램", layout="wide")
st.title("📋 공사일보 자동화 프로그램 (v3.0)")

# 2) 사이드바: OpenAI API Key 입력
st.sidebar.title("🔑 OpenAI API Settings")
api_key_input = st.sidebar.text_input("OpenAI API Key", type="password")
if api_key_input:
    openai.api_key = api_key_input
else:
    st.sidebar.warning("API Key를 입력해주세요.")

# 3) 상단 여백 및 고정 푸터
st.markdown("<div style='height: 60px;'></div>", unsafe_allow_html=True)
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

# 4) GPT-4o OCR 호출 함수
def call_gpt_ocr(image_bytes: bytes):
    img_b64 = base64.b64encode(image_bytes).decode()
    system_prompt = (
        "당신은 건설현장 ‘공사일보’ 전용 OCR 전문가입니다.\n"
        "– 이미지 상단의 공종명, 업체명, 날짜를 추출하고, "
        "No·직종·성명·작업구역·작업내용·비고를 JSON 배열로 반환하세요.\n"
        "– 필드가 비어 있으면 빈 문자열(\"\")로 표기하세요.\n"
        "– 작업구역이 다르면 같은 작업내용이라도 별도 행으로 분리하세요.\n"
        "– 괄호·화살표 그룹핑은 연결된 모든 행에 텍스트를 복제하세요."
    )
    user_prompt = f"```image-base64\n{img_b64}\n```"
    resp = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt}
        ],
        temperature=0
    )
    content = resp.choices[0].message.content.strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        st.error("OCR 결과를 파싱할 수 없습니다.")
        return []

# 5) 세션 상태 초기화
if "initialized" not in st.session_state:
    st.session_state.initialized   = False
    st.session_state.images        = []
    st.session_state.previews      = []
    st.session_state.current       = 0
    st.session_state.data          = []
    st.session_state.completed     = False
    st.session_state.default_date  = date.today()

# 6) 파일 업로드
uploaded_files = st.file_uploader(
    "이미지 업로드 (png, jpg, jpeg)", type=["png","jpg","jpeg"],
    accept_multiple_files=True
)

# 7) 초기 OCR 및 데이터 매핑 (업로드 직후 단 한 번 실행)
if uploaded_files and not st.session_state.initialized and api_key_input:
    st.session_state.initialized = True
    st.session_state.images      = uploaded_files
    st.session_state.previews    = [Image.open(f) for f in uploaded_files]
    ocr_results = []
    # 각 이미지에 대해 GPT-4o 호출
    for f in uploaded_files:
        img_bytes = f.read()
        ocr_json = call_gpt_ocr(img_bytes)
        ocr_results.append(ocr_json)
    # session_state.data 초기화
    st.session_state.data = []
    for results in ocr_results:
        # 기본 날짜는 default_date, 기타 필드는 OCR 결과 첫 페이지 기준 매핑
        if results:
            total_person = sum(int(rec.get("인원",0)) for rec in results)
            equipment_set = {rec.get("장비","") for rec in results if rec.get("장비")}
            content_combined = "\n".join(rec.get("작업내용","") for rec in results)
            st.session_state.data.append({
                "날짜": st.session_state.default_date,
                "공종": results[0].get("공종",""),
                "인원": total_person,
                "장비": ", ".join(equipment_set),
                "내용": content_combined
            })
        else:
            st.session_state.data.append({
                "날짜": st.session_state.default_date,
                "공종": "", "인원": 0, "장비": "", "내용": ""
            })

# 8) 썸네일 및 삭제 기능
if st.session_state.previews:
    st.markdown("### 🖼 업로드한 파일들")
    delete_idx = None
    cols = st.columns(len(st.session_state.previews))
    for i, col in enumerate(cols):
        with col:
            st.image(st.session_state.previews[i], caption=f"Page {i+1}", width=100)
            if st.button("❌", key=f"delete_{i}"):
                delete_idx = i
    if delete_idx is not None:
        del st.session_state.images[delete_idx]
        del st.session_state.previews[delete_idx]
        del st.session_state.data[delete_idx]
        st.session_state.current = max(0, st.session_state.current-1)
        st.session_state.initialized = False
        st.experimental_rerun()

# 9) 공사일보 입력폼
if st.session_state.previews and st.session_state.current < len(st.session_state.previews):
    idx = st.session_state.current
    total = len(st.session_state.previews)
    col1, col2 = st.columns([1,2])

    with col1:
        st.image(st.session_state.previews[idx],
                 caption=f"이미지 {idx+1} / {total}", use_container_width=True)
    with col2:
        st.subheader("📝 공사일보 입력")
        saved = st.session_state.data[idx]
        with st.form(key=f"entry_form_{idx}"):
            날짜 = st.date_input("날짜", value=saved["날짜"])
            공종명 = st.text_input("공종명", value=saved["공종"])
            col_in, col_eq = st.columns(2)
            with col_in:
                인원 = st.number_input("인원", min_value=0, step=1, value=saved["인원"])
            with col_eq:
                장비 = st.text_input("장비", value=saved["장비"])
            내용 = st.text_area("공사일보 내용", value=saved["내용"], height=200)

            action = st.radio("동작 선택", ["이전", "저장 & 다음"], index=1)
            submitted = st.form_submit_button("확인")
            if submitted:
                st.session_state.data[idx] = {
                    "날짜": 날짜,
                    "공종": 공종명,
                    "인원": 인원,
                    "장비": 장비,
                    "내용": 내용
                }
                if idx == 0:
                    st.session_state.default_date = 날짜
                if action == "이전":
                    st.session_state.current = max(0, idx-1)
                else:
                    if idx < total-1:
                        st.session_state.current = idx+1
                    else:
                        st.session_state.completed = True
                st.experimental_rerun()

# 10) 결과 취합 및 표시
if st.session_state.previews:
    formatted = []
    for entry in st.session_state.data:
        if entry["공종"] or entry["내용"]:
            line = f"{entry['공종']} ({entry['인원']} / 장비: {entry['장비']})\n{entry['내용']}"
            formatted.append(line)
    total_person = sum(e["인원"] for e in st.session_state.data)
    equipment_list = [e["장비"] for e in st.session_state.data if e["장비"]]
    equipment_line = ", ".join(equipment_list)
    output_text = (
        f"날짜: {st.session_state.default_date}\n\n"
        + "\n\n".join(formatted)
        + f"\n\n총인원 : {total_person}"
        + f"\n\n장비: {equipment_line}"
    )

    st.markdown("### 📄 공사일보 취합 (수정 가능)")
    st.text_area("복사 가능한 최종 텍스트", value=output_text, height=400)

    st.markdown("### 📊 전체 공사일보 결과")
    df = pd.DataFrame(st.session_state.data)
    st.dataframe(df)
