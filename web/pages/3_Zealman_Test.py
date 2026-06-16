"""
Zealman 工作流可视化测试页面
支持 J12 电商数字人（人物替换+姿态迁移+背景替换）
"""
import json, ssl, time, base64
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
    wf_names = [f.name for f in wf_files if not f.name.startswith("_") and not f.name.startswith("image_")]
    selected_wf = st.selectbox("工作流", wf_names, index=0 if wf_names else None)

    if selected_wf:
        with open(WORKFLOW_DIR / selected_wf, encoding="utf-8") as f:
            workflow = json.load(f)

        # 图片上传
        st.markdown("**🖼️ 替换人物图片** (651:image)")
        uploaded_img = st.file_uploader("上传图片", type=["jpg", "jpeg", "png", "webp"], key="img_upload")

        # 提示词
        prompt_text = st.text_area("📝 CLIP 提示词 (754:text)", value="年轻女性，时尚穿搭，电商风格，专业灯光", height=60, key="clip_text")
        wan_pos = st.text_area("🎬 Wan 正向提示词 (804:positive_prompt)", value="年轻女性，时尚穿搭，自然动作", height=60, key="wan_pos")
        wan_neg = st.text_area("🚫 Wan 负向提示词 (804:negative_prompt)", value="低质量，模糊，变形，扭曲，水印，文字", height=60, key="wan_neg")

        with st.expander("⚙️ 高级参数"):
            steps = st.slider("采样步数 (530:steps)", 4, 30, 8)
            seed_val = st.number_input("随机种子 (530:seed)", 0, 999999999999, 42)
            cfg_val = st.slider("CFG (530:cfg)", 1.0, 10.0, 1.0, 0.5)

# ── 右侧：视频上传 + 控制 + 结果 ──
with col2:
    st.subheader("🎥 姿态参考视频 (63:video)")
    uploaded_video = st.file_uploader("上传参考视频", type=["mp4", "mov", "avi", "webm"], key="vid_upload")

    st.markdown("---")

    if selected_wf and st.button("🚀 提交生成", type="primary", use_container_width=True, disabled=not uploaded_img):
        with st.spinner("提交中..."):
            img_bytes = uploaded_img.read()
            img_b64 = base64.b64encode(img_bytes).decode()
            img_data = f"data:{uploaded_img.type or 'image/png'};base64,{img_b64}"

            vid_data = ""
            if uploaded_video:
                vid_bytes = uploaded_video.read()
                vid_b64 = base64.b64encode(vid_bytes).decode()
                vid_data = f"data:{uploaded_video.type or 'video/mp4'};base64,{vid_b64}"

            input_values = {
                "52:image": img_data,
                "132:90:text": prompt_text,
                "132:7:text": wan_neg or "low quality, blurry, distorted",
            }
            if vid_data:
                input_values["52:image"] = vid_data

            try:
                # G03用workflow_id（已在面板保存），其他用完整模板
                payload = {"workflow_template": workflow, "input_values": input_values}
                if "G03" in selected_wf or "SmoothMix" in selected_wf:
                    # G03 API 节点ID: 52=LoadImage, 132:90=正提示词, 132:7=负提示词
                    payload = {"workflow_id": "G03-图生视频-Wan2.2SmoothMix", "input_values": input_values}
                resp = _api("POST", "/api/workflow/generate", payload)
                st.session_state["pid"] = resp["prompt_id"]
                st.session_state["start_time"] = time.time()
                st.success(f'任务已提交: {resp["prompt_id"][:20]}...')
                st.rerun()
            except Exception as e:
                st.error(f"提交失败: {e}")

    if "pid" in st.session_state:
        pid = st.session_state["pid"]
        elapsed = time.time() - st.session_state.get("start_time", time.time())

        try:
            result = _api("GET", f"/api/workflow/result?prompt_id={pid}")
            pending = result.get("pending", True)
            results_list = result.get("results", [])

            if pending:
                st.info(f"⏳ 生成中... {elapsed:.0f}s")
                st.progress(min(elapsed / 180, 0.95))
                time.sleep(2)
                st.rerun()
            elif results_list:
                st.success(f"✅ 完成！耗时 {elapsed:.0f}s")
                for r in results_list:
                    url = f"{BASE_URL}{r['url']}"
                    rtype = r.get("type", "unknown")
                    if rtype == "image":
                        st.image(url, caption="生成结果")
                    elif rtype == "video":
                        st.video(url)
                    else:
                        st.markdown(f"[{rtype}] {url}")
                if st.button("🔄 重新生成"):
                    del st.session_state["pid"]
                    st.rerun()
            else:
                st.warning("任务完成但无输出")
        except Exception as e:
            st.error(f"查询失败: {e}")

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
