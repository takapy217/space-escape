# app.py — 修正版（動画を確実に切り替え、▶次へ/Next）
import streamlit as st
import json, re, base64, time
from pathlib import Path
from typing import Union, Dict, Any

# -----------------------------
# ページ設定
# -----------------------------
st.set_page_config(page_title="宇宙船脱出 / Spaceship Escape", layout="centered")

# -----------------------------
# CSS調整：動画・画像を縦に並べ、余計な記号を抑止
# -----------------------------
st.markdown("""
<style>
video, .stVideo video, .stImage img{
  display:block !important;
  width:100% !important;
  height:auto !important;
  margin:0 0 12px 0 !important;
  background:#000;
}
.stImage img{ border-radius:0 !important; }
/* 謎の記号や空段落の除去 */
video + p:empty,
video + p:has(br:only-child),
.stImage + p:empty,
.stImage + p:has(br:only-child){ display:none !important; }
.stMarkdown p{
  margin-top:0.35rem !important;
  margin-bottom:0.35rem !important;
}
@media (max-width:480px){
  video, .stVideo video, .stImage img{ margin-bottom:8px !important; }
}
</style>
""", unsafe_allow_html=True)

# -----------------------------
# 物語データ
# -----------------------------
def load_story(lang: str) -> Dict[str, Any]:
    p = Path("story_space_adv_en.json" if lang == "en" else "story_space_adv_jp.json")
    if not p.exists():
        return {
            "intro_text": "JSON not found. Please prepare story file.",
            "chapters": {
                "1": {
                    "text": "Dummy chapter. Please prepare JSON.",
                    "video": "assets/sample.mp4",
                    "choices": [
                        {"text": "▶次へ/Next", "result": {"text": "End", "next": "1", "lp": 0}, "correct": True}
                    ]
                }
            }
        }
    return json.loads(p.read_text(encoding="utf-8"))

# -----------------------------
# セッション管理
# -----------------------------
def init_session():
    defaults = {
        "chapter": "start",
        "lp": 90,
        "selected": None,
        "show_result": False,
        "player_name": "",
        "lang": "ja",
        "lp_updated": False,
    }
    for k,v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

def personalize(text: str) -> str:
    return re.sub(r"{player_name}", st.session_state.get("player_name","あなた"), text or "")

def ensure_asset(path: str) -> Path:
    p = Path(path)
    if not (str(p).startswith("assets/") or str(p).startswith("./assets/")):
        p = Path("assets") / p
    return p

# -----------------------------
# 動画レンダリング（必ずVIDEO_SLOTに上書き）
# -----------------------------
VIDEO_SLOT = st.empty()

def render_video(path: str, *, autoplay=True, muted=True, loop=False, controls=False):
    p = ensure_asset(path)
    if not p.exists():
        st.warning(f"Video not found: {p}")
        return
    b64 = base64.b64encode(p.read_bytes()).decode("utf-8")

    attrs = []
    if autoplay: attrs.append("autoplay")
    if muted:    attrs.append("muted")
    if loop:     attrs.append("loop")
    if controls: attrs.append("controls")
    attrs.extend(["playsinline","webkit-playsinline","x5-playsinline"])
    attr_str = " ".join(attrs)

    html = f"""
    <video {attr_str} preload="metadata"
           style="display:block;width:100%;height:auto;background:#000;">
      <source src="data:video/mp4;base64,{b64}" type="video/mp4">
    </video>
    """
    VIDEO_SLOT.markdown(html, unsafe_allow_html=True)

# -----------------------------
# 汎用メディアレンダリング
# -----------------------------
def render_media(spec: Union[str, Dict[str, Any]]):
    if not spec:
        return
    if isinstance(spec, str):
        path = ensure_asset(spec)
        if str(path).lower().endswith(".mp4"):
            render_video(str(path))
        else:
            st.image(path, use_container_width=True)
        return

    mtype = (spec.get("type") or "").lower()
    file  = spec.get("file")

    if not file:
        if "video" in spec:
            mtype, file = "video", spec["video"]
        elif "image" in spec:
            mtype, file = "image", spec["image"]

    if not file:
        return

    if mtype == "video" or str(file).lower().endswith(".mp4"):
        render_video(file,
                     autoplay=bool(spec.get("autoplay", True)),
                     muted=bool(spec.get("muted", True)),
                     loop=bool(spec.get("loop", False)),
                     controls=bool(spec.get("controls", False)))
    else:
        st.image(ensure_asset(file), use_container_width=True)

def render_chapter_media(chapter: Dict[str, Any]):
    spec = chapter.get("media") or chapter.get("video") or chapter.get("image")
    render_media(spec)

def render_result_media(chapter: Dict[str, Any], result_data: Dict[str, Any]):
    spec = (result_data.get("result_media") or result_data.get("result_image")
            or chapter.get("choice_media") or chapter.get("choice_image")
            or chapter.get("video") or chapter.get("image"))
    render_media(spec)

# -----------------------------
# ナビゲーション
# -----------------------------
def go_next_chapter(next_key: str):
    st.session_state.update({
        "chapter": str(next_key),
        "selected": None,
        "show_result": False,
        "lp_updated": False,
    })

def choose_index(i: int):
    st.session_state.update({"selected": i, "show_result": True, "lp_updated": False})

def start_game():
    st.session_state.update({"chapter": "1", "lp": 90, "lp_updated": False})

# -----------------------------
# メイン
# -----------------------------
def main():
    init_session()
    story = load_story(st.session_state.lang)

    if st.session_state.chapter == "start":
        lang_map = {"日本語":"ja","English":"en"}
        st.session_state.lang = lang_map[st.radio("🌐 Language / 言語",("日本語","English"),index=0)]
        st.image("assets/img_start.png", use_container_width=True)
        st.markdown("宇宙船脱出 / Spaceship Escape")
        st.button("▶ ゲームを始める / Game start", on_click=start_game)
        st.markdown(personalize(story.get("intro_text","")))
        return

    chapter = story["chapters"].get(st.session_state.chapter)
    if not chapter:
        st.error("章データが見つかりません")
        return

    if st.session_state.lp <= 0:
        st.markdown("### 💀 Game Over")
        st.image("assets/img_gameover.png", use_container_width=True)
        if st.button("🔁 Restart"):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            init_session()
        return

    if st.session_state.show_result and st.session_state.selected is not None:
        choice = chapter["choices"][st.session_state.selected]
        result_data = choice["result"]
        if not st.session_state.lp_updated:
            st.session_state.lp = max(0, st.session_state.lp + result_data.get("lp",0))
            st.session_state.lp_updated = True
        render_result_media(chapter, result_data)
        if int(st.session_state.chapter) >= 7:
            st.markdown(f"⏳ Time Left: {st.session_state.lp} min")
        st.markdown(personalize(result_data.get("text","")))
        if choice.get("correct", False):
            st.button("▶次へ/Next",
                      on_click=go_next_chapter,
                      args=(str(result_data.get("next","end")),))
        else:
            st.button("▶ 他を選んでください/Choose Again",
                      on_click=lambda: st.session_state.update({"show_result":False,"selected":None,"lp_updated":False}))
        return

    # 通常の章
    render_chapter_media(chapter)
    if int(st.session_state.chapter) >= 7:
        st.markdown(f"⏳ Time Left: {st.session_state.lp} min")
    st.markdown(personalize(chapter.get("text","")))
    choices = chapter.get("choices") or []
    if not choices:
        st.markdown("🎉 Congratulations! Game Clear! 🎉")
        if st.button("🔙 Back to Start"):
            st.balloons()
            time.sleep(2)
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()
        return
    for i, c in enumerate(choices):
        st.button(personalize(c["text"]), key=f"choice_{i}", on_click=choose_index, args=(i,))

if __name__ == "__main__":
    main()
