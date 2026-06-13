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
Output preview components for web UI (right column)
"""

import base64
import os
from pathlib import Path

import streamlit as st
from loguru import logger

from web.i18n import tr, get_language
from web.utils.async_helpers import run_async
from pixelle_video.models.progress import ProgressEvent
from pixelle_video.config import config_manager


def render_output_preview(pixelle_video, video_params):
    """Render output preview section (right column)"""
    # Check if batch mode
    is_batch = video_params.get("batch_mode", False)
    
    if is_batch:
        # Batch generation mode
        render_batch_output(pixelle_video, video_params)
    else:
        # Single video generation mode (original logic)
        render_single_output(pixelle_video, video_params)


def render_single_output(pixelle_video, video_params):
    """Render single video generation output (original logic, unchanged)"""
    # Extract parameters from video_params dict
    text = video_params.get("text", "")
    mode = video_params.get("mode", "generate")
    title = video_params.get("title")
    n_scenes = video_params.get("n_scenes", 5)
    split_mode = video_params.get("split_mode", "paragraph")
    bgm_path = video_params.get("bgm_path")
    bgm_volume = video_params.get("bgm_volume", 0.2)
    
    tts_mode = video_params.get("tts_inference_mode", "local")
    selected_voice = video_params.get("tts_voice")
    tts_speed = video_params.get("tts_speed")
    tts_workflow_key = video_params.get("tts_workflow")
    ref_audio_path = video_params.get("ref_audio")
    
    frame_template = video_params.get("frame_template")
    custom_values_for_video = video_params.get("template_params", {})
    workflow_key = video_params.get("media_workflow")
    api_video_params = video_params.get("api_video_params")
    prompt_prefix = video_params.get("prompt_prefix", "")
    
    with st.container(border=True):
        st.markdown(f"**{tr('section.video_generation')}**")

        if not config_manager.validate():
            st.warning(tr("settings.not_configured"))

        # ================================================================
        # 两步交互：AI生成 → 编辑确认 → 生成视频
        # ================================================================
        confirmed = st.session_state.get("st_confirmed", False)
        scenes_key = "st_scenes"

        # AI 生成分镜（固定脚本模式下显示，生成模式下也显示）
        if text.strip():
            st.markdown("---")
            st.markdown("**📋 分镜内容管理**")

            if st.button("🤖 AI 分析生成分镜", use_container_width=True, key="ai_gen_scenes"):
                with st.spinner("AI 分析文章中..."):
                    try:
                        from pixelle_video.utils.content_generators import generate_scene_breakdown
                        import uuid as _uuid
                        scenes = run_async(generate_scene_breakdown(
                            pixelle_video.llm, text
                        ))
                        # 为每个分镜分配唯一 ID，用于 widget key 隔离
                        for _s in scenes:
                            if "_uid" not in _s:
                                _s["_uid"] = str(_uuid.uuid4())[:8]
                        st.session_state[scenes_key] = scenes
                        st.session_state["st_confirmed"] = False
                        st.rerun()
                    except Exception as e:
                        st.error(f"AI 分析失败: {e}")

        # 显示可编辑的分镜内容
        scenes = st.session_state.get(scenes_key, [])
        if scenes:
            st.markdown("---")
            st.caption("以下内容可自由修改，修改后点「确认内容」")
            ref_key = "st_refs"
            if ref_key not in st.session_state:
                st.session_state[ref_key] = {}

            # 确保每个分镜都有唯一 ID
            import uuid as _uuid
            for _s in scenes:
                if "_uid" not in _s:
                    _s["_uid"] = str(_uuid.uuid4())[:8]

            edited = []
            for i, s in enumerate(scenes):
                uid = s["_uid"]  # 稳定的唯一标识
                st.markdown(f"**分镜 {i+1}**")

                c1, c2 = st.columns([1, 1])
                with c1:
                    ips = s.get("image_prompts", [s.get("image_prompt", "")])
                    if isinstance(ips, str):
                        ips = [ips]
                    ip_text = ips[0] if ips else ""
                    ip = st.text_area(f"画面提示词", ip_text, height=80,
                                      key=f"st_ip_{uid}", label_visibility="collapsed",
                                      placeholder=f"分镜{i+1}画面提示词")
                with c2:
                    nr = st.text_area(f"旁白", s.get("narration", ""), height=80,
                                      key=f"st_nr_{uid}", label_visibility="collapsed",
                                      placeholder=f"分镜{i+1}旁白")

                # 操作按钮行：插入 + 删除
                b1, b2, b3 = st.columns([1, 1, 2])
                with b1:
                    if st.button(f"＋ 插入到分镜{i+1}后", key=f"btn_insert_{uid}",
                                 use_container_width=True):
                        ss = st.session_state
                        cur = list(ss.get(scenes_key, []))
                        new_scene = {"image_prompt": "", "narration": "",
                                     "_uid": str(_uuid.uuid4())[:8]}
                        cur.insert(i + 1, new_scene)
                        ss[scenes_key] = cur
                        st.rerun()
                with b2:
                    if st.button(f"✕ 删除分镜{i+1}", key=f"btn_delete_{uid}",
                                 use_container_width=True):
                        ss = st.session_state
                        cur = list(ss.get(scenes_key, []))
                        if 0 <= i < len(cur):
                            removed = cur.pop(i)
                            ss[scenes_key] = cur
                            # 清除被删分镜的参考图
                            refs = ss.get(ref_key, {})
                            refs.pop(removed.get("_uid", ""), None)
                            ss[ref_key] = refs
                        st.rerun()

                # 参考图上传（key 基于 uid，不受位置变化影响）
                ref_col, del_col = st.columns([4, 1])
                with ref_col:
                    uploaded = st.file_uploader(
                        "📷 参考图（可选）", type=["jpg", "jpeg", "png", "webp"],
                        key=f"st_upload_{uid}", label_visibility="collapsed",
                        help="上传参考图以融入插画创作")
                    if uploaded and uploaded.size <= 10 * 1024 * 1024:
                        import base64
                        img_bytes = uploaded.read()
                        b64 = base64.b64encode(img_bytes).decode()
                        mime = uploaded.type
                        st.session_state[ref_key][uid] = f"data:{mime};base64,{b64}"
                    elif uploaded:
                        st.error("图片不能超过 10MB")

                with del_col:
                    if uid in st.session_state[ref_key]:
                        ref_data = st.session_state[ref_key][uid]
                        st.image(ref_data, width=60, caption="参考图")
                        if st.button("✕", key=f"st_delref_{uid}", help="删除参考图"):
                            del st.session_state[ref_key][uid]
                            st.rerun()

                edited.append({
                    "image_prompt": ip, "narration": nr,
                    "reference_image": st.session_state[ref_key].get(uid),
                    "_uid": uid
                })

            # 在末尾添加新分镜按钮
            if st.button("＋ 在末尾添加新分镜", key="btn_append_end",
                         help="在最后添加一个空白分镜", use_container_width=True):
                ss = st.session_state
                cur = list(ss.get(scenes_key, []))
                cur.append({"image_prompt": "", "narration": "",
                            "_uid": str(_uuid.uuid4())[:8]})
                ss[scenes_key] = cur
                st.rerun()

            cA, cB = st.columns([1, 1])
            with cA:
                if st.button("✅ 确认内容", use_container_width=True, type="primary", key="confirm_scenes"):
                    if all(e["image_prompt"].strip() and e["narration"].strip() for e in edited):
                        assembled = "\n\n".join(
                            f"{e['image_prompt']} | {e['narration']}" for e in edited
                        )
                        st.session_state["st_confirmed"] = True
                        st.session_state["st_assembled"] = assembled
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

            # 确认后显示可用的生成按钮
            if confirmed:
                assembled = st.session_state.get("st_assembled", "")
                text = assembled  # 覆盖原始 text
                st.success(f"✅ 已确认 {len(edited)} 个分镜，可以生成视频了")
                st.caption(f"已组装 {len(edited)} 段，每段格式：画面提示词｜旁白")

        # Generate Button
        if st.button("🎬 生成视频" if confirmed else tr("btn.generate"),
                     type="primary", use_container_width=True,
                     disabled=bool(scenes) and not confirmed):
            # Validate system configuration
            if not config_manager.validate():
                st.error(tr("settings.not_configured"))
                st.stop()
            
            # Validate input
            if not text:
                st.error(tr("error.input_required"))
                st.stop()

            from pixelle_video.utils.template_util import get_template_type
            if frame_template and get_template_type(frame_template) == "video" and not workflow_key:
                st.error(
                    "请选择视频生成工作流或 API 视频模型后再生成。"
                    if get_language() == "zh_CN"
                    else "Please select a video workflow or API video model before generating."
                )
                st.stop()
            
            # Show progress
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Record start time for generation
            import time
            start_time = time.time()
            
            try:
                # Progress callback to update UI
                def update_progress(event: ProgressEvent):
                    """Update progress bar and status text from ProgressEvent"""
                    # Translate event to user-facing message
                    if event.event_type == "frame_step":
                        # Frame step: "分镜 3/5 - 步骤 2/4: 生成插图"
                        action_key = f"progress.step_{event.action}"
                        action_text = tr(action_key)
                        message = tr(
                            "progress.frame_step",
                            current=event.frame_current,
                            total=event.frame_total,
                            step=event.step,
                            action=action_text
                        )
                    elif event.event_type == "processing_frame":
                        # Processing frame: "分镜 3/5"
                        message = tr(
                            "progress.frame",
                            current=event.frame_current,
                            total=event.frame_total
                        )
                    else:
                        # Simple events: use i18n key directly
                        message = tr(f"progress.{event.event_type}")
                    
                    # Append extra_info if available (e.g., batch progress)
                    if event.extra_info:
                        message = f"{message} - {event.extra_info}"
                    
                    status_text.text(message)
                    progress_bar.progress(min(int(event.progress * 100), 99))  # Cap at 99% until complete
                
                # Generate video (directly pass parameters)
                # Note: media_width and media_height are auto-determined from template
                video_params = {
                    "text": text,
                    "mode": mode,
                    "title": title if title else None,
                    "n_scenes": n_scenes,
                    "split_mode": split_mode,
                    "media_workflow": workflow_key,
                    "api_video_params": api_video_params,
                    "frame_template": frame_template,
                    "prompt_prefix": prompt_prefix,
                    "bgm_path": bgm_path,
                    "bgm_volume": bgm_volume if bgm_path else 0.2,
                    "progress_callback": update_progress,
                    "media_width": st.session_state.get('template_media_width'),
                    "media_height": st.session_state.get('template_media_height'),
                }
                # 参考图
                video_params["reference_images"] = st.session_state.get("st_ref_images", {})
                # Add TTS parameters based on mode
                video_params["tts_inference_mode"] = tts_mode
                if tts_mode == "local":
                    video_params["tts_voice"] = selected_voice
                    video_params["tts_speed"] = tts_speed
                else:  # comfyui
                    video_params["tts_workflow"] = tts_workflow_key
                    if ref_audio_path:
                        video_params["ref_audio"] = str(ref_audio_path)
                
                # Add custom template parameters if any
                if custom_values_for_video:
                    video_params["template_params"] = custom_values_for_video
                
                result = run_async(pixelle_video.generate_video(**video_params))
                
                # Calculate total generation time
                total_generation_time = time.time() - start_time
                
                progress_bar.progress(100)
                status_text.text(tr("status.success"))
                
                # Display success message
                st.success(tr("status.video_generated", path=result.video_path))
                
                st.markdown("---")
                
                # Video information (compact display)
                file_size_mb = result.file_size / (1024 * 1024)
                
                # Parse video size from template path
                from pixelle_video.utils.template_util import parse_template_size, resolve_template_path
                template_path = resolve_template_path(result.storyboard.config.frame_template)
                video_width, video_height = parse_template_size(template_path)
                
                info_text = (
                    f"⏱️ {tr('info.generation_time')} {total_generation_time:.1f}s   "
                    f"📦 {file_size_mb:.2f}MB   "
                    f"🎬 {len(result.storyboard.frames)}{tr('info.scenes_unit')}   "
                    f"📐 {video_width}x{video_height}"
                )
                st.caption(info_text)
                
                st.markdown("---")
                
                # Video preview
                if os.path.exists(result.video_path):
                    st.video(result.video_path)
                    
                    # Download button
                    with open(result.video_path, "rb") as video_file:
                        video_bytes = video_file.read()
                        video_filename = os.path.basename(result.video_path)
                        st.download_button(
                            label="⬇️ 下载视频" if get_language() == "zh_CN" else "⬇️ Download Video",
                            data=video_bytes,
                            file_name=video_filename,
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


def render_batch_output(pixelle_video, video_params):
    """Render batch generation output (minimal, redirect to History)"""
    topics = video_params.get("topics", [])
    
    with st.container(border=True):
        st.markdown(f"**{tr('batch.section_generation')}**")
        
        # Check if topics are provided
        if not topics:
            st.warning(tr("batch.no_topics"))
            return
        
        # Check system configuration
        if not config_manager.validate():
            st.warning(tr("settings.not_configured"))
            return
        
        batch_count = len(topics)
        
        # Display batch info
        st.info(tr("batch.prepare_info", count=batch_count))
        
        # Estimated time (optional)
        estimated_minutes = batch_count * 3  # Assume 3 minutes per video
        st.caption(tr("batch.estimated_time", minutes=estimated_minutes))
        
        # Generate button with batch semantics
        if st.button(
            tr("batch.generate_button", count=batch_count),
            type="primary",
            use_container_width=True,
            help=tr("batch.generate_help")
        ):
            # Prepare shared config
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
            # Add TTS parameters based on mode (only add non-None values)
            if shared_config["tts_inference_mode"] == "local":
                tts_voice = video_params.get("tts_voice")
                tts_speed = video_params.get("tts_speed")
                if tts_voice:
                    shared_config["tts_voice"] = tts_voice
                if tts_speed:
                    shared_config["tts_speed"] = tts_speed
            else:  # comfyui
                tts_workflow = video_params.get("tts_workflow")
                if tts_workflow:
                    shared_config["tts_workflow"] = tts_workflow
                ref_audio = video_params.get("ref_audio")
                if ref_audio:
                    shared_config["ref_audio"] = str(ref_audio)
            
            # Add template parameters
            if video_params.get("template_params"):
                shared_config["template_params"] = video_params["template_params"]
            
            # UI containers
            overall_progress_container = st.container()
            current_task_container = st.container()
            
            # Overall progress UI
            overall_progress_bar = overall_progress_container.progress(0)
            overall_status = overall_progress_container.empty()
            
            # Current task progress UI
            current_task_title = current_task_container.empty()
            current_task_progress = current_task_container.progress(0)
            current_task_status = current_task_container.empty()
            
            # Overall progress callback
            def update_overall_progress(current, total, topic):
                progress = (current - 1) / total
                overall_progress_bar.progress(progress)
                overall_status.markdown(
                    f"📊 **{tr('batch.overall_progress')}**: {current}/{total} ({int(progress * 100)}%)"
                )
            
            # Single task progress callback factory
            def make_task_progress_callback(task_idx, topic):
                def callback(event: ProgressEvent):
                    # Display current task title
                    current_task_title.markdown(f"🎬 **{tr('batch.current_task')} {task_idx}**: {topic}")
                    
                    # Update task detailed progress
                    if event.event_type == "frame_step":
                        action_key = f"progress.step_{event.action}"
                        action_text = tr(action_key)
                        message = tr(
                            "progress.frame_step",
                            current=event.frame_current,
                            total=event.frame_total,
                            step=event.step,
                            action=action_text
                        )
                    elif event.event_type == "processing_frame":
                        message = tr(
                            "progress.frame",
                            current=event.frame_current,
                            total=event.frame_total
                        )
                    else:
                        message = tr(f"progress.{event.event_type}")
                    
                    current_task_progress.progress(event.progress)
                    current_task_status.text(message)
                
                return callback
            
            # Execute batch generation
            from web.utils.batch_manager import SimpleBatchManager
            import time
            
            batch_manager = SimpleBatchManager()
            start_time = time.time()
            
            batch_result = batch_manager.execute_batch(
                pixelle_video=pixelle_video,
                topics=topics,
                shared_config=shared_config,
                overall_progress_callback=update_overall_progress,
                task_progress_callback_factory=make_task_progress_callback
            )
            
            total_time = time.time() - start_time
            
            # Clear progress displays
            overall_progress_bar.progress(1.0)
            overall_status.markdown(f"✅ **{tr('batch.completed')}**")
            current_task_title.empty()
            current_task_progress.empty()
            current_task_status.empty()
            
            # Display results summary
            st.markdown("---")
            st.markdown(f"**{tr('batch.results_title')}**")
            
            col1, col2, col3 = st.columns(3)
            col1.metric(tr("batch.total"), batch_result["total_count"])
            col2.metric(f"✅ {tr('batch.success')}", batch_result["success_count"])
            col3.metric(f"❌ {tr('batch.failed')}", batch_result["failed_count"])
            
            # Display total time
            minutes = int(total_time / 60)
            seconds = int(total_time % 60)
            st.caption(f"⏱️ {tr('batch.total_time')}: {minutes}{tr('batch.minutes')}{seconds}{tr('batch.seconds')}")
            
            # Redirect to History page
            st.markdown("---")
            st.success(tr("batch.success_message"))
            st.info(tr("batch.view_in_history"))
            
            # Button to go to History page using JavaScript URL navigation
            st.markdown(
                f"""
                <a href="/History" target="_blank">
                    <button style="
                        width: 100%;
                        padding: 0.5rem 1rem;
                        background-color: white;
                        color: rgb(49, 51, 63);
                        border: 1px solid rgba(49, 51, 63, 0.2);
                        border-radius: 0.5rem;
                        cursor: pointer;
                        font-size: 1rem;
                        font-weight: 400;
                        text-align: center;
                    ">
                        📚 {tr('batch.goto_history')}
                    </button>
                </a>
                """,
                unsafe_allow_html=True
            )
            
            # Show failed tasks if any
            if batch_result["errors"]:
                st.markdown("---")
                st.markdown(f"#### {tr('batch.failed_list')}")
                
                for item in batch_result["errors"]:
                    with st.expander(f"🔴 {tr('batch.task')} {item['index']}: {item['topic']}", expanded=False):
                        st.error(f"**{tr('batch.error')}**: {item['error']}")
                        
                        # Detailed error (collapsed)
                        with st.expander(tr("batch.error_detail")):
                            st.code(item['traceback'], language="python")
    
