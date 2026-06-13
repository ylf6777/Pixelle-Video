"""
开发调试辅助工具
仅在开发模式下使用，提供 Session State 查看等功能
"""
import os
import streamlit as st


def is_dev_mode() -> bool:
    """检查是否处于开发模式"""
    return os.environ.get("PIXELLE_VIDEO_DEV_MODE", "").strip().lower() in ("1", "true", "yes")


def render_session_state_debug():
    """在侧边栏渲染 Session State 查看器，方便调试时检查状态"""
    if not is_dev_mode():
        return
    with st.sidebar.expander("🔍 Session State Debug", expanded=False):
        st.caption(f"共 {len(st.session_state)} 个键")
        # 按前缀分组显示
        keys_by_prefix = {}
        for k in sorted(st.session_state.keys()):
            if k.startswith("_"):
                prefix = "_internal"
            elif "_" in k:
                prefix = k.rsplit("_", 1)[0]
            else:
                prefix = "root"
            keys_by_prefix.setdefault(prefix, []).append(k)
        for prefix, keys in sorted(keys_by_prefix.items()):
            with st.expander(f"📦 {prefix} ({len(keys)})", expanded=False):
                for k in keys:
                    v = st.session_state[k]
                    # 截断长值
                    v_str = str(v)
                    if len(v_str) > 120:
                        v_str = v_str[:120] + "…"
                    st.text(f"{k}: {v_str}")
