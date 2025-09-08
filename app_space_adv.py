# app.py — 自動再生 / 動画→動画も先頭から / PC&スマホ両対応 / 余白ゼロ（モバイルも）
import streamlit as st
import streamlit.components.v1 as components
import json, re, base64, html, os, time
from pathlib import Path
from typing import Union, Dict, Any

# 1) ページ設定（必ず最上段）
st.set_page_config(page_title="宇宙船脱出 / Spaceship Escape", layout="centered")

# 2) CSS（角丸ゼロ／重なり防止／上端欠け・スマホ余白対策）
st.markdown("""
<style>
.block-container { padding-top: 2rem !important; padding-bottom: 1rem !important; }

/* ラッパ下の余白を削る */
.stImage, .stVideo { margin-bottom: 0 !important; padding-bottom: 0 !important; }

/* メディア領域のみ角丸ゼロ＆幅100% */
.stImage img,
.stVideo video,
.media-tight > video,
.media-tight > img {
  display:block !important; width:100% !important; height:auto !important;
  margin:0 !important; padding:0 !important; border-radius:0 !important;
  vertical-align: bottom !important;
}

/* メディア直後の要素は最小マージン */
.stImage + div, .stVideo + div, .media-tight + div { margin-top:.44rem !important; }

/* スマホでは完全に詰める */
@media (max-width: 768px) {
  .stImage + div, .stVideo + div, .media-tight + div { margin-top:0 !important; }
}

/* 段落の行間は最小（欠け防止） */
.stMarkdown p { margin-top:0 !important; margin-bottom:.42rem !important; }

/* iOS 最適化＆余白の最終防波堤 */
video {
  -webkit-transform: translateZ(0);
  margin-bottom: 0 !important;
  line-height: 0 !important;
}

/* ボタン角丸も四角に統一（不要なら削除） */
.stButton > button { border-radius:0 !important; }
</style>
""", unsafe_allow_html=True)

CUSTOM_CSS = """
<style>
[data-testid="stImage"], [data-testid="stVideo"]{
  border-radius:0 !important; overflow:hidden !important; margin-bottom:0 !important; padding-bottom:0 !important;
}
[data-testid="stImage"] img{ border-radius:0 !important; display:block !important; }
[data-testid="stVideo"] video{ display:block !important; width:100% !important; height:auto !important; }
</style>
"""

# 3) 物語データ
def load_story(lang: str) -> Dict[str, Any]:
    p = Path("story_space_adv_en.json" if lang == "en" else "story_space_adv_jp.json")
    if not p.exists():
        return {
            "intro_text": "JSONが見つかりません。assets/ にメディアを配置してください。",
            "chapters": {
                "1": {
                    "text": "ダミー章です。JSONを用意してください。",
                    "image": "assets/img_start.png",
                    "choices": [
                        {"text": "▶ Next", "result": {"text": "終わり", "next": "1", "lp": 0}, "correct": True}
                    ]
                }
            }
        }
    return json.loads(p.read_text(encoding="utf-8"))

# 4) セッション関連
def start_game():
    st.session_state.update({
        "chapter": "1",
        "lp": 90,           # ←ここで毎回リセット
        "lp_updated": False
    })

def ch_ge(n: int) -> bool:
    try:
        return int(st.session_state.get("chapter", "0")) >= n
    except Exception:
        return False

def init_session():
    defaults = {
        "chapter": "start",
        "lp": 90,
        "selected": None,
        "show_result": False,
        "show_next": False,
        "show_story": False,
        "player_name": "",
        "lang": "ja",
        "show_choices": False,
        "lp_updated": False,
        "last_media_sig": "",
        "vid_seq": 0,  # 動画ごとに連番（切り替え時は必ず新しい<video>）
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

def personalize(text: str) -> str:
    return re.sub(r"{player_name}", st.session_state.get("player_name", "あなた"), text or "")

def ensure_asset(path: str) -> Path:
    p = Path(path)
    if not (str(p).startswith("assets/") or str(p).startswith("./assets/")):
        p = Path("assets") / p
    return p

# 5) メディア描画（Blob URL 方式・自動再生・モバイル余白ゼロ：iframeの高さを動画実寸に自動追従）
def render_video(path: str, *, autoplay=True, muted=True, loop=False, controls=False, poster: str | None = None):
    """
    - Python側: 動画をbase64化
    - iframe内JS: Blob化→URL.createObjectURL→<video src>に設定
    - autoplay+muted+playsinline（+webkit-playsinline）でiOS自動再生
    - canplayで1回だけ play()（失敗時のみ軽い再トライ）
    - iframeの高さを <video> 実寸に合わせて動的に変更（スマホの“巨大な空白”を完全解消）
    """
    st.session_state.vid_seq += 1
    seq = st.session_state.vid_seq

    p = ensure_asset(path)
    if not p.exists():
        st.warning(f"動画ファイルが見つかりません: {p}")
        return

    b64 = base64.b64encode(p.read_bytes()).decode("utf-8")

    attrs = []
    if autoplay: attrs.append("autoplay")
    if muted:    attrs.append("muted")
    if loop:     attrs.append("loop")
    if controls: attrs.append("controls")
    attrs.append("playsinline")
    attr_str = " ".join(attrs)

    poster_attr = ""
    if poster:
        pp = ensure_asset(poster)
        if pp.exists():
            poster_attr = f' poster="{html.escape(str(pp).replace(os.sep, "/"))}"'

    # iframeの高さを動画の実寸に合わせる関数を用意し、loadedmetadata/canplay/resizeで呼ぶ
    html_code = f"""
    <style>
      html, body {{ margin:0; padding:0; background:#000; }}
    </style>
    <div class="media-tight" style="margin:0;padding:0;border:0;">
      <video id="v{seq}" {attr_str} preload="auto" width="100%" height="auto"{poster_attr}
             style="display:block;margin:0;padding:0;border-radius:0;background:#000;vertical-align:bottom;line-height:0;">
      </video>
    </div>
    <script>
      (function(){{
        function b64ToBlob(b64, contentType) {{
          const bin = atob(b64);
          const len = bin.length;
          const bytes = new Uint8Array(len);
          for (let i=0; i<len; i++) bytes[i] = bin.charCodeAt(i);
          return new Blob([bytes], {{type: contentType}});
        }}

        // 重要：iframeの高さを動画の実寸に合わせる
        function fitFrameToVideo(v) {{
          try {{
            const h = v.getBoundingClientRect().height || v.videoHeight || 0;
            if (h > 0 && window.frameElement) {{
              window.frameElement.style.height = Math.ceil(h) + "px";
            }}
          }} catch(_){{
            // noop
          }}
        }}

        try {{
          const v = document.getElementById("v{seq}");
          v.setAttribute("playsinline","");           // iOS
          v.setAttribute("webkit-playsinline","");    // iOS 旧WebKit互換
          v.muted = {str(bool(muted)).lower()};

          const blob = b64ToBlob("{b64}", "video/mp4");
          const url  = URL.createObjectURL(blob);
          v.src = url;

          let played = false;
          const tryPlayOnce = () => {{
            if (played) return;
            played = true;
            const p = v.play();
            if (p && typeof p.catch === "function") {{
              p.catch(() => setTimeout(() => v.play().catch(()=>{{}}), 200));
            }}
          }};

          const onReady = () => {{ fitFrameToVideo(v); tryPlayOnce(); }};
          v.addEventListener("loadedmetadata", onReady, {{ once: false }});
          v.addEventListener("canplay",        onReady, {{ once: false }});
          window.addEventListener("resize",    () => fitFrameToVideo(v));

          // 再生開始後も念のため高さを合わせ直す
          v.addEventListener("playing", () => {{
            fitFrameToVideo(v);
            setTimeout(() => URL.revokeObjectURL(url), 4000);
          }});

          // 初期リサイズ（低速端末でイベントが遅い場合の保険）
          setTimeout(() => fitFrameToVideo(v), 150);
          setTimeout(() => fitFrameToVideo(v), 600);
        }} catch(e) {{
          console.error(e);
        }}
      }})();
    </script>
    """
    # 初期高さは小さめでOK。JSで即フィットさせる。
    components.html(html_code, height=120, scrolling=False)

def render_media(spec: Union[str, Dict[str, Any]]):
    if spec is None:
        return
    if isinstance(spec, str):
        st.image(ensure_asset(spec), use_container_width=True)
        return

    mtype = spec.get("type", "image")
    file = spec.get("file")
    if not file:
        return

    if mtype == "video":
        render_video(
            file,
            autoplay=bool(spec.get("autoplay", True)),   # 既定：自動再生
            muted=bool(spec.get("muted", True)),         # 既定：無音（必須）
            loop=bool(spec.get("loop", False)),
            controls=bool(spec.get("controls", False)),  # 既定：コントロール非表示
            poster=spec.get("poster"),
        )
    else:
        st.image(ensure_asset(file), use_container_width=True)

def render_chapter_media(chapter: Dict[str, Any]):
    spec = chapter.get("media") or chapter.get("image")
    render_media(spec)

def render_result_media(chapter: Dict[str, Any], result_data: Dict[str, Any]):
    spec = (
        result_data.get("result_media")
        or result_data.get("result_image")
        or chapter.get("choice_media")
        or chapter.get("choice_image")
        or chapter.get("image")
    )
    render_media(spec)

# 6) 状態操作
def go_next_chapter(next_key: str):
    st.session_state.update({
        "chapter": str(next_key),
        "selected": None,
        "show_result": False,
        "show_story": False,
        "show_choices": False,
        "lp_updated": False,
    })

def choose_index(i: int):
    st.session_state.update({"selected": i, "show_result": True, "lp_updated": False})

def start_game():
    st.session_state.chapter = "1"

# 7) メイン
def main():
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    init_session()

    header_col  = st.container()
    media_col   = st.container()
    status_col  = st.container()
    text_col    = st.container()
    choices_col = st.container()
    footer_col  = st.container()

    if st.session_state.chapter == "start":
        with header_col:
            lang_map = {"日本語": "ja", "English": "en"}
            st.session_state.lang = lang_map[st.radio("🌐 Language / 言語を選んでください：", ("日本語", "English"), index=0)]
            story = load_story(st.session_state.lang)

            st.image("assets/img_start.png", use_container_width=True)
            st.markdown("宇宙船脱出 / Spaceship Escape")
            st.button("▶ ゲームを始める / Game start", key="btn_start", on_click=start_game)

            st.markdown(personalize(story.get("intro_text", "")))
        return

    story = load_story(st.session_state.lang)
    chapter_key = st.session_state.chapter
    chapter = story["chapters"].get(chapter_key)
    if not chapter:
        with header_col:
            st.error("この章のデータが見つかりません")
        return

    if st.session_state.lp <= 0:
        with media_col:
            st.markdown("### 💀  Game Over")
            st.image("assets/img_gameover.png", use_container_width=True)
        with footer_col:
            if st.button("🔁 最初からやり直す / Restart"):
                for k in list(st.session_state.keys()):
                    del st.session_state[k]
                init_session()
        return

    if st.session_state.show_result and st.session_state.selected is not None:
        choice = chapter["choices"][st.session_state.selected]
        result_data = choice["result"]
        result_text = personalize(result_data.get("text", ""))

        if not st.session_state.lp_updated and ch_ge(7):
            st.session_state.lp = max(0, min(100, st.session_state.lp + result_data.get("lp", 0)))
            st.session_state.lp_updated = True

        with media_col:
            render_result_media(chapter, result_data)

        with status_col:
            if ch_ge(7):
                st.markdown(f"⏳ 残り時間/Time left: {st.session_state.lp} min")

        with text_col:
            st.markdown(result_text, unsafe_allow_html=True)

        with choices_col:
            button_label_n = result_data.get("button_label_n", "▶ 次へ / Next")
            if choice.get("correct", False):
                st.button(button_label_n, on_click=go_next_chapter, args=(str(result_data.get("next", "end")),))
            else:
                st.button(
                    "▶ 他を試してください / Choose Again",
                    on_click=lambda: st.session_state.update({"show_result": False, "selected": None, "lp_updated": False}),
                )
        return

    # 通常シーン描画
    with media_col:
        st.session_state.last_media_sig = str(st.session_state.chapter)
        render_chapter_media(chapter)

    with status_col:
        if ch_ge(7):
            st.markdown(f"⏳ 残り時間/Time left: {st.session_state.lp} min")

    with text_col:
        st.markdown(personalize(chapter.get("text", "")), unsafe_allow_html=True)

    with choices_col:
        choices = chapter.get("choices") or []
        if not choices:
            st.markdown("🎉 Congratulations! Game Clear! 🎉")
            if st.button("🔙 スタート画面に戻る / Back to start"):
                st.balloons()
                time.sleep(2)
                st.session_state.clear()
                st.rerun()
            return

        for i, c in enumerate(choices):
            st.button(personalize(c["text"]), key=f"choice_{i}", on_click=choose_index, args=(i,))

if __name__ == "__main__":
    main()
