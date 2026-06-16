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
Video Processing Service

High-performance video composition service built on ffmpeg-python.

Features:
- Video concatenation
- Audio/video merging
- Background music addition
- Image to video conversion

Note: Requires FFmpeg to be installed on the system.
"""

import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import List, Literal, Optional

import ffmpeg
from loguru import logger

from pixelle_video.utils.os_util import (
    get_resource_path,
    list_resource_files,
    resource_exists
)


def check_ffmpeg() -> None:
    """
    检查系统是否安装了 FFmpeg，未找到时给出各平台的安装提示

    Raises:
        RuntimeError: 系统中未找到 ffmpeg 可执行文件时抛出
    """
    if not shutil.which("ffmpeg"):
        raise RuntimeError(
            "FFmpeg not found. Please install it:\n"
            "  macOS: brew install ffmpeg\n"
            "  Ubuntu/Debian: apt-get install ffmpeg\n"
            "  Windows: https://ffmpeg.org/download.html"
        )


class VideoService:
    """
    视频合成器，封装常用视频处理任务

    基于 ffmpeg-python，支持视频拼接、音视频合并、背景音乐添加、图片转视频、
    图片叠加等操作。在可能的情况下使用 stream copy 以保留原始质量。

    Requires:
        系统需安装 FFmpeg（首次使用时延迟检查）
    """

    def __init__(self):
        """
        初始化视频服务，FFmpeg 可用性检查延迟到首次使用时执行

        Side Effects:
            设置 self._ffmpeg_checked = False
        """
        self._ffmpeg_checked = False

    def _ensure_ffmpeg(self):
        """
        延迟检查 FFmpeg 可用性，只在首次使用时执行一次

        Side Effects:
            调用 check_ffmpeg() 并将 self._ffmpeg_checked 设为 True
        """
        if not self._ffmpeg_checked:
            check_ffmpeg()
            self._ffmpeg_checked = True

    def concat_videos(
        self,
        videos: List[str],
        output: str,
        method: Literal["demuxer", "filter"] = "demuxer",
        bgm_path: Optional[str] = None,
        bgm_volume: float = 0.2,
        bgm_mode: Literal["once", "loop"] = "loop"
    ) -> str:
        """
        将多个视频拼接为一个，可选添加背景音乐

        Args:
            videos: 要拼接的视频文件路径列表
            output: 输出视频文件路径
            method: 拼接方式 —— "demuxer"（快速无重编码，要求格式一致）或 "filter"（较慢但兼容不同格式）
            bgm_path: 背景音乐文件路径（可选，None 时不添加 BGM）
            bgm_volume: BGM 音量（0.0 到 1.0+，默认 0.2）
            bgm_mode: BGM 播放模式 —— "once"（单次）或 "loop"（循环，默认）

        Returns:
            输出视频文件路径

        Raises:
            ValueError: videos 列表为空时抛出
            RuntimeError: FFmpeg 执行失败时抛出
        """
        self._ensure_ffmpeg()

        if not videos:
            raise ValueError("Videos list cannot be empty")
        
        if len(videos) == 1:
            logger.info(f"Only one video provided, copying to {output}")
            shutil.copy(videos[0], output)
            return output
        
        logger.info(f"Concatenating {len(videos)} videos using {method} method")
        
        # Step 1: Concatenate videos
        if bgm_path:
            # If BGM needed, concatenate to temp file first
            temp_output = output.replace('.mp4', '_no_bgm.mp4')
            concat_result = self._concat_demuxer(videos, temp_output) if method == "demuxer" else self._concat_filter(videos, temp_output)
            
            # Step 2: Add BGM
            logger.info(f"Adding BGM: {bgm_path} (volume={bgm_volume}, mode={bgm_mode})")
            final_result = self._add_bgm_to_video(
                video=concat_result,
                bgm_path=bgm_path,
                output=output,
                volume=bgm_volume,
                mode=bgm_mode
            )
            
            # Clean up temp file
            if os.path.exists(temp_output):
                os.unlink(temp_output)
            
            return final_result
        else:
            # No BGM, direct concatenation
            if method == "demuxer":
                return self._concat_demuxer(videos, output)
            else:
                return self._concat_filter(videos, output)
    
    def _concat_demuxer(self, videos: List[str], output: str) -> str:
        """
        使用 concat demuxer 方式拼接视频（快速，无重编码，要求格式一致）

        等价 FFmpeg 命令：ffmpeg -f concat -safe 0 -i filelist.txt -c copy output.mp4

        Args:
            videos: 视频文件路径列表
            output: 输出文件路径

        Returns:
            输出视频文件路径

        Raises:
            RuntimeError: FFmpeg 执行失败时抛出

        Side Effects:
            创建并随后删除临时文件列表
        """
        # Create temporary file list
        with tempfile.NamedTemporaryFile(
            mode='w',
            delete=False,
            suffix='.txt',
            encoding='utf-8'
        ) as f:
            for video in videos:
                abs_path = Path(video).absolute()
                escaped_path = str(abs_path).replace("'", "'\\''")
                f.write(f"file '{escaped_path}'\n")
            filelist = f.name
        
        try:
            logger.debug(f"Created filelist: {filelist}")
            (
                ffmpeg
                .input(filelist, format='concat', safe=0)
                .output(output, c='copy')
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
            logger.success(f"Videos concatenated successfully: {output}")
            return output
        except ffmpeg.Error as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            logger.error(f"FFmpeg concat error: {error_msg}")
            raise RuntimeError(f"Failed to concatenate videos: {error_msg}")
        finally:
            if os.path.exists(filelist):
                os.unlink(filelist)
    
    def _concat_filter(self, videos: List[str], output: str) -> str:
        """
        使用 concat filter 方式拼接视频（较慢但兼容不同格式和编码）

        等价 FFmpeg 命令：使用 filter_complex concat 滤镜拼接音视频流

        Args:
            videos: 视频文件路径列表
            output: 输出文件路径

        Returns:
            输出视频文件路径

        Raises:
            RuntimeError: FFmpeg 执行失败时抛出
        """
        try:
            # Build filter_complex string manually
            n = len(videos)
            
            # Build input stream labels: [0:v][0:a][1:v][1:a]...
            stream_spec = "".join([f"[{i}:v][{i}:a]" for i in range(n)])
            filter_complex = f"{stream_spec}concat=n={n}:v=1:a=1[v][a]"
            
            # Build ffmpeg command
            cmd = ['ffmpeg']
            for video in videos:
                cmd.extend(['-i', video])
            cmd.extend([
                '-filter_complex', filter_complex,
                '-map', '[v]',
                '-map', '[a]',
                '-y',  # Overwrite output
                output
            ])
            
            # Run command
            import subprocess
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            logger.success(f"Videos concatenated successfully: {output}")
            return output
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else str(e)
            logger.error(f"FFmpeg concat filter error: {error_msg}")
            raise RuntimeError(f"Failed to concatenate videos: {error_msg}")
        except Exception as e:
            logger.error(f"Concatenation error: {e}")
            raise RuntimeError(f"Failed to concatenate videos: {e}")
    
    def _get_video_duration(self, video: str) -> float:
        """
        获取视频时长

        Args:
            video: 视频文件路径

        Returns:
            视频时长（秒），获取失败时返回 0.0
        """
        try:
            probe = ffmpeg.probe(video)
            duration = float(probe['format']['duration'])
            return duration
        except Exception as e:
            logger.warning(f"Failed to get video duration: {e}")
            return 0.0
    
    def _get_audio_duration(self, audio: str) -> float:
        """
        获取音频时长，获取失败时基于文件大小估算

        Args:
            audio: 音频文件路径

        Returns:
            音频时长（秒），获取失败时基于文件大小粗略估算（至少 1.0 秒）
        """
        try:
            probe = ffmpeg.probe(audio)
            duration = float(probe['format']['duration'])
            return duration
        except Exception as e:
            logger.warning(f"Failed to get audio duration: {e}, using estimate")
            # Fallback: estimate based on file size (very rough)
            import os
            file_size = os.path.getsize(audio)
            # Assume ~16kbps for MP3, so 2KB per second
            estimated_duration = file_size / 2000
            return max(1.0, estimated_duration)  # At least 1 second
    
    def has_audio_stream(self, video: str) -> bool:
        """
        检测视频文件是否包含音频流

        Args:
            video: 视频文件路径

        Returns:
            True 表示存在音频流，False 表示无音频流或检测失败
        """
        try:
            probe = ffmpeg.probe(video)
            audio_streams = [s for s in probe.get('streams', []) if s['codec_type'] == 'audio']
            has_audio = len(audio_streams) > 0
            logger.debug(f"Video {video} has_audio={has_audio}")
            return has_audio
        except Exception as e:
            logger.warning(f"Failed to probe video audio streams: {e}, assuming no audio")
            return False
    
    def merge_audio_video(
        self,
        video: str,
        audio: str,
        output: str,
        replace_audio: bool = True,
        audio_volume: float = 1.0,
        video_volume: float = 0.0,
        pad_strategy: str = "freeze",  # "freeze" (freeze last frame) or "black" (black screen)
        auto_adjust_duration: bool = True,  # Automatically adjust video duration to match audio
        duration_tolerance: float = 0.3,  # Tolerance for video being longer than audio (seconds)
    ) -> str:
        """
        将音频合并到视频中，智能处理时长不匹配问题

        自动处理三种时长场景：
        - 视频短于音频：按 pad_strategy 补足视频时长
        - 视频略长于音频（在 tolerance 内）：保留原样
        - 视频明显长于音频（超出 tolerance）：裁剪视频以匹配音频

        自动检测视频是否有音频流：
        - 无音频流：直接添加音频轨
        - 有音频流且 replace_audio=True：替换原有音频
        - 有音频流且 replace_audio=False：混合两路音频

        Args:
            video: 视频文件路径
            audio: 音频文件路径
            output: 输出视频文件路径
            replace_audio: True 替换原有音频，False 混合原音频和新音频
            audio_volume: 新音频音量（0.0 到 1.0+，默认 1.0）
            video_volume: 原视频音频音量（0.0 到 1.0+，默认 0.0，仅 replace_audio=False 时使用）
            pad_strategy: 视频补足策略 —— "freeze"（冻结最后一帧，默认）或 "black"（黑屏填充）
            auto_adjust_duration: 是否启用智能时长调整（默认 True）
            duration_tolerance: 视频长于音频的容忍度（秒，默认 0.3）

        Returns:
            输出视频文件路径

        Raises:
            RuntimeError: FFmpeg 执行失败时抛出
        """
        self._ensure_ffmpeg()

        # Get durations of video and audio
        video_duration = self._get_video_duration(video)
        audio_duration = self._get_audio_duration(audio)
        
        logger.info(f"Video duration: {video_duration:.2f}s, Audio duration: {audio_duration:.2f}s")
        
        # Intelligent duration adjustment (if enabled)
        if auto_adjust_duration:
            diff = video_duration - audio_duration
            
            if diff < 0:
                # Video shorter than audio → Must pad to avoid black screen
                logger.warning(f"⚠️ Video shorter than audio by {abs(diff):.2f}s, padding required")
                video = self._pad_video_to_duration(video, audio_duration, pad_strategy)
                video_duration = audio_duration  # Update duration after padding
                logger.info(f"📌 Padded video to {audio_duration:.2f}s")
            
            elif diff > duration_tolerance:
                # Video significantly longer than audio → Trim
                logger.info(f"⚠️ Video longer than audio by {diff:.2f}s (tolerance: {duration_tolerance}s)")
                video = self._trim_video_to_duration(video, audio_duration)
                video_duration = audio_duration  # Update duration after trimming
                logger.info(f"✂️ Trimmed video to {audio_duration:.2f}s")
            
            else:  # 0 <= diff <= duration_tolerance
                # Video slightly longer but within tolerance → Keep as-is
                logger.info(f"✅ Duration acceptable: video={video_duration:.2f}s, audio={audio_duration:.2f}s (diff={diff:.2f}s)")
        
        # Determine target duration (max of both)
        target_duration = max(video_duration, audio_duration)
        logger.info(f"Target output duration: {target_duration:.2f}s")
        
        # Check if video has audio stream
        video_has_audio = self.has_audio_stream(video)
        
        # Prepare video stream (potentially with padding)
        input_video = ffmpeg.input(video)
        video_stream = input_video.video
        
        # Pad video if audio is longer
        if audio_duration > video_duration:
            pad_duration = audio_duration - video_duration
            logger.info(f"Audio is longer, padding video by {pad_duration:.2f}s using '{pad_strategy}' strategy")
            
            if pad_strategy == "freeze":
                # Freeze last frame: tpad filter
                video_stream = video_stream.filter('tpad', stop_mode='clone', stop_duration=pad_duration)
            else:  # black
                # Generate black frames for padding duration
                # Get video properties
                probe = ffmpeg.probe(video)
                video_info = next(s for s in probe['streams'] if s['codec_type'] == 'video')
                width = int(video_info['width'])
                height = int(video_info['height'])
                fps_str = video_info['r_frame_rate']
                fps_num, fps_den = map(int, fps_str.split('/'))
                fps = fps_num / fps_den if fps_den != 0 else 30
                
                # Create black video for padding
                black_video_path = self._get_unique_temp_path("black_pad", os.path.basename(output))
                black_input = ffmpeg.input(
                    f'color=c=black:s={width}x{height}:r={fps}',
                    f='lavfi',
                    t=pad_duration
                )
                
                # Concatenate original video with black padding
                video_stream = ffmpeg.concat(video_stream, black_input.video, v=1, a=0)
        
        # Prepare audio stream (pad if needed to match target duration)
        input_audio = ffmpeg.input(audio)
        audio_stream = input_audio.audio.filter('volume', audio_volume)
        
        # Pad audio with silence if video is longer
        if video_duration > audio_duration:
            pad_duration = video_duration - audio_duration
            logger.info(f"Video is longer, padding audio with {pad_duration:.2f}s silence")
            # Use apad to add silence at the end
            audio_stream = audio_stream.filter('apad', whole_dur=target_duration)
        
        if not video_has_audio:
            logger.info(f"Video has no audio stream, adding audio track")
            # Video is silent, just add the audio
            try:
                (
                    ffmpeg
                    .output(
                        video_stream,
                        audio_stream,
                        output,
                        vcodec='libx264',  # Re-encode video if padded
                        acodec='aac',
                        audio_bitrate='192k'
                    )
                    .overwrite_output()
                    .run(capture_stdout=True, capture_stderr=True)
                )
                
                logger.success(f"Audio added to silent video: {output}")
                return output
            except ffmpeg.Error as e:
                error_msg = e.stderr.decode() if e.stderr else str(e)
                logger.error(f"FFmpeg error adding audio to silent video: {error_msg}")
                raise RuntimeError(f"Failed to add audio to video: {error_msg}")
        
        # Video has audio, proceed with merging
        logger.info(f"Merging audio with video (replace={replace_audio})")
        
        try:
            if replace_audio:
                # Replace audio: use only new audio, ignore original
                (
                    ffmpeg
                    .output(
                        video_stream,
                        audio_stream,
                        output,
                        vcodec='libx264',  # Re-encode video if padded
                        acodec='aac',
                        audio_bitrate='192k'
                    )
                    .overwrite_output()
                    .run(capture_stdout=True, capture_stderr=True)
                )
            else:
                # Mix audio: combine original and new audio
                mixed_audio = ffmpeg.filter(
                    [
                        input_video.audio.filter('volume', video_volume),
                        audio_stream
                    ],
                    'amix',
                    inputs=2,
                    duration='longest'  # Use longest audio
                )
                
                (
                    ffmpeg
                    .output(
                        video_stream,
                        mixed_audio,
                        output,
                        vcodec='libx264',  # Re-encode video if padded
                        acodec='aac',
                        audio_bitrate='192k'
                    )
                    .overwrite_output()
                    .run(capture_stdout=True, capture_stderr=True)
                )
            
            logger.success(f"Audio merged successfully: {output}")
            return output
        except ffmpeg.Error as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            logger.error(f"FFmpeg merge error: {error_msg}")
            raise RuntimeError(f"Failed to merge audio and video: {error_msg}")
    
    def overlay_image_on_video(
        self,
        video: str,
        overlay_image: str,
        output: str,
        scale_mode: str = "contain"
    ) -> str:
        """
        在视频上叠加透明图片（如渲染的 HTML 字幕层）

        Args:
            video: 底视频文件路径
            overlay_image: 透明叠加图片路径（如透明背景的 HTML 渲染结果）
            output: 输出视频文件路径
            scale_mode: 底视频缩放模式 —— "contain"（适配含黑边）、"cover"（裁剪填充）或 "stretch"（拉伸）

        Returns:
            输出视频文件路径

        Raises:
            RuntimeError: FFmpeg 执行失败时抛出
        """
        self._ensure_ffmpeg()
        logger.info(f"Overlaying image on video (scale_mode={scale_mode})")
        
        try:
            # Get overlay image dimensions
            overlay_probe = ffmpeg.probe(overlay_image)
            overlay_stream = next(s for s in overlay_probe['streams'] if s['codec_type'] == 'video')
            overlay_width = int(overlay_stream['width'])
            overlay_height = int(overlay_stream['height'])
            
            logger.debug(f"Overlay dimensions: {overlay_width}x{overlay_height}")
            
            input_video = ffmpeg.input(video)
            input_overlay = ffmpeg.input(overlay_image)
            
            # Scale video to fit overlay size using scale_mode
            if scale_mode == "contain":
                # Scale to fit (letterbox/pillarbox if aspect ratio differs)
                # Use scale filter with force_original_aspect_ratio=decrease and pad to center
                scaled_video = (
                    input_video
                    .filter('scale', overlay_width, overlay_height, force_original_aspect_ratio='decrease')
                    .filter('pad', overlay_width, overlay_height, '(ow-iw)/2', '(oh-ih)/2', color='black')
                )
            elif scale_mode == "cover":
                # Scale to cover (crop if aspect ratio differs)
                scaled_video = (
                    input_video
                    .filter('scale', overlay_width, overlay_height, force_original_aspect_ratio='increase')
                    .filter('crop', overlay_width, overlay_height)
                )
            else:  # stretch
                # Stretch to exact dimensions
                scaled_video = input_video.filter('scale', overlay_width, overlay_height)
            
            # Overlay the transparent image on top of the scaled video
            output_stream = ffmpeg.overlay(scaled_video, input_overlay)
            
            (
                ffmpeg
                .output(output_stream, output, 
                        vcodec='libx264',
                        pix_fmt='yuv420p',
                        preset='medium',
                        crf=23)
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
            
            logger.success(f"Image overlaid on video: {output}")
            return output
        except ffmpeg.Error as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            logger.error(f"FFmpeg overlay error: {error_msg}")
            raise RuntimeError(f"Failed to overlay image on video: {error_msg}")
    
    def create_video_from_image(
        self,
        image: str,
        audio: str,
        output: str,
        fps: int = 30,
    ) -> str:
        """
        将静态图片与音频合成为视频，图片作为静态帧持续音频的整个时长

        Args:
            image: 图片文件路径
            audio: 音频文件路径
            output: 输出视频路径
            fps: 帧率（默认 30）

        Returns:
            输出视频文件路径

        Raises:
            RuntimeError: FFmpeg 执行失败时抛出
        """
        self._ensure_ffmpeg()
        logger.info("Creating video from image and audio")
        
        try:
            # Get audio duration to ensure exact video duration match
            probe = ffmpeg.probe(audio)
            audio_duration = float(probe['format']['duration'])
            logger.debug(f"Audio duration: {audio_duration:.3f}s")
            
            # Input image with loop (loop=1 means loop indefinitely)
            # Use framerate to set input framerate
            input_image = ffmpeg.input(image, loop=1, framerate=fps)
            input_audio = ffmpeg.input(audio)
            
            # Combine image and audio
            # Use -t to explicitly set video duration = audio duration
            (
                ffmpeg
                .output(
                    input_image,
                    input_audio,
                    output,
                    t=audio_duration,  # Force video duration to match audio exactly
                    vcodec='libx264',
                    acodec='aac',
                    pix_fmt='yuv420p',
                    audio_bitrate='192k',
                    preset='medium',
                    crf=23,
                    **{'b:v': '2M'}  # Video bitrate
                )
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
            
            logger.success(f"Video created from image: {output} (duration: {audio_duration:.3f}s)")
            return output
        except ffmpeg.Error as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            logger.error(f"FFmpeg error creating video from image: {error_msg}")
            raise RuntimeError(f"Failed to create video from image: {error_msg}")
    
    def add_bgm(
        self,
        video: str,
        bgm: str,
        output: str,
        bgm_volume: float = 0.3,
        loop: bool = True,
        fade_in: float = 0.0,
        fade_out: float = 0.0,
    ) -> str:
        """
        为视频添加背景音乐，与原音频混合

        Args:
            video: 视频文件路径
            bgm: 背景音乐文件路径
            output: 输出视频文件路径
            bgm_volume: BGM 音量（0.0 到 1.0+，默认 0.3）
            loop: 是否循环 BGM 以匹配视频时长（默认 True）
            fade_in: BGM 淡入时长（秒，默认 0.0）
            fade_out: BGM 淡出时长（秒，默认 0.0，暂未实现）

        Returns:
            输出视频文件路径

        Raises:
            RuntimeError: FFmpeg 执行失败时抛出
        """
        self._ensure_ffmpeg()
        logger.info(f"Adding BGM to video (volume={bgm_volume}, loop={loop})")
        
        try:
            input_video = ffmpeg.input(video)
            
            # Configure BGM input with looping if needed
            bgm_input = ffmpeg.input(
                bgm,
                stream_loop=-1 if loop else 0  # -1 = infinite loop
            )
            
            # Apply volume adjustment to BGM
            bgm_audio = bgm_input.audio.filter('volume', bgm_volume)
            
            # Apply fade effects if specified
            if fade_in > 0:
                bgm_audio = bgm_audio.filter('afade', type='in', duration=fade_in)
            # Note: fade_out at the end requires knowing the duration, which is complex
            # For now, we skip fade_out in this implementation
            # A more advanced implementation would need to:
            # 1. Get video duration
            # 2. Calculate fade_out start time
            # 3. Apply fade filter with specific start_time
            
            # Mix original audio with BGM
            mixed_audio = ffmpeg.filter(
                [input_video.audio, bgm_audio],
                'amix',
                inputs=2,
                duration='first'  # Use video's duration
            )
            
            (
                ffmpeg
                .output(
                    input_video.video,
                    mixed_audio,
                    output,
                    vcodec='copy',
                    acodec='aac',
                    audio_bitrate='192k'
                )
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
            
            logger.success(f"BGM added successfully: {output}")
            return output
        except ffmpeg.Error as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            logger.error(f"FFmpeg BGM error: {error_msg}")
            raise RuntimeError(f"Failed to add BGM: {error_msg}")
    
    def _add_bgm_to_video(
        self,
        video: str,
        bgm_path: str,
        output: str,
        volume: float = 0.2,
        mode: Literal["once", "loop"] = "loop"
    ) -> str:
        """
        内部辅助方法：解析 BGM 路径后调用 add_bgm 添加背景音乐

        Args:
            video: 视频文件路径
            bgm_path: BGM 路径（可以是预设名称或自定义路径）
            output: 输出文件路径
            volume: BGM 音量（0.0 到 1.0，默认 0.2）
            mode: 播放模式 —— "once"（单次）或 "loop"（循环，默认）

        Returns:
            输出视频文件路径

        Raises:
            FileNotFoundError: BGM 文件未找到时抛出
        """
        # Resolve BGM path (raises FileNotFoundError if not found)
        resolved_bgm = self._resolve_bgm_path(bgm_path)
        
        # Add BGM using existing method
        loop = (mode == "loop")
        return self.add_bgm(
            video=video,
            bgm=resolved_bgm,
            output=output,
            bgm_volume=volume,
            loop=loop,
            fade_in=0.0
        )
    
    def _get_unique_temp_path(self, prefix: str, original_filename: str) -> str:
        """
        生成唯一临时文件路径以避免并发冲突

        Args:
            prefix: 临时文件前缀（如 "trimmed", "padded", "black_pad"）
            original_filename: 原始文件名，保留在临时路径中

        Returns:
            唯一临时文件路径，格式为 temp/{prefix}_{uuid8位}_{original_filename}
        """
        from pixelle_video.utils.os_util import get_temp_path
        
        unique_id = uuid.uuid4().hex[:8]
        return get_temp_path(f"{prefix}_{unique_id}_{original_filename}")
    
    def _resolve_bgm_path(self, bgm_path: str) -> str:
        """
        解析 BGM 路径，支持文件名和自定义路径，优先使用用户自定义覆盖

        搜索优先级：直接路径 > data/bgm/（自定义） > bgm/（默认）

        Args:
            bgm_path: BGM 文件名字符串或自定义绝对/相对路径

        Returns:
            解析后的绝对路径

        Raises:
            FileNotFoundError: BGM 文件未找到时抛出，提示已尝试的路径和可用文件列表
        """
        # Try direct path first (absolute or relative)
        if os.path.exists(bgm_path):
            return os.path.abspath(bgm_path)
        
        # Try as filename in resource directories (custom > default)
        if resource_exists("bgm", bgm_path):
            return get_resource_path("bgm", bgm_path)
        
        # Not found - provide helpful error message
        tried_paths = [
            os.path.abspath(bgm_path),
            f"data/bgm/{bgm_path} or bgm/{bgm_path}"
        ]
        
        # List available BGM files
        available_bgm = self._list_available_bgm()
        available_msg = f"\n  Available BGM files: {', '.join(available_bgm)}" if available_bgm else ""
        
        raise FileNotFoundError(
            f"BGM file not found: '{bgm_path}'\n"
            f"  Tried paths:\n"
            f"    1. {tried_paths[0]}\n"
            f"    2. {tried_paths[1]}"
            f"{available_msg}"
        )
    
    def _list_available_bgm(self) -> list[str]:
        """
        列出所有可用的 BGM 文件（合并 bgm/ 和 data/bgm/ 目录）

        Returns:
            音频文件名列表（含扩展名），按字母排序，仅包含 mp3/wav/ogg/flac/m4a/aac 格式
        """
        try:
            # Use resource API to get merged list
            all_files = list_resource_files("bgm")
            
            # Filter to audio files only
            audio_extensions = ('.mp3', '.wav', '.ogg', '.flac', '.m4a', '.aac')
            return sorted([f for f in all_files if f.lower().endswith(audio_extensions)])
        except Exception as e:
            logger.warning(f"Failed to list BGM files: {e}")
            return []
    
    def _trim_video_to_duration(self, video: str, target_duration: float) -> str:
        """
        将视频裁切到指定时长，优先使用 stream copy 以加速

        Args:
            video: 输入视频文件路径
            target_duration: 目标时长（秒）

        Returns:
            裁切后的视频文件路径（临时文件）

        Raises:
            RuntimeError: FFmpeg 执行失败时抛出

        Side Effects:
            在 temp/ 目录创建临时文件
        """
        output = self._get_unique_temp_path("trimmed", os.path.basename(video))
        
        try:
            # Use stream copy when possible for fast trimming
            input_stream = ffmpeg.input(video, t=target_duration)
            output_kwargs = {"vcodec": "copy"}
            if self.has_audio_stream(video):
                output_kwargs["acodec"] = "copy"
            (
                input_stream
                .output(output, **output_kwargs)
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True, quiet=True)
            )
            return output
        except ffmpeg.Error as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            logger.error(f"FFmpeg error trimming video: {error_msg}")
            raise RuntimeError(f"Failed to trim video: {error_msg}")
    
    def _pad_video_to_duration(self, video: str, target_duration: float, pad_strategy: str = "freeze") -> str:
        """
        将视频补足到指定时长，通过冻结最后一帧或添加黑帧实现

        Args:
            video: 输入视频文件路径
            target_duration: 目标时长（秒）
            pad_strategy: 补足策略 —— "freeze"（冻结最后一帧）或 "black"（黑屏填充）

        Returns:
            补足后的视频文件路径（临时文件），若无需补足则返回原路径

        Raises:
            RuntimeError: FFmpeg 执行失败时抛出

        Side Effects:
            在 temp/ 目录创建临时文件
        """
        output = self._get_unique_temp_path("padded", os.path.basename(video))
        
        video_duration = self._get_video_duration(video)
        pad_duration = target_duration - video_duration
        
        if pad_duration <= 0:
            # No padding needed, return original
            return video
        
        try:
            input_video = ffmpeg.input(video)
            video_stream = input_video.video
            
            if pad_strategy == "freeze":
                # Freeze last frame using tpad filter
                video_stream = video_stream.filter('tpad', stop_mode='clone', stop_duration=pad_duration)
                
                # Output with re-encoding (tpad requires it)
                (
                    ffmpeg
                    .output(
                        video_stream,
                        output,
                        vcodec='libx264',
                        preset='fast',
                        crf=23
                    )
                    .overwrite_output()
                    .run(capture_stdout=True, capture_stderr=True, quiet=True)
                )
            else:  # black
                # Generate black frames for padding duration
                # Get video properties
                probe = ffmpeg.probe(video)
                video_info = next(s for s in probe['streams'] if s['codec_type'] == 'video')
                width = int(video_info['width'])
                height = int(video_info['height'])
                fps_str = video_info['r_frame_rate']
                fps_num, fps_den = map(int, fps_str.split('/'))
                fps = fps_num / fps_den if fps_den != 0 else 30
                
                # Create black video for padding
                black_input = ffmpeg.input(
                    f'color=c=black:s={width}x{height}:r={fps}',
                    f='lavfi',
                    t=pad_duration
                )
                
                # Concatenate original video with black padding
                video_stream = ffmpeg.concat(video_stream, black_input.video, v=1, a=0)
                
                (
                    ffmpeg
                    .output(
                        video_stream,
                        output,
                        vcodec='libx264',
                        preset='fast',
                        crf=23
                    )
                    .overwrite_output()
                    .run(capture_stdout=True, capture_stderr=True, quiet=True)
                )
            
            return output
        except ffmpeg.Error as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            logger.error(f"FFmpeg error padding video: {error_msg}")
            raise RuntimeError(f"Failed to pad video: {error_msg}")

