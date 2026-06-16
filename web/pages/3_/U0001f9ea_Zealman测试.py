"""
Zealman 工作流可视化测试页面
支持 J12 电商数字人（人物替换+姿态迁移+背景替换）
"""
import json, ssl, time, base64, io
import urllib.request
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="Zealman 工作流测试", page_icon="🧪", layout="wide")

BASE_URL = "https://uu1021136-781466526648.bjb2.seetacloud.com:8443"
WORKFLOW_DIR = Path(__file__).parent.parent.parent / "workflows" / "selfhost"

# SSL 配置
_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE


def _api(method: str, path: str, data: dict | None = None) -> dict:
    """zealman API 请求"""
    url = f"{BASE_URL}{path}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}) if body else urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=60, context=_CTX) as r:
        return json.loads(r.read())


st.title("🧪 Zealman 工作流测试")
st.caption(f"API: {BASE_URL}")

# ── 左侧：参数配置 ──
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📋 输入参数")

    # 工作流选择
    wf_files = sorted(WORKFLOW_DIR.glob("*.json"))
    wf_names = [f.name for f in wf_files if not f.name.startswith("_")]
    selected_wf = st.selectbox("工作流", wf_names, index=0)

    with open(WORKFLOW_DIR / selected_wf, encoding="utf-8") as f:
        workflow = json.load(f)

    # 图片上传
    st.markdown("**🖼️ 替换人物图片** (651:image)")
    uploaded_img = st.file_uploader("上传图片", type=["jpg", "jpeg", "png", "webp"], key="img_upload",
                                    help="用于替换原视频中的人物")

    # 提示词
    st.markdown("**📝 提示词** (754:text)")
    prompt_text = st.text_area("CLIP 提示词", value="年轻女性，时尚穿搭，电商风格，专业灯光",
                               height=60, key="clip_text",
                               help="描述人物外观、风格、场景")

    st.markdown("**🎬 Wan 正向提示词** (804:positive_prompt)")
    wan_pos = st.text_area("正向", value="年轻女性，时尚穿搭，自然动作，专业摄影棚灯光，高清画质",
                           height=60, key="wan_pos")

    st.markdown("**🚫 Wan 负向提示词** (804:negative_prompt)")
    wan_neg = st.text_area("负向", value="低质量，模糊，变形，扭曲，丑陋，多余手指，水印，文字",
                           height=60, key="wan_neg")

    # 高级参数
    with st.expander("⚙️ 高级参数"):
        steps = st.slider("采样步数 (530:steps)", 4, 30, 8)
        seed_val = st.number_input("随机种子 (530:seed)", 0, 999999999999, 42)
        cfg_val = st.slider("CFG (530:cfg)", 1.0, 10.0, 1.0, 0.5)

# ── 右侧：视频上传 + 控制 + 结果 ──
with col2:
    st.subheader("🎥 姿态参考视频 (63:video)")
    uploaded_video = st.file_uploader("上传参考视频", type=["mp4", "mov", "avi", "webm"], key="vid_upload",
                                      help="提供动作姿态的参考视频")

    # 提交按钮
    st.markdown("---")
    if st.button("🚀 提交生成", type="primary", use_container_width=True, disabled=not uploaded_img):
        with st.spinner("提交中..."):
            # 图片转 base64
            img_bytes = uploaded_img.read()
            img_b64 = base64.b64encode(img_bytes).decode()
            mime = uploaded_img.type or "image/png"
            img_data = f"data:{mime};base64,{img_b64}"

            # 视频处理
            vid_data = ""
            if uploaded_video:
                vid_bytes = uploaded_video.read()
                vid_b64 = base64.b64encode(vid_bytes).decode()
                vid_mime = uploaded_video.type or "video/mp4"
                vid_data = f"data:{vid_mime};base64,{vid_b64}"

            # 构建 input_values
            input_values = {
                "651:image": img_data,
                "754:text": prompt_text,
                "804:positive_prompt": wan_pos,
                "804:negative_prompt": wan_neg,
                "530:steps": steps,
                "530:seed": seed_val,
                "530:cfg": cfg_val,
            }
            if vid_data:
                input_values["63:video"] = vid_data

            try:
                resp = _api("POST", "/api/workflow/generate", {
                    "workflow_template": workflow,
                    "input_values": input_values,
                })
                st.session_state["pid"] = resp["prompt_id"]
                st.session_state["start_time"] = time.time()
                st.success(f'任务已提交: {resp["prompt_id"][:20]}...')
                st.rerun()
            except Exception as e:
                st.error(f"提交失败: {e}")

    # 进度与结果
    if "pid" in st.session_state:
        pid = st.session_state["pid"]
        elapsed = time.time() - st.session_state.get("start_time", time.time())

        # 轮询状态
        status_placeholder = st.empty()
        progress_bar = st.progress(0)
        result_placeholder = st.empty()

        try:
            result = _api("GET", f"/api/workflow/result?prompt_id={pid}")
            pending = result.get("pending", True)
            results_list = result.get("results", [])

            if pending:
                status_placeholder.info(f"⏳ 生成中... {elapsed:.0f}s")
                progress_bar.progress(min(elapsed / 180, 0.95))
                time.sleep(2)
                st.rerun()
            elif results_list:
                status_placeholder.success(f"✅ 完成！耗时 {elapsed:.0f}s")
                progress_bar.progress(1.0)
                for r in results_list:
                    url = f"{BASE_URL}{r['url']}"
                    rtype = r.get("type", "unknown")
                    if rtype == "image":
                        st.image(url, caption="生成结果")
                    elif rtype == "video":
                        st.video(url)
                    else:
                        st.markdown(f"[{rtype}] {url}")
                # 清除状态，允许重新提交
                if st.button("🔄 重新生成"):
                    del st.session_state["pid"]
                    st.rerun()
            else:
                status_placeholder.warning("任务完成但无输出，可能配置有误")
        except Exception as e:
            status_placeholder.error(f"查询失败: {e}")

# ── 底部：状态栏 ──
st.markdown("---")
try:
    health = _api("GET", "/api/health")
    gpu = _api("GET", "/api/gpu/info")
    comfy = _api("GET", "/api/comfy/status")
    st.caption(
        f"🟢 服务器正常 | GPU: {gpu.get('gpuName', '?')} | "
        f"ComfyUI: {'✅ 运行中' if comfy.get('running') else '⏸ 已停止'} | "
        f"运行时间: {health.get('uptime', 0):.0f}s"
    )
except:
    st.caption("⚠️ 无法连接服务器")
