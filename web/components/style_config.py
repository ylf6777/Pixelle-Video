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
Style configuration components for web UI (middle column)
"""

import os
import base64
from pathlib import Path

import streamlit as st
from loguru import logger

from web.i18n import tr, get_language
from web.utils.async_helpers import run_async
from web.utils.streamlit_helpers import check_and_warn_selfhost_workflow
from web.pipelines.api_workflows import (
    list_api_media_workflows,
    list_local_media_workflows,
    render_api_video_controls,
    workflow_select_help,
    workflow_source_help,
    workflow_source_label,
)
from pixelle_video.config import config_manager
from pixelle_video.tts_voices import EDGE_TTS_VOICES, get_voice_display_name
from web.prompt_templates import (
    CUSTOM_TEMPLATE_KEY,
    check_edit_permission,
    get_template_binding,
    get_template_choices,
    get_template_name,
    get_template_prompt,
    is_template_locked,
)


def is_api_workflow(workflow_key: str | None) -> bool:
    """Return True for direct provider workflow keys such as api/dashscope/xxx."""
    return bool(workflow_key and workflow_key.startswith("api/"))


def render_style_config(pixelle_video):
    """Render style configuration section (middle column)"""
    # TTS Section (moved from left column)
    # ====================================================================
    with st.container(border=True):
        st.markdown(f"**{tr('section.tts')}**")
        
        with st.expander(tr("help.feature_description"), expanded=False):
            st.markdown(f"**{tr('help.what')}**")
            st.markdown(tr("tts.what"))
            st.markdown(f"**{tr('help.how')}**")
            st.markdown(tr("tts.how"))
        
        # Get TTS config
        comfyui_config = config_manager.get_comfyui_config()
        tts_config = comfyui_config["tts"]
        
        # Inference mode selection
        tts_mode = st.radio(
            tr("tts.inference_mode"),
            ["local", "comfyui"],
            horizontal=True,
            format_func=lambda x: tr(f"tts.mode.{x}"),
            index=0 if tts_config.get("inference_mode", "local") == "local" else 1,
            key="tts_inference_mode"
        )
        
        # Show hint based on mode
        if tts_mode == "local":
            st.caption(tr("tts.mode.local_hint"))
        else:
            st.caption(tr("tts.mode.comfyui_hint"))
        
        # ================================================================
        # Local Mode UI
        # ================================================================
        if tts_mode == "local":
            # Get saved voice from config
            local_config = tts_config.get("local", {})
            saved_voice = local_config.get("voice", "zh-CN-YunjianNeural")
            saved_speed = local_config.get("speed", 1.2)

            # ---- TTS 模板绑定：读取已激活的风格模板的语音/语速设置 ----
            _tts_bound_voice = None
            _tts_bound_speed = None
            _tts_active_key = st.session_state.get("_style_template_active", "") or st.session_state.get("style_template_key_image", "")
            if _tts_active_key and _tts_active_key != CUSTOM_TEMPLATE_KEY:
                _tts_binding = get_template_binding(_tts_active_key)
                if _tts_binding:
                    _tts_bound_voice = _tts_binding.tts_voice
                    _tts_bound_speed = _tts_binding.tts_speed

            _tts_locked = bool(_tts_bound_voice)
            if _tts_bound_voice:
                saved_voice = _tts_bound_voice
            if _tts_bound_speed is not None:
                saved_speed = _tts_bound_speed

            # Build voice options with i18n
            voice_options = []
            voice_ids = []
            default_voice_index = 0

            for idx, voice_config in enumerate(EDGE_TTS_VOICES):
                voice_id = voice_config["id"]
                display_name = get_voice_display_name(voice_id, tr, get_language())
                voice_options.append(display_name)
                voice_ids.append(voice_id)

                # Set default index if matches saved voice
                if voice_id == saved_voice:
                    default_voice_index = idx

            # ---- 模板启动后强制同步 TTS widget 状态 ----
            # Streamlit widget 有自己的内部状态，index/value 参数在 widget 状态存在时被忽略。
            # 模板绑定切换后必须直接写入 st.session_state 才能让锁定值真正生效。
            if _tts_locked and _tts_bound_voice:
                _bound_display = get_voice_display_name(_tts_bound_voice, tr, get_language())
                if _bound_display in voice_options:
                    st.session_state["tts_local_voice"] = _bound_display
                if _tts_bound_speed is not None:
                    st.session_state["tts_local_speed"] = float(_tts_bound_speed)
            
            # Two-column layout: Voice | Speed
            voice_col, speed_col = st.columns([1, 1])
            
            with voice_col:
                # 模板绑定提示
                if _tts_locked:
                    st.caption("🔒 由风格模板锁定")
                # Voice selector（locked 时不传 index，由 session_state 驱动）
                _voice_kwargs = dict(
                    label=tr("tts.voice_selector"),
                    options=voice_options,
                    disabled=_tts_locked,
                    key="tts_local_voice",
                )
                if not _tts_locked:
                    _voice_kwargs["index"] = default_voice_index
                selected_voice_display = st.selectbox(**_voice_kwargs)
                
                # Get actual voice ID
                selected_voice_index = voice_options.index(selected_voice_display)
                selected_voice = voice_ids[selected_voice_index]
            
            with speed_col:
                # 模板绑定提示
                if _tts_locked:
                    st.caption("🔒 由风格模板锁定")
                # Speed slider（locked 时不传 value，由 session_state 驱动）
                _speed_kwargs = dict(
                    label=tr("tts.speed"),
                    min_value=0.5,
                    max_value=2.0,
                    step=0.1,
                    format="%.1fx",
                    disabled=_tts_locked,
                    key="tts_local_speed",
                )
                if not _tts_locked:
                    _speed_kwargs["value"] = saved_speed
                tts_speed = st.slider(**_speed_kwargs)
                st.caption(tr("tts.speed_label", speed=f"{tts_speed:.1f}"))
            
            # Variables for video generation
            tts_workflow_key = None
            ref_audio_path = None
        
        # ================================================================
        # ComfyUI Mode UI
        # ================================================================
        else:  # comfyui mode
            # Get available TTS workflows
            tts_workflows = pixelle_video.tts.list_workflows()
            
            # Build options for selectbox
            tts_workflow_options = [wf["display_name"] for wf in tts_workflows]
            tts_workflow_keys = [wf["key"] for wf in tts_workflows]
            
            # Default to saved workflow if exists
            default_tts_index = 0
            saved_tts_workflow = tts_config.get("comfyui", {}).get("default_workflow")
            if saved_tts_workflow and saved_tts_workflow in tts_workflow_keys:
                default_tts_index = tts_workflow_keys.index(saved_tts_workflow)
            
            tts_workflow_display = st.selectbox(
                "TTS Workflow",
                tts_workflow_options if tts_workflow_options else ["No TTS workflows found"],
                index=default_tts_index,
                label_visibility="collapsed",
                key="tts_workflow_select"
            )
            
            # Get the actual workflow key
            if tts_workflow_options:
                tts_selected_index = tts_workflow_options.index(tts_workflow_display)
                tts_workflow_key = tts_workflow_keys[tts_selected_index]
            else:
                tts_workflow_key = "selfhost/tts_edge.json"  # fallback
            
            # Check and warn for selfhost TTS workflow (auto popup if not confirmed)
            check_and_warn_selfhost_workflow(tts_workflow_key)
            
            # Reference audio upload (optional, for voice cloning)
            ref_audio_file = st.file_uploader(
                tr("tts.ref_audio"),
                type=["mp3", "wav", "flac", "m4a", "aac", "ogg"],
                help=tr("tts.ref_audio_help"),
                key="ref_audio_upload"
            )
            
            # Save uploaded ref_audio to temp file if provided
            ref_audio_path = None
            if ref_audio_file is not None:
                # Audio preview player (directly play uploaded file)
                st.audio(ref_audio_file)
                
                # Save to temp directory
                temp_dir = Path("temp")
                temp_dir.mkdir(exist_ok=True)
                ref_audio_path = temp_dir / f"ref_audio_{ref_audio_file.name}"
                with open(ref_audio_path, "wb") as f:
                    f.write(ref_audio_file.getbuffer())
            
            # Variables for video generation
            selected_voice = None
            tts_speed = None
        
        # ================================================================
        # TTS Preview (works for both modes)
        # ================================================================
        with st.expander(tr("tts.preview_title"), expanded=False):
            # Preview text input
            preview_text = st.text_input(
                tr("tts.preview_text"),
                value="大家好，这是一段测试语音。",
                placeholder=tr("tts.preview_text_placeholder"),
                key="tts_preview_text"
            )
            
            # Preview button
            if st.button(tr("tts.preview_button"), key="preview_tts", use_container_width=True):
                with st.spinner(tr("tts.previewing")):
                    try:
                        # Build TTS params based on mode
                        tts_params = {
                            "text": preview_text,
                            "inference_mode": tts_mode
                        }
                        
                        if tts_mode == "local":
                            tts_params["voice"] = selected_voice
                            tts_params["speed"] = tts_speed
                        else:  # comfyui
                            tts_params["workflow"] = tts_workflow_key
                            if ref_audio_path:
                                tts_params["ref_audio"] = str(ref_audio_path)
                        
                        audio_path = run_async(pixelle_video.tts(**tts_params))
                        
                        # Play the audio
                        if audio_path:
                            st.success(tr("tts.preview_success"))
                            if os.path.exists(audio_path):
                                st.audio(audio_path, format="audio/mp3")
                            elif audio_path.startswith('http'):
                                st.audio(audio_path)
                            else:
                                st.error("Failed to generate preview audio")
                            
                            # Show file path
                            st.caption(f"📁 {audio_path}")
                        else:
                            st.error("Failed to generate preview audio")
                    except Exception as e:
                        st.error(tr("tts.preview_failed", error=str(e)))
                        logger.exception(e)
    
    # ====================================================================
    # Storyboard Template Section
    # ====================================================================
    
    def get_template_preview_path(template_path: str, language: str = "zh_CN") -> str:
        """
        Get the preview image path for a template based on language.
        
        Args:
            template_path: Template path like "1080x1920/image_default.html"
            language: Language code, either "zh_CN" or "en"
            
        Returns:
            Path to preview image in docs/images/
        """
        # Extract size and template name from path
        # e.g., "1080x1920/image_default.html" -> size="1080x1920", name="image_default"
        path_parts = template_path.split('/')
        if len(path_parts) >= 2:
            size = path_parts[0]  # e.g., "1080x1920"
            template_file = path_parts[1]  # e.g., "image_default.html"
            template_name = template_file.replace('.html', '')  # e.g., "image_default"
            
            # Build preview image path
            # Format: docs/images/{size}/{template_name}.jpg or {template_name}_en.jpg
            # Chinese uses Chinese preview, all other languages use English preview for better i18n
            suffix = "" if language == "zh_CN" else "_en"
            
            # Try different image extensions
            for ext in ['.jpg', '.png']:
                preview_path = f"docs/images/{size}/{template_name}{suffix}{ext}"
                if os.path.exists(preview_path):
                    return preview_path
            
            # Fallback: try without language suffix (for templates with only one version)
            for ext in ['.jpg', '.png']:
                preview_path = f"docs/images/{size}/{template_name}{ext}"
                if os.path.exists(preview_path):
                    return preview_path
        
        # If no preview found, return empty string
        return ""
    
    with st.container(border=True):
        st.markdown(f"**{tr('section.template')}**")

        # ---- 当前风格模板可视化指示 ----
        _active_style_key = st.session_state.get("_style_template_active", "") or st.session_state.get("style_template_key_image", "")
        if _active_style_key and _active_style_key != CUSTOM_TEMPLATE_KEY:
            _active_name = get_template_name(_active_style_key, tr)
            st.caption(f"🎨 当前风格模板：**{_active_name}**")

        with st.expander(tr("help.feature_description"), expanded=False):
            st.markdown(f"**{tr('help.what')}**")
            st.markdown(tr("template.what"))
            st.markdown(f"**{tr('help.how')}**")
            st.markdown(tr("template.how"))
        
        # Template preview link (based on language)
        current_lang = get_language()
        
        # Import template utilities
        from pixelle_video.utils.template_util import get_templates_grouped_by_size_and_type, get_template_type
        
        # Template type selector
        st.markdown(f"**{tr('template.type_selector')}**")
        
        template_type_options = {
            'static': tr('template.type.static'),
            'image': tr('template.type.image'),
            'video': tr('template.type.video'),
        }
        
        # Radio buttons in horizontal layout
        selected_template_type = st.radio(
            tr('template.type_selector'),
            options=list(template_type_options.keys()),
            format_func=lambda x: template_type_options[x],
            index=1,  # Default to 'image'
            key="template_type_selector",
            label_visibility="collapsed",
            horizontal=True
        )
        
        # Display hint based on selected type (below radio buttons)
        if selected_template_type == 'static':
            st.info(tr('template.type.static_hint'))
        elif selected_template_type == 'image':
            st.info(tr('template.type.image_hint'))
        elif selected_template_type == 'video':
            st.info(tr('template.type.video_hint'))
        
        # Get templates grouped by size, filtered by selected type
        grouped_templates = get_templates_grouped_by_size_and_type(selected_template_type)
        
        if not grouped_templates:
            st.warning(f"No {template_type_options[selected_template_type]} templates found. Please select a different type or add templates.")
            st.stop()
        
        # Build orientation i18n mapping
        ORIENTATION_I18N = {
            'portrait': tr('orientation.portrait'),
            'landscape': tr('orientation.landscape'),
            'square': tr('orientation.square')
        }
        
        # Get default template from config
        template_config = pixelle_video.config.get("template", {})
        config_default_template = template_config.get("default_template", "1080x1920/image_default.html")

        # Backward compatibility
        if config_default_template == "1080x1920/default.html":
            config_default_template = "1080x1920/image_default.html"
        
        # Determine type-specific default template
        type_default_templates = {
            'static': '1080x1920/static_default.html',
            'image': '1080x1920/image_default.html',
            'video': '1080x1920/video_default.html',
        }
        type_specific_default = type_default_templates.get(selected_template_type, config_default_template)
        
        # Initialize selected template in session state if not exists
        if 'selected_template' not in st.session_state:
            st.session_state['selected_template'] = type_specific_default
        
        # Track last selected template type to detect type changes
        last_template_type = st.session_state.get('last_template_type', None)
        if last_template_type != selected_template_type:
            # Template type changed, reset to type-specific default
            st.session_state['selected_template'] = type_specific_default
            st.session_state['last_template_type'] = selected_template_type

        # ---- 风格模板 ↔ 画面模板自动绑定 ----
        _bound_template = None
        _fixed_params = None
        # 优先读已激活模板，否则回退到下拉选中值
        _tmpl_active_key = st.session_state.get("_style_template_active", "")
        if not _tmpl_active_key:
            _tmpl_active_key = st.session_state.get("style_template_key_image", "")
        if _tmpl_active_key and _tmpl_active_key != CUSTOM_TEMPLATE_KEY:
            _binding = get_template_binding(_tmpl_active_key)
            if _binding and _binding.frame_template:
                _bound_template = _binding.frame_template
                _fixed_params = _binding.fixed_params

        if _bound_template:
            st.session_state['selected_template'] = _bound_template
            # 同步模板类型（绑定的都是 image 模板）
            if st.session_state.get('last_template_type') != 'image':
                st.session_state['last_template_type'] = 'image'
                selected_template_type = 'image'

        # Collect size groups and prepare tabs
        size_groups = []
        size_labels = []
        
        for size, templates in grouped_templates.items():
            if not templates:
                continue
            
            # Filter templates to only include those with proper naming convention
            # Only show templates starting with static_, image_, or video_
            valid_templates = []
            for template in templates:
                template_name = template.display_info.name
                if template_name.startswith(('static_', 'image_', 'video_')):
                    valid_templates.append(template)
            
            # Skip if no valid templates after filtering
            if not valid_templates:
                continue
            
            # Separate templates into two groups: with preview and without preview
            templates_with_preview = []
            templates_without_preview = []
            
            for template in valid_templates:
                preview_path = get_template_preview_path(template.template_path, current_lang)
                if preview_path and os.path.exists(preview_path):
                    templates_with_preview.append(template)
                else:
                    templates_without_preview.append(template)
            
            # Skip this group if no templates at all
            if not templates_with_preview and not templates_without_preview:
                continue
            
            # Combine: templates with preview first, then without preview
            all_templates = templates_with_preview + templates_without_preview
            
            # Get orientation from first template in group
            orientation = ORIENTATION_I18N.get(
                all_templates[0].display_info.orientation, 
                all_templates[0].display_info.orientation
            )
            width = all_templates[0].display_info.width
            height = all_templates[0].display_info.height
            
            # Create tab label
            tab_label = f"{orientation} {width}×{height}"
            size_labels.append(tab_label)
            size_groups.append(all_templates)
        
        # Create tabs for each size group (wrapped in expander)
        with st.expander(tr("template.gallery_view"), expanded=True):
            if size_groups:
                tabs = st.tabs(size_labels)
                
                for tab, all_templates in zip(tabs, size_groups):
                    with tab:
                        # Create grid layout (5 columns)
                        num_cols = 5
                        cols = st.columns(num_cols)
                        
                        for idx, template in enumerate(all_templates):
                            col_idx = idx % num_cols
                            with cols[col_idx]:
                                # Get preview image path
                                preview_path = get_template_preview_path(template.template_path, current_lang)
                                
                                # Display preview image or placeholder
                                if preview_path and os.path.exists(preview_path):
                                    st.image(preview_path, use_container_width=True)
                                else:
                                    # Placeholder for templates without preview (fixed height, compact layout)
                                    st.markdown(
                                        f"""
                                        <div style="
                                            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                                            height: 150px;
                                            display: flex;
                                            align-items: center;
                                            justify-content: center;
                                            text-align: center;
                                            border-radius: 8px;
                                            color: white;
                                            margin-bottom: 15px;
                                            padding: 10px;
                                        ">
                                            <div style="
                                                font-size: 14px; 
                                                opacity: 0.95;
                                                overflow: hidden;
                                                text-overflow: ellipsis;
                                                display: -webkit-box;
                                                -webkit-line-clamp: 5;
                                                -webkit-box-orient: vertical;
                                                word-break: break-all;
                                            ">{template.display_info.name}</div>
                                        </div>
                                        """,
                                        unsafe_allow_html=True
                                    )
                                
                                # Select button (unified label)
                                is_selected = (st.session_state['selected_template'] == template.template_path)
                                button_label = f"{tr('template.selected')}" if is_selected else tr('template.select_button')
                                button_type = "primary" if is_selected else "secondary"
                                
                                if st.button(
                                    button_label,
                                    key=f"template_{template.template_path}",
                                    use_container_width=True,
                                    type=button_type,
                                ):
                                    st.session_state['selected_template'] = template.template_path
                                    st.rerun()
            else:
                st.warning(tr("template.no_templates_with_preview"))
            
            # Display selected template name (inside expander, below tabs)
            frame_template = st.session_state['selected_template']
            
            # Find the selected template's display name
            selected_template_name = None
            for size, templates in grouped_templates.items():
                for template in templates:
                    if template.template_path == frame_template:
                        selected_template_name = template.display_info.name
                        break
                if selected_template_name:
                    break
            
        if selected_template_name:
            st.info(f"📋 {tr('template.selected_template')}: **{selected_template_name}**")
        

        # Display video size from template
        from pixelle_video.utils.template_util import parse_template_size
        video_width, video_height = parse_template_size(frame_template)
        st.caption(tr("template.video_size_info", width=video_width, height=video_height))
        
        # Custom template parameters (for video generation)
        from pixelle_video.services.frame_html import HTMLFrameGenerator
        # Resolve template path to support both data/templates/ and templates/
        from pixelle_video.utils.template_util import resolve_template_path
        template_path_for_params = resolve_template_path(frame_template)
        generator_for_params = HTMLFrameGenerator(template_path_for_params)
        custom_params_for_video = generator_for_params.parse_template_parameters()
        
        # Get media size from template (for image/video generation)
        media_width, media_height = generator_for_params.get_media_size()
        st.session_state['template_media_width'] = media_width
        st.session_state['template_media_height'] = media_height
        
        # Detect template media type
        from pixelle_video.utils.template_util import get_template_type
        
        template_name = Path(frame_template).name
        template_media_type = get_template_type(template_name)
        template_requires_media = (template_media_type in ["image", "video"])
        
        # Store in session state for workflow filtering
        st.session_state['template_media_type'] = template_media_type
        st.session_state['template_requires_media'] = template_requires_media
        
        # Backward compatibility
        st.session_state['template_requires_image'] = (template_media_type == "image")
        
        custom_values_for_video = {}
        # 检查是否有风格模板绑定的固定参数
        _has_bound_params = bool(_fixed_params)
        # 模板启动后强制同步/清理 template param 的 widget 状态
        _prev_bound = st.session_state.get("_prev_has_bound_params", False)
        if _has_bound_params and _fixed_params:
            for _pname, _pval in _fixed_params.items():
                _wkey = f"video_custom_{_pname}"
                st.session_state[_wkey] = _pval
        elif _prev_bound and not _has_bound_params:
            # 从绑定切到自定义：清除所有 video_custom_* 和 preview_* widget 状态
            _dead_keys = [k for k in st.session_state if k.startswith("video_custom_")]
            for _k in _dead_keys:
                if _k in st.session_state:
                    del st.session_state[_k]
        st.session_state["_prev_has_bound_params"] = _has_bound_params
        if custom_params_for_video:
            if _has_bound_params:
                st.markdown("🔒 " + tr("template.custom_parameters"))
            else:
                st.markdown("📝 " + tr("template.custom_parameters"))

            # Render custom parameter inputs in 2 columns
            video_custom_col1, video_custom_col2 = st.columns(2)

            param_items = list(custom_params_for_video.items())
            mid_point = (len(param_items) + 1) // 2

            def _render_param(param_name, config):
                param_type = config['type']
                # 固定参数覆盖默认值
                default = _fixed_params.get(param_name, config['default']) if _has_bound_params else config['default']
                label = config['label']
                is_fixed = _has_bound_params and param_name in (_fixed_params or {})
                disabled = is_fixed

                _wkey = f"video_custom_{param_name}"
                if param_type == 'text':
                    _kwargs = dict(label=label, disabled=disabled, key=_wkey)
                    if not is_fixed:
                        _kwargs["value"] = default
                    custom_values_for_video[param_name] = st.text_input(**_kwargs)
                elif param_type == 'number':
                    _kwargs = dict(label=label, disabled=disabled, key=_wkey)
                    if not is_fixed:
                        _kwargs["value"] = default
                    custom_values_for_video[param_name] = st.number_input(**_kwargs)
                elif param_type == 'color':
                    _kwargs = dict(label=label, disabled=disabled, key=_wkey)
                    if not is_fixed:
                        _kwargs["value"] = default
                    custom_values_for_video[param_name] = st.color_picker(**_kwargs)
                elif param_type == 'bool':
                    _kwargs = dict(label=label, disabled=disabled, key=_wkey)
                    if not is_fixed:
                        _kwargs["value"] = default
                    custom_values_for_video[param_name] = st.checkbox(**_kwargs)

            # Left column parameters
            with video_custom_col1:
                for param_name, config in param_items[:mid_point]:
                    _render_param(param_name, config)

            # Right column parameters
            with video_custom_col2:
                for param_name, config in param_items[mid_point:]:
                    _render_param(param_name, config)
        
        # Template preview expander
        with st.expander(tr("template.preview_title"), expanded=False):
            col1, col2 = st.columns(2)

            with col1:
                preview_title = st.text_input(
                    tr("template.preview_param_title"),
                    value="",
                    placeholder="留空由 AI 自动生成",
                    key="preview_title"
                )
                preview_image = st.text_input(
                    tr("template.preview_param_image"),
                    value="resources/example.png",
                    help=tr("template.preview_image_help"),
                    key="preview_image"
                )

            with col2:
                preview_text = st.text_area(
                    tr("template.preview_param_text"),
                    value="",
                    placeholder="留空由 AI 自动生成",
                    height=100,
                    key="preview_text"
                )
            
            # Info: Size is auto-determined from template
            from pixelle_video.utils.template_util import parse_template_size, resolve_template_path
            template_width, template_height = parse_template_size(resolve_template_path(frame_template))
            st.info(f"📐 {tr('template.size_info')}: {template_width} × {template_height}")
            
            # Preview button
            if st.button(tr("template.preview_button"), key="btn_preview_template", use_container_width=True):
                with st.spinner(tr("template.preview_generating")):
                    try:
                        from pixelle_video.services.frame_html import HTMLFrameGenerator

                        # Use the currently selected template (size is auto-parsed)
                        from pixelle_video.utils.template_util import resolve_template_path
                        template_path = resolve_template_path(frame_template)
                        generator = HTMLFrameGenerator(template_path)
                        
                        # Build ext dict with auto-injected parameters (same as FrameProcessor)
                        ext = {
                            "index": 1,  # Preview uses index 1
                        }
                        
                        # Add custom parameters from user input
                        if custom_values_for_video:
                            ext.update(custom_values_for_video)
                        
                        # Generate preview
                        preview_path = run_async(generator.generate_frame(
                            title=preview_title,
                            text=preview_text,
                            image=preview_image,
                            ext=ext
                        ))
                        
                        # Display preview
                        if preview_path:
                            st.success(tr("template.preview_success"))
                            st.image(
                                preview_path, 
                                caption=tr("template.preview_caption", template=frame_template),
                            )
                            
                            # Show file path
                            st.caption(f"📁 {preview_path}")
                        else:
                            st.error("Failed to generate preview")
                            
                    except Exception as e:
                        st.error(tr("template.preview_failed", error=str(e)))
                        logger.exception(e)
    
    # ====================================================================
    # Media Generation Section (conditional based on template)
    # ====================================================================
    # Check if current template requires media generation
    template_media_type = st.session_state.get('template_media_type', 'image')
    template_requires_media = st.session_state.get('template_requires_media', True)
    
    api_video_params = {}

    if template_requires_media:
        comfyui_config = config_manager.get_comfyui_config()
        media_width = st.session_state.get('template_media_width')
        media_height = st.session_state.get('template_media_height')
        media_config_key = "video" if template_media_type == "video" else "image"
        saved_workflow = comfyui_config.get(media_config_key, {}).get("default_workflow") or ""
        workflow_key = None

        with st.container(border=True):
            section_title = tr('section.video') if template_media_type == "video" else tr('section.image')
            st.markdown(f"**{section_title}**")
        
            # 1. ComfyUI Workflow selection
            with st.expander(tr("help.feature_description"), expanded=False):
                st.markdown(f"**{tr('help.what')}**")
                if template_media_type == "video":
                    st.markdown(tr("style.video_workflow_what"))
                else:
                    st.markdown(tr("style.workflow_what"))
                st.markdown(f"**{tr('help.how')}**")
                if template_media_type == "video":
                    st.markdown(tr("style.video_workflow_how"))
                else:
                    st.markdown(tr("style.workflow_how"))

            source_options = ["runninghub", "selfhost", "api"]
            default_source_index = 0
            for index, source in enumerate(source_options):
                if saved_workflow.startswith(f"{source}/"):
                    default_source_index = index
                    break
            source_key = "standard_video_workflow_source" if template_media_type == "video" else "standard_image_workflow_source"
            workflow_source = st.radio(
                "生成来源" if get_language() == "zh_CN" else "Generation source",
                source_options,
                index=default_source_index,
                format_func=workflow_source_label,
                horizontal=True,
                key=source_key,
                help=workflow_source_help("快速创作媒体生成" if get_language() == "zh_CN" else "Quick Create media generation"),
            )

            if workflow_source == "api":
                if template_media_type == "video":
                    workflows = list_api_media_workflows(
                        pixelle_video,
                        "video",
                        required_adapter_abilities=["text_to_video"],
                        verified_only=True,
                    )
                else:
                    workflows = list_api_media_workflows(pixelle_video, "image")
            elif template_media_type == "video":
                workflows = list_local_media_workflows(
                    pixelle_video,
                    "video",
                    workflow_source,
                    key_contains="video_",
                )
            else:
                workflows = list_local_media_workflows(pixelle_video, "image", workflow_source)
        
            # Build options for selectbox
            # Display: "image_flux.json - Runninghub"
            # Value: "runninghub/image_flux.json"
            workflow_options = [wf["display_name"] for wf in workflows]
            workflow_keys = [wf["key"] for wf in workflows]
        
            # Default to first option (should be runninghub by sorting)
            default_workflow_index = 0
        
            # If user has a saved preference in config, try to match it
            if saved_workflow and saved_workflow in workflow_keys:
                default_workflow_index = workflow_keys.index(saved_workflow)
        
            workflow_display = st.selectbox(
                "Workflow" if workflow_source != "api" else ("API 模型" if get_language() == "zh_CN" else "API model"),
                workflow_options if workflow_options else ["No workflows found"],
                index=default_workflow_index,
                label_visibility="visible",
                key=f"{source_key}_select",
                help=workflow_select_help(),
            )
        
            # Get the actual workflow key (e.g., "runninghub/image_flux.json")
            if workflow_options:
                workflow_selected_index = workflow_options.index(workflow_display)
                workflow_key = workflow_keys[workflow_selected_index]
                workflow_info = workflows[workflow_selected_index]
            else:
                workflow_key = None
                workflow_info = None
                if workflow_source == "api" and template_media_type == "video":
                    st.warning(
                        "没有找到已验证的 API 文生视频模型，请先配置 DashScope/Seedance 等提供商，或切换到本地/RunningHub 工作流。"
                        if get_language() == "zh_CN"
                        else "No verified API text-to-video model found. Configure a provider or switch to local/RunningHub workflows."
                    )
                else:
                    st.warning(
                        "当前来源下没有可用工作流。"
                        if get_language() == "zh_CN"
                        else "No workflow is available for the selected source."
                    )
            
            # Check and warn for selfhost media workflow (auto popup if not confirmed)
            if workflow_key and not is_api_workflow(workflow_key):
                check_and_warn_selfhost_workflow(workflow_key)
            
            # Display media size info (read-only)
            if template_media_type == "video":
                size_info_text = tr('style.video_size_info', width=media_width, height=media_height)
            else:
                size_info_text = tr('style.image_size_info', width=media_width, height=media_height)
            st.info(f"📐 {size_info_text}")

            if template_media_type == "video" and media_width and media_height:
                default_video_ratio = "1:1" if media_width == media_height else ("9:16" if media_height > media_width else "16:9")
            else:
                default_video_ratio = "9:16"

            if template_media_type == "video" and is_api_workflow(workflow_key):
                api_video_params = render_api_video_controls(
                    workflow_info,
                    key_prefix="standard_video",
                    default_duration=5,
                    allow_audio_driven=False,
                    show_duration=False,
                    default_ratio=default_video_ratio,
                )
        
            # ================================================================
            # Prompt Prefix Template Selector
            # ================================================================
            # 构建模板选项（用模板键作为选项值，Streamlit 直接管理状态）
            template_choices = get_template_choices(tr)
            template_keys = [tc[0] for tc in template_choices]

            # 下拉菜单 — 使用 Streamlit 原生 key 管理状态
            # 这样 widget 交互后，脚本启动前 st.session_state 就已更新
            dropdown_state_key = f"style_template_key_{media_config_key}"
            if dropdown_state_key not in st.session_state:
                st.session_state[dropdown_state_key] = template_keys[-1]  # 默认「自定义模板」，不锁任何参数

            selected_template_key = st.selectbox(
                tr("style.template_selector"),
                options=template_keys,
                format_func=lambda k: get_template_name(k, tr),
                help=tr("style.template_selector_help"),
                key=dropdown_state_key,
            )

            # ---- 模板启动按钮：点击后才激活绑定，触发参数锁定 ----
            _active_state_key = "_style_template_active"
            if _active_state_key not in st.session_state:
                st.session_state[_active_state_key] = template_keys[-1]  # 默认自定义

            _is_already_active = (st.session_state[_active_state_key] == selected_template_key)
            _btn_label = "✅ 已应用" if _is_already_active else "🚀 应用模板设置"
            _btn_type = "primary" if not _is_already_active else "secondary"

            apply_col1, apply_col2 = st.columns([1, 3])
            with apply_col1:
                if st.button(_btn_label, key="apply_style_template", type=_btn_type,
                             disabled=_is_already_active, use_container_width=True):
                    st.session_state[_active_state_key] = selected_template_key
                    st.rerun()
            with apply_col2:
                if _is_already_active:
                    st.caption(f"当前激活：**{get_template_name(selected_template_key, tr)}**")
                else:
                    _sel_name = get_template_name(selected_template_key, tr)
                    st.caption(f"已选择「{_sel_name}」，点击左侧按钮应用")

            # 统一使用已激活的模板键（而非下拉选中键）来控制锁定行为
            _effective_template_key = st.session_state[_active_state_key]

            # 根据激活模板渲染对应的 prompt 输入区
            lock_status = is_template_locked(_effective_template_key)
            has_permission = check_edit_permission()

            if _effective_template_key == CUSTOM_TEMPLATE_KEY:
                # ---- 自定义模板：始终可编辑 ----
                custom_state_key = f"custom_prompt_{media_config_key}"
                if custom_state_key not in st.session_state:
                    st.session_state[custom_state_key] = ""

                prompt_prefix = st.text_area(
                    tr("style.template_custom_label"),
                    value=st.session_state[custom_state_key],
                    placeholder=tr("style.template_custom_placeholder"),
                    height=80,
                    help=tr("style.template_custom_help"),
                    label_visibility="visible",
                    key=f"custom_prompt_textarea_{media_config_key}",
                )
                st.session_state[custom_state_key] = prompt_prefix

            elif lock_status and not has_permission:
                # ---- 内置模板 + 无编辑权限：只读 ----
                template_prompt = get_template_prompt(_effective_template_key)
                st.text_area(
                    tr("style.template_locked"),
                    value=template_prompt,
                    height=80,
                    disabled=True,
                    help=tr("style.template_locked_help"),
                    label_visibility="visible",
                    key=f"locked_prompt_display_{media_config_key}",
                )
                prompt_prefix = template_prompt

            else:
                # ---- 内置模板 + 有编辑权限：可编辑 ----
                template_prompt = get_template_prompt(_effective_template_key)
                edit_state_key = f"builtin_prompt_edited_{media_config_key}_{_effective_template_key}"
                if edit_state_key not in st.session_state:
                    st.session_state[edit_state_key] = template_prompt

                prompt_prefix = st.text_area(
                    tr("style.template_editable"),
                    value=st.session_state[edit_state_key],
                    height=80,
                    help=tr("style.prompt_prefix_help"),
                    label_visibility="visible",
                    key=f"editable_prompt_textarea_{media_config_key}_{_effective_template_key}",
                )
                st.session_state[edit_state_key] = prompt_prefix

            # ---- 模板绑定参数信息面板（展示选中模板的全部参数，预览模式） ----
            if selected_template_key != CUSTOM_TEMPLATE_KEY:
                _info_binding = get_template_binding(selected_template_key)
                if _info_binding:
                    _is_applied = (_effective_template_key == selected_template_key)
                    _status = "✅ 已应用" if _is_applied else "👁 预览中（点击左侧按钮应用）"
                    with st.container(border=True):
                        st.markdown(f"📋 **{get_template_name(selected_template_key, tr)}** — 绑定参数 {_status}")
                        lines = []
                        # TTS
                        if _info_binding.tts_voice:
                            _voice_display = get_voice_display_name(_info_binding.tts_voice, tr, get_language())
                            lines.append(f"| 语音 | {_voice_display} (`{_info_binding.tts_voice}`) |")
                        if _info_binding.tts_speed is not None:
                            lines.append(f"| 语速 | {_info_binding.tts_speed:.1f}x |")
                        # 画面模板
                        if _info_binding.frame_template:
                            lines.append(f"| 画面模板 | `{_info_binding.frame_template}` |")
                        # 固定参数
                        if _info_binding.fixed_params:
                            for k, v in _info_binding.fixed_params.items():
                                _val = v[:60] + "…" if len(v) > 60 else v
                                lines.append(f"| {k} | {_val} |")
                        # 生图风格
                        if _info_binding.prompt:
                            _prompt_short = _info_binding.prompt[:80] + "…" if len(_info_binding.prompt) > 80 else _info_binding.prompt
                            lines.append(f"| 生图风格 | {_prompt_short} |")
                        if lines:
                            st.markdown("\n".join(lines))

            # Media preview expander
            preview_title = tr("style.video_preview_title") if template_media_type == "video" else tr("style.preview_title")
            with st.expander(preview_title, expanded=False):
                # Test prompt input
                test_prompt_label = tr("style.test_video_prompt") if template_media_type == "video" else tr("style.test_prompt")
                test_prompt_value = "a peaceful lake, gentle camera movement" if template_media_type == "video" else "a dog"
                
                test_prompt = st.text_input(
                    test_prompt_label,
                    value=test_prompt_value,
                    help=tr("style.test_prompt_help"),
                    key="style_test_prompt"
                )
            
                # Preview button
                preview_button_label = tr("style.video_preview") if template_media_type == "video" else tr("style.preview")
                if st.button(preview_button_label, key="preview_style", use_container_width=True):
                    if not workflow_key:
                        st.error(
                            "请先选择可用的工作流或模型。"
                            if get_language() == "zh_CN"
                            else "Please select an available workflow or model first."
                        )
                        st.stop()
                    previewing_text = tr("style.video_previewing") if template_media_type == "video" else tr("style.previewing")
                    with st.spinner(previewing_text):
                        try:
                            from pixelle_video.utils.prompt_helper import build_image_prompt
                        
                            # Build final prompt with prefix
                            final_prompt = build_image_prompt(test_prompt, prompt_prefix)

                            preview_params = dict(api_video_params) if template_media_type == "video" else {}

                            # Generate preview media with the selected source only.
                            media_result = run_async(pixelle_video.media(
                                prompt=final_prompt,
                                workflow=workflow_key,
                                media_type=template_media_type,
                                width=int(media_width),
                                height=int(media_height),
                                duration=5 if template_media_type == "video" else None,
                                **preview_params,
                            ))
                            preview_media_path = media_result.url
                        
                            # Display preview (support both URL and local path)
                            if preview_media_path:
                                success_text = tr("style.video_preview_success") if template_media_type == "video" else tr("style.preview_success")
                                st.success(success_text)

                                if template_media_type == "video":
                                    st.video(preview_media_path)
                                else:
                                    if preview_media_path.startswith('http'):
                                        # URL - use directly
                                        img_html = f'<div class="preview-image"><img src="{preview_media_path}" alt="Style Preview"/></div>'
                                    else:
                                        # Local file - encode as base64
                                        with open(preview_media_path, 'rb') as f:
                                            img_data = base64.b64encode(f.read()).decode()
                                        img_html = f'<div class="preview-image"><img src="data:image/png;base64,{img_data}" alt="Style Preview"/></div>'

                                    st.markdown(img_html, unsafe_allow_html=True)
                            
                                # Show the final prompt used
                                st.info(f"**{tr('style.final_prompt_label')}**\n{final_prompt}")
                            
                                # Show file path
                                st.caption(f"📁 {preview_media_path}")
                            else:
                                st.error(tr("style.preview_failed_general"))
                        except Exception as e:
                            st.error(tr("style.preview_failed", error=str(e)))
                            logger.exception(e)
        
    
    else:
        # Template doesn't need images - show simplified message
        with st.container(border=True):
            st.markdown(f"**{tr('section.image')}**")
            st.info("ℹ️ " + tr("image.not_required"))
            st.caption(tr("image.not_required_hint"))
            
            # Get media size from template (even though not used, for consistency)
            media_width = st.session_state.get('template_media_width')
            media_height = st.session_state.get('template_media_height')
            
            # Set default values for later use
            workflow_key = None
            prompt_prefix = ""
    
    # Return all style configuration parameters
    final_media_workflow = workflow_key

    return {
        "tts_inference_mode": tts_mode,
        "tts_voice": selected_voice if tts_mode == "local" else None,
        "tts_speed": tts_speed if tts_mode == "local" else None,
        "tts_workflow": tts_workflow_key if tts_mode == "comfyui" else None,
        "ref_audio": str(ref_audio_path) if ref_audio_path else None,
        "frame_template": frame_template,
        "template_params": custom_values_for_video if custom_values_for_video else None,
        "media_workflow": final_media_workflow,
        "api_video_params": api_video_params if template_media_type == "video" else None,
        "prompt_prefix": prompt_prefix if prompt_prefix else "",
        "media_width": media_width,
        "media_height": media_height
    }
