# Copyright (C) 2025 AIDC-AI
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Output preview components for web UI (right column).
Each functional unit is an independent callable assigned to a module-level variable.

=============================================================================
改代码速查表（修改前先看这里，防止改错位置）
=============================================================================

【要改分镜增删逻辑】
  → 找 _storyboard_ops（约第90行），里面 _do_insert / _do_delete / append
  → 纯 Python 逻辑，不依赖 Streamlit，改了可以直接跑 python 测试

【要改单张分镜卡片的 UI（文本框、按钮、参考图布局）】
  → 找 _render_storyboard_card（约第150行）
  → 一张卡片的完整渲染：文本区 + 插入按钮 + 删除按钮 + 参考图

【要改参考图上传/删除逻辑】
  → 找 _reference_image_manager（约第125行）
  → _save_ref_image / _remove_ref_image

【要改 AI 分析生成分镜的逻辑】
  → 找 _exec_ai_breakdown（约第70行）
  → 调的是 pixelle_video.utils.content_generators.generate_scene_breakdown

【要改确认/重置按钮的行为】
  → 找 _render_storyboard_editor（约第240行），看 confirm_scenes / reset_scenes

【要改视频生成按钮、进度条、下载】
  → 找 _execute_video_generation（约第290行）

【要改整个单视频模式的流程编排（AI分析→编辑→确认→生成）】
  → 找 _execute_single_output（约第350行）

【要改批量生成模式】
  → 找 _execute_batch_output（约第390行）

【外部调用入口（不要随意改名，其他地方 import 这个）】
  → render_output_preview（约第530行）
  → render_single_output
  → render_batch_output

=============================================================================
"""

import base64
import os
import uuid as _uuid
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import streamlit as st
from loguru import logger

from web.i18n import tr, get_language
from web.utils.async_helpers import run_async
from pixelle_video.models.progress import ProgressEvent
from pixelle_video.config import config_manager
from pixelle_video.constants import (
    MAX_REF_IMAGE_SIZE,
    PROGRESS_CAP,
    BATCH_ESTIMATED_MINUTES_PER_VIDEO,
)


# ═══════════════════════════════════════════════════════════════════════════
# 模块 1：AI 分镜生成
# 改 AI 分镜拆分逻辑 → 看这个模块
# 核心函数：_exec_ai_breakdown
# 调用的外部：pixelle_video.utils.content_generators.generate_scene_breakdown
# ═══════════════════════════════════════════════════════════════════════════

_ai_scene_breakdown = lambda pixelle_video, text, scenes_key="st_scenes", media_type="image": (
    # 调用 AI 分析文章并拆分为分镜，为每个分镜分配 _uid
    _exec_ai_breakdown(pixelle_video, text, scenes_key, media_type)
)

def _exec_ai_breakdown(pixelle_video, text: str, scenes_key: str,
                        media_type: str = "image") -> None:
    """调用 generate_scene_breakdown 并将结果写入 st.session_state。

    根据当前分镜类型（image/video）使用对应的提示词模板，
    确保生图模式生成 image_prompts，视频模式生成 video_prompts。
    如果 AI 返回的 JSON 解析失败，看 pixelle_video/utils/content_generators.py
    里 _parse_json 函数。"""

    from pixelle_video.utils.content_generators import generate_scene_breakdown
    scenes = run_async(generate_scene_breakdown(pixelle_video.llm, text, media_type))
    for _s in scenes:
        if "_uid" not in _s:
            _s["_uid"] = str(_uuid.uuid4())[:8]
    st.session_state[scenes_key] = scenes
    st.session_state["st_confirmed"] = False


# ═══════════════════════════════════════════════════════════════════════════
# 模块 2：分镜 CRUD 纯逻辑
# 改插入/删除/追加分镜的位置和内容 → 看这个模块
# 不依赖 st，不依赖 Streamlit，纯 Python，可直接 python 跑测试
# 核心函数：_do_insert(列表, 索引) / _do_delete(列表, 索引)
# 新分镜初始值在这里定义：{"image_prompt": "", "narration": "", "_uid": "..."}
# ═══════════════════════════════════════════════════════════════════════════

_storyboard_ops = {
    "insert_after": lambda cur, idx: (
        # 在 idx 之后插入一个空白分镜，返回新列表
        _do_insert(cur, idx)
    ),
    "delete_at": lambda cur, idx: (
        # 删除 idx 位置的分镜，返回 (新列表, 被删分镜的_uid)
        _do_delete(cur, idx)
    ),
    "append": lambda cur: (
        # 在末尾追加一个空白分镜，返回新列表
        cur + [{"image_prompt": "", "narration": "", "_uid": str(_uuid.uuid4())[:8]}]
    ),
}

def _do_insert(cur: List[dict], idx: int) -> List[dict]:
    """在 idx 后插入空白分镜，返回新列表（不修改原列表）。
    注意：新分镜的默认文本为空字符串，如果出现非空文本说明 widget key 碰撞了"""
    result = list(cur)
    result.insert(idx + 1, {"image_prompt": "", "narration": "",
                             "_uid": str(_uuid.uuid4())[:8]})
    return result

def _do_delete(cur: List[dict], idx: int) -> Tuple[List[dict], Optional[str]]:
    """删除 idx 位置的分镜，返回 (新列表, 被删_uid)。被删_uid 用于清除关联参考图。"""
    if not (0 <= idx < len(cur)):
        return list(cur), None
    result = list(cur)
    removed = result.pop(idx)
    return result, removed.get("_uid")


# ═══════════════════════════════════════════════════════════════════════════
# 模块 3：参考图管理
# 改参考图的上传/删除/存储逻辑 → 看这个模块
# 参考图以 base64 data URL 存储在 st.session_state["st_refs"][uid]
# ═══════════════════════════════════════════════════════════════════════════

_reference_image_manager = {
    "save": lambda ref_key, uid, uploaded_file: (
        _save_ref_image(ref_key, uid, uploaded_file)
    ),
    "remove": lambda ref_key, uid: (
        _remove_ref_image(ref_key, uid)
    ),
    "remove_by_uid": lambda ref_key, uid: (
        # 删除指定 uid 的参考图（供删除分镜时使用）
        st.session_state.get(ref_key, {}).pop(uid, None)
    ),
}

def _save_ref_image(ref_key: str, uid: str, uploaded_file) -> Optional[str]:
    """保存上传的参考图为 base64 data URL，返回 data URL 或 None。"""
    if not uploaded_file or uploaded_file.size > MAX_REF_IMAGE_SIZE:
        return None
    img_bytes = uploaded_file.read()
    b64 = base64.b64encode(img_bytes).decode()
    mime = uploaded_file.type or "image/png"
    data_url = f"data:{mime};base64,{b64}"
    st.session_state.setdefault(ref_key, {})[uid] = data_url
    return data_url

def _remove_ref_image(ref_key: str, uid: str) -> None:
    """删除指定 uid 的参考图。"""
    refs = st.session_state.get(ref_key, {})
    refs.pop(uid, None)
    if ref_key in st.session_state:
        st.session_state[ref_key] = refs


# ═══════════════════════════════════════════════════════════════════════════
# 模块 4：单个分镜卡片渲染
# 改卡片的 UI 布局、按钮样式、文本框大小 → 看这个模块
# 注意：widget key 必须用 uid 不能用索引 i，否则插入/删除后文本会串位
# 核心函数：_render_storyboard_card(scene, index_1based, uid, ...)
# ═══════════════════════════════════════════════════════════════════════════

def _render_storyboard_card(
    scene: dict,
    index_1based: int,
    uid: str,
    scenes_key: str,
    ref_key: str,
    edited_list: List[dict],
) -> None:
    """渲染一张完整的分镜卡片（文本区 + 操作按钮 + 参考图），结果追加到 edited_list。"""
    st.markdown(f"**分镜 {index_1based}**")

    # ---- 文本编辑区 ----
    c1, c2 = st.columns([1, 1])
    with c1:
        ips = scene.get("image_prompts", [scene.get("image_prompt", "")])
        if isinstance(ips, str):
            ips = [ips]
        ip_text = ips[0] if ips else ""
        ip = st.text_area(
            f"画面提示词", ip_text, height=80,
            key=f"st_ip_{uid}", label_visibility="collapsed",
            placeholder=f"分镜{index_1based}画面提示词")
    with c2:
        nr = st.text_area(
            f"旁白", scene.get("narration", ""), height=80,
            key=f"st_nr_{uid}", label_visibility="collapsed",
            placeholder=f"分镜{index_1based}旁白")

    # ---- 操作按钮行 ----
    b1, b2, b3 = st.columns([1, 1, 2])
    with b1:
        if st.button(f"＋ 插入到分镜{index_1based}后", key=f"btn_insert_{uid}",
                     use_container_width=True):
            cur = list(st.session_state.get(scenes_key, []))
            st.session_state[scenes_key] = _storyboard_ops["insert_after"](cur, index_1based - 1)
            st.rerun()
    with b2:
        if st.button(f"✕ 删除分镜{index_1based}", key=f"btn_delete_{uid}",
                     use_container_width=True):
            cur = list(st.session_state.get(scenes_key, []))
            new_cur, removed_uid = _storyboard_ops["delete_at"](cur, index_1based - 1)
            st.session_state[scenes_key] = new_cur
            if removed_uid:
                _reference_image_manager["remove_by_uid"](ref_key, removed_uid)
            st.rerun()

    # ---- 参考图上传/预览 ----
    ref_col, del_col = st.columns([4, 1])
    with ref_col:
        uploaded = st.file_uploader(
            "📷 参考图（可选）", type=["jpg", "jpeg", "png", "webp"],
            key=f"st_upload_{uid}", label_visibility="collapsed",
            help="上传参考图以融入插画创作")
        if uploaded is not None:
            if uploaded.size <= MAX_REF_IMAGE_SIZE:
                _reference_image_manager["save"](ref_key, uid, uploaded)
            else:
                st.error("图片不能超过 10MB")

    with del_col:
        if uid in st.session_state.get(ref_key, {}):
            st.image(st.session_state[ref_key][uid], width=60, caption="参考图")
            if st.button("✕", key=f"st_delref_{uid}", help="删除参考图"):
                _reference_image_manager["remove"](ref_key, uid)
                st.rerun()

    # ---- 收集编辑结果 ----
    edited_list.append({
        "image_prompt": ip, "narration": nr,
        "reference_image": st.session_state.get(ref_key, {}).get(uid),
        "_uid": uid
    })


# ═══════════════════════════════════════════════════════════════════════════
# 模块 5：分镜编辑器整体
# 改确认按钮、重置按钮、"在末尾添加"按钮 → 看这个模块
# 改确认后数据组装格式（画面提示词｜旁白）→ 看 confirm_scenes 按钮回调
# ═══════════════════════════════════════════════════════════════════════════

_storyboard_editor = lambda scenes_key, ref_key, confirmed: (
    _render_storyboard_editor(scenes_key, ref_key, confirmed)
)

def _render_storyboard_editor(scenes_key: str, ref_key: str, confirmed: bool) -> Tuple[str, List[dict]]:
    """渲染完整的分镜编辑器。返回 (assembled_text, edited_list)。"""
    scenes = st.session_state.get(scenes_key, [])

    # 确保每个分镜都有唯一 ID（兼容旧数据）
    for _s in scenes:
        if "_uid" not in _s:
            _s["_uid"] = str(_uuid.uuid4())[:8]

    if not scenes:
        return "", []

    st.markdown("---")
    st.caption("以下内容可自由修改，修改后点「确认内容」")

    edited = []

    # 渲染每张分镜卡片
    for i, s in enumerate(scenes):
        _render_storyboard_card(
            scene=s,
            index_1based=i + 1,
            uid=s["_uid"],
            scenes_key=scenes_key,
            ref_key=ref_key,
            edited_list=edited,
        )

    # ---- 末尾追加按钮 ----
    if st.button("＋ 在末尾添加新分镜", key="btn_append_end",
                 help="在最后添加一个空白分镜", use_container_width=True):
        cur = list(st.session_state.get(scenes_key, []))
        st.session_state[scenes_key] = _storyboard_ops["append"](cur)
        st.rerun()

    # ---- 确认 / 重置 ----
    assembled_text = ""
    cA, cB = st.columns([1, 1])
    with cA:
        if st.button("✅ 确认内容", use_container_width=True, type="primary", key="confirm_scenes"):
            if all(e["image_prompt"].strip() and e["narration"].strip() for e in edited):
                assembled_text = "\n\n".join(
                    f"{e['image_prompt']} | {e['narration']}" for e in edited
                )
                st.session_state["st_confirmed"] = True
                st.session_state["st_assembled"] = assembled_text
                st.session_state["st_ref_images"] = {
                    i: e["reference_image"] for i, e in enumerate(edited)
                    if e.get("reference_image")
                }
                st.success(f"已确认 {len(edited)} 个分镜")
                st.rerun()
            else:
                st.error("每个分镜都需要填写画面提示词和旁白")
    with cB:
        if st.button("🔄 重置", use_container_width=True, key="reset_scenes"):
            st.session_state.pop(scenes_key, None)
            st.session_state["st_confirmed"] = False
            st.rerun()

    # 确认后的状态提示
    if confirmed:
        assembled_text = st.session_state.get("st_assembled", "")
        st.success(f"✅ 已确认 {len(edited)} 个分镜，可以生成视频了")
        st.caption(f"已组装 {len(edited)} 段，每段格式：画面提示词｜旁白")

    return assembled_text, edited


# ═══════════════════════════════════════════════════════════════════════════
# 模块 6：视频生成与展示
# 改生成按钮行为、进度条、视频预览、下载按钮 → 看这个模块
# 核心函数：_execute_video_generation
# 实际调用的外部：pixelle_video.generate_video(**gen_params)
# ═══════════════════════════════════════════════════════════════════════════

_video_generator = lambda pixelle_video, video_params: (
    _execute_video_generation(pixelle_video, video_params)
)

def _execute_video_generation(pixelle_video, video_params: dict) -> None:
    """执行视频生成、显示进度条、预览和下载按钮。"""
    if not config_manager.validate():
        st.error(tr("settings.not_configured"))
        st.stop()

    if not video_params.get("text"):
        st.error(tr("error.input_required"))
        st.stop()

    frame_template = video_params.get("frame_template")
    workflow_key = video_params.get("media_workflow")
    if frame_template:
        from pixelle_video.utils.template_util import get_template_type
        if get_template_type(frame_template) == "video" and not workflow_key:
            st.error(
                "请选择视频生成工作流或 API 视频模型后再生成。"
                if get_language() == "zh_CN"
                else "Please select a video workflow or API video model before generating."
            )
            st.stop()

    progress_bar = st.progress(0)
    status_text = st.empty()
    start_time = time.time()

    try:
        def update_progress(event: ProgressEvent):
            if event.event_type == "frame_step":
                action_text = tr(f"progress.step_{event.action}")
                message = tr("progress.frame_step", current=event.frame_current,
                             total=event.frame_total, step=event.step, action=action_text)
            elif event.event_type == "processing_frame":
                message = tr("progress.frame", current=event.frame_current,
                             total=event.frame_total)
            else:
                message = tr(f"progress.{event.event_type}")
            if event.extra_info:
                message = f"{message} - {event.extra_info}"
            status_text.text(message)
            progress_bar.progress(min(int(event.progress * 100), PROGRESS_CAP))

        gen_params = {
            "text": video_params.get("text"),
            "mode": video_params.get("mode"),
            "title": video_params.get("title") or None,
            "n_scenes": video_params.get("n_scenes", 5),
            "split_mode": video_params.get("split_mode", "paragraph"),
            "media_workflow": workflow_key,
            "api_video_params": video_params.get("api_video_params"),
            "frame_template": frame_template,
            "prompt_prefix": video_params.get("prompt_prefix", ""),
            "bgm_path": video_params.get("bgm_path"),
            "bgm_volume": video_params.get("bgm_volume", 0.2),
            "progress_callback": update_progress,
            "media_width": st.session_state.get('template_media_width'),
            "media_height": st.session_state.get('template_media_height'),
            "reference_images": st.session_state.get("st_ref_images", {}),
            "tts_inference_mode": video_params.get("tts_inference_mode", "local"),
        }
        if gen_params["tts_inference_mode"] == "local":
            gen_params["tts_voice"] = video_params.get("tts_voice")
            gen_params["tts_speed"] = video_params.get("tts_speed")
        else:
            gen_params["tts_workflow"] = video_params.get("tts_workflow")
            if video_params.get("ref_audio"):
                gen_params["ref_audio"] = str(video_params["ref_audio"])
        if video_params.get("template_params"):
            gen_params["template_params"] = video_params["template_params"]

        result = run_async(pixelle_video.generate_video(**gen_params))
        total_time = time.time() - start_time

        progress_bar.progress(100)
        status_text.text(tr("status.success"))
        st.success(tr("status.video_generated", path=result.video_path))
        st.markdown("---")

        file_size_mb = result.file_size / (1024 * 1024)
        from pixelle_video.utils.template_util import parse_template_size, resolve_template_path
        tp = resolve_template_path(result.storyboard.config.frame_template)
        vw, vh = parse_template_size(tp)
        st.caption(
            f"⏱️ {tr('info.generation_time')} {total_time:.1f}s   "
            f"📦 {file_size_mb:.2f}MB   "
            f"🎬 {len(result.storyboard.frames)}{tr('info.scenes_unit')}   "
            f"📐 {vw}x{vh}"
        )
        st.markdown("---")

        if os.path.exists(result.video_path):
            st.video(result.video_path)
            with open(result.video_path, "rb") as vf:
                st.download_button(
                    label="⬇️ 下载视频" if get_language() == "zh_CN" else "⬇️ Download Video",
                    data=vf.read(),
                    file_name=os.path.basename(result.video_path),
                    mime="video/mp4",
                    use_container_width=True
                )
        else:
            st.error(tr("status.video_not_found", path=result.video_path))

    except Exception as e:
        status_text.text("")
        progress_bar.empty()
        st.error(tr("status.error", error=str(e)))
        logger.exception(e)
        st.stop()


# ═══════════════════════════════════════════════════════════════════════════
# 模块 7：单视频模式入口
# 改整个单视频页面的流程编排（Step1→Step2→Step3 的顺序）→ 看这个模块
# 当前流程：AI分析按钮 → 分镜编辑器 → 生成视频按钮
# 不要在别的模块改流程顺序，只在这里改
# ═══════════════════════════════════════════════════════════════════════════

_render_single_output = lambda pixelle_video, video_params: (
    _execute_single_output(pixelle_video, video_params)
)

def _execute_single_output(pixelle_video, video_params: dict) -> None:
    """单视频模式的完整入口：AI分析 → 编辑 → 确认 → 生成。"""
    text = video_params.get("text", "")
    confirmed = st.session_state.get("st_confirmed", False)
    scenes_key = "st_scenes"
    ref_key = "st_refs"

    if ref_key not in st.session_state:
        st.session_state[ref_key] = {}

    with st.container(border=True):
        st.markdown(f"**{tr('section.video_generation')}**")

        if not config_manager.validate():
            st.warning(tr("settings.not_configured"))

        # Step 1：AI 分析生成分镜
        if text.strip():
            st.markdown("---")
            st.markdown("**📋 分镜内容管理**")
            if st.button("🤖 AI 分析生成分镜", use_container_width=True, key="ai_gen_scenes"):
                with st.spinner("AI 分析文章中..."):
                    try:
                        media_type = st.session_state.get("template_media_type", "image")
                        _exec_ai_breakdown(pixelle_video, text, scenes_key, media_type)
                        st.rerun()
                    except Exception as e:
                        logger.exception(f"AI 分镜分析失败: {e}")
                        st.error(f"AI 分析失败: {e}")

        # Step 2：分镜编辑器
        assembled_text, _ = _storyboard_editor(scenes_key, ref_key, confirmed)
        if confirmed and assembled_text:
            text = assembled_text

        # Step 3：生成按钮
        scenes = st.session_state.get(scenes_key, [])
        gen_disabled = bool(scenes) and not confirmed
        if st.button("🎬 生成视频" if confirmed else tr("btn.generate"),
                     type="primary", use_container_width=True, disabled=gen_disabled):
            video_params["text"] = text
            _video_generator(pixelle_video, video_params)


# ═══════════════════════════════════════════════════════════════════════════
# 模块 8：批量视频入口
# 改批量生成逻辑 → 看这个模块
# 注意：批量模式不走分镜编辑器，直接调 pixelle_video.generate_video
# ═══════════════════════════════════════════════════════════════════════════

_render_batch_output = lambda pixelle_video, video_params: (
    _execute_batch_output(pixelle_video, video_params)
)

def _execute_batch_output(pixelle_video, video_params: dict) -> None:
    """批量视频生成模式。"""
    topics = video_params.get("topics", [])

    with st.container(border=True):
        st.markdown(f"**{tr('batch.section_generation')}**")

        if not topics:
            st.warning(tr("batch.no_topics"))
            return

        if not config_manager.validate():
            st.warning(tr("settings.not_configured"))
            return

        batch_count = len(topics)
        st.info(tr("batch.prepare_info", count=batch_count))
        estimated_minutes = batch_count * BATCH_ESTIMATED_MINUTES_PER_VIDEO
        st.caption(tr("batch.estimated_time", minutes=estimated_minutes))

        if st.button(tr("batch.generate_button", count=batch_count),
                     type="primary", use_container_width=True,
                     help=tr("batch.generate_help")):
            # 组装共享配置
            shared_config = {
                "title_prefix": video_params.get("title_prefix"),
                "n_scenes": video_params.get("n_scenes") or 5,
                "media_workflow": video_params.get("media_workflow"),
                "api_video_params": video_params.get("api_video_params"),
                "frame_template": video_params.get("frame_template"),
                "prompt_prefix": video_params.get("prompt_prefix") or "",
                "bgm_path": video_params.get("bgm_path"),
                "bgm_volume": video_params.get("bgm_volume") or 0.2,
                "tts_inference_mode": video_params.get("tts_inference_mode") or "local",
                "media_width": video_params.get("media_width"),
                "media_height": video_params.get("media_height"),
            }
            if shared_config["tts_inference_mode"] == "local":
                for k in ("tts_voice", "tts_speed"):
                    v = video_params.get(k)
                    if v is not None:
                        shared_config[k] = v
            else:
                for k in ("tts_workflow", "ref_audio"):
                    v = video_params.get(k)
                    if v is not None:
                        shared_config[k] = str(v) if k == "ref_audio" else v
            if video_params.get("template_params"):
                shared_config["template_params"] = video_params["template_params"]

            # 进度 UI
            overall_container = st.container()
            task_container = st.container()
            overall_bar = overall_container.progress(0)
            overall_status = overall_container.empty()
            task_title = task_container.empty()
            task_bar = task_container.progress(0)
            task_status = task_container.empty()

            def update_overall(current, total, topic):
                p = (current - 1) / total
                overall_bar.progress(p)
                overall_status.markdown(
                    f"📊 **{tr('batch.overall_progress')}**: {current}/{total} ({int(p * 100)}%)"
                )

            def make_task_callback(task_idx, topic):
                def callback(event: ProgressEvent):
                    task_title.markdown(f"🎬 **{tr('batch.current_task')} {task_idx}**: {topic}")
                    if event.event_type == "frame_step":
                        at = tr(f"progress.step_{event.action}")
                        msg = tr("progress.frame_step", current=event.frame_current,
                                 total=event.frame_total, step=event.step, action=at)
                    elif event.event_type == "processing_frame":
                        msg = tr("progress.frame", current=event.frame_current,
                                 total=event.frame_total)
                    else:
                        msg = tr(f"progress.{event.event_type}")
                    task_bar.progress(event.progress)
                    task_status.text(msg)
                return callback

            from web.utils.batch_manager import SimpleBatchManager
            start = time.time()
            result = SimpleBatchManager().execute_batch(
                pixelle_video=pixelle_video, topics=topics, shared_config=shared_config,
                overall_progress_callback=update_overall,
                task_progress_callback_factory=make_task_callback,
            )
            elapsed = time.time() - start

            overall_bar.progress(1.0)
            overall_status.markdown(f"✅ **{tr('batch.completed')}**")
            task_title.empty(); task_bar.empty(); task_status.empty()

            st.markdown("---")
            st.markdown(f"**{tr('batch.results_title')}**")
            c1, c2, c3 = st.columns(3)
            c1.metric(tr("batch.total"), result["total_count"])
            c2.metric(f"✅ {tr('batch.success')}", result["success_count"])
            c3.metric(f"❌ {tr('batch.failed')}", result["failed_count"])
            m, s = divmod(int(elapsed), 60)
            st.caption(f"⏱️ {tr('batch.total_time')}: {m}{tr('batch.minutes')}{s}{tr('batch.seconds')}")

            st.markdown("---")
            st.success(tr("batch.success_message"))
            st.info(tr("batch.view_in_history"))
            st.markdown(
                f"""<a href="/History" target="_blank"><button style="
                width:100%;padding:0.5rem 1rem;background-color:white;
                color:rgb(49,51,63);border:1px solid rgba(49,51,63,0.2);
                border-radius:0.5rem;cursor:pointer;font-size:1rem;
                text-align:center;">📚 {tr('batch.goto_history')}</button></a>""",
                unsafe_allow_html=True)

            if result["errors"]:
                st.markdown("---")
                st.markdown(f"#### {tr('batch.failed_list')}")
                for item in result["errors"]:
                    with st.expander(f"🔴 {tr('batch.task')} {item['index']}: {item['topic']}", expanded=False):
                        st.error(f"**{tr('batch.error')}**: {item['error']}")
                        with st.expander(tr("batch.error_detail")):
                            st.code(item['traceback'], language="python")


# ═══════════════════════════════════════════════════════════════════════════
# 顶层路由
# 外部调用的入口：render_output_preview
# 根据 batch_mode 决定走单视频还是批量模式
# 注意：render_single_output / render_batch_output 是向下兼容别名，不要删除
# ═══════════════════════════════════════════════════════════════════════════

render_output_preview = lambda pixelle_video, video_params: (
    _render_batch_output(pixelle_video, video_params)
    if video_params.get("batch_mode", False)
    else _render_single_output(pixelle_video, video_params)
)

# 向下兼容别名（其他文件可能 import 了这两个名字，不要删除）
render_single_output = _render_single_output
render_batch_output = _render_batch_output
