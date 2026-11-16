import streamlit as st
import os
import time
import shutil
import secrets
from datetime import datetime

# --- Configuration ---
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp_data")
EXPIRATION_HOURS = 12   # 傳送後 12 小時自動刪除
REFRESH_SECONDS = 10    # 收件匣自動刷新間隔

os.makedirs(DATA_DIR, exist_ok=True)


@st.cache_data(ttl=600, show_spinner=False)
def cleanup_old_data():
    """每 10 分鐘最多掃一次，刪除過期資料。"""
    now = time.time()
    for name in os.listdir(DATA_DIR):
        path = os.path.join(DATA_DIR, name)
        if os.path.isdir(path) and now - os.path.getmtime(path) > EXPIRATION_HOURS * 3600:
            shutil.rmtree(path, ignore_errors=True)


def unique_path(folder: str, name: str) -> str:
    """同名檔案自動加 _1、_2，避免互相覆蓋。"""
    name = os.path.basename(name) or "file"
    stem, ext = os.path.splitext(name)
    path, i = os.path.join(folder, name), 1
    while os.path.exists(path):
        path = os.path.join(folder, f"{stem}_{i}{ext}")
        i += 1
    return path


def read_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


st.set_page_config(page_title="資料傳輸助手", page_icon="📦", layout="centered")
st.title("📦 資料傳輸助手")
st.caption(f"傳送的內容所有人都看得到，{EXPIRATION_HOURS} 小時後自動刪除。")

tab_send, tab_inbox = st.tabs(["📤 傳送", "📥 接收"])

# --- 傳送 ---
with tab_send:
    with st.form("send_form", clear_on_submit=True):
        text_input = st.text_area("貼上文字：", height=150)
        uploaded_files = st.file_uploader("上傳檔案：", accept_multiple_files=True)
        submitted = st.form_submit_button("🚀 傳送", type="primary")

    if submitted:
        if not text_input and not uploaded_files:
            st.warning("請輸入文字或上傳檔案！")
        else:
            t_id = datetime.now().strftime("%Y%m%d-%H%M%S-") + secrets.token_hex(3)
            # 先寫到暫存資料夾，寫完再改名，收件匣不會看到寫到一半的包裹
            tmp_dir = os.path.join(DATA_DIR, f".tmp-{t_id}")
            os.makedirs(tmp_dir)

            if text_input:
                with open(os.path.join(tmp_dir, "text_data.txt"), "w", encoding="utf-8") as f:
                    f.write(text_input)

            if uploaded_files:
                files_dir = os.path.join(tmp_dir, "files")
                os.makedirs(files_dir)
                for file in uploaded_files:
                    with open(unique_path(files_dir, file.name), "wb") as f:
                        f.write(file.getbuffer())

            os.rename(tmp_dir, os.path.join(DATA_DIR, t_id))
            st.success("✅ 傳送成功！到「接收」分頁即可下載。")


# --- 接收（每 REFRESH_SECONDS 秒自動刷新，只重跑這一區）---
@st.fragment(run_every=REFRESH_SECONDS)
def inbox():
    cleanup_old_data()

    transfers = sorted(
        (
            d for d in os.listdir(DATA_DIR)
            if not d.startswith(".") and os.path.isdir(os.path.join(DATA_DIR, d))
        ),
        reverse=True,
    )

    if not transfers:
        st.info("📭 目前沒有資料。")
        return

    for t_id in transfers:
        t_path = os.path.join(DATA_DIR, t_id)
        try:
            ts = datetime.strptime(t_id[:15], "%Y%m%d-%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            ts = "未知時間"

        with st.expander(f"📦 {ts}", expanded=True):
            text_path = os.path.join(t_path, "text_data.txt")
            if os.path.exists(text_path):
                with open(text_path, encoding="utf-8") as f:
                    st.code(f.read(), language="text", wrap_lines=True)

            files_dir = os.path.join(t_path, "files")
            if os.path.isdir(files_dir):
                for file_name in sorted(os.listdir(files_dir)):
                    file_path = os.path.join(files_dir, file_name)
                    size_mb = os.path.getsize(file_path) / 1024 / 1024
                    st.download_button(
                        label=f"⬇️ {file_name}（{size_mb:.1f} MB）",
                        data=lambda p=file_path: read_bytes(p),  # 按下才讀檔
                        file_name=file_name,
                        mime="application/octet-stream",
                        key=f"dl_{t_id}_{file_name}",
                    )

            if st.button("🗑️ 刪除", key=f"del_{t_id}"):
                shutil.rmtree(t_path, ignore_errors=True)
                st.rerun()


with tab_inbox:
    inbox()
