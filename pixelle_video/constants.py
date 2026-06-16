"""
Pixelle-Video 全局常量定义

将散落在各处的魔数统一管理，方便修改和全局引用。
所有常量为模块级变量，无外部依赖。

分类:
    - 文件上传限制
    - 分镜参数
    - UI 布局配置
    - 视频生成相关
    - LLM 调用默认值
    - 模板路径预设
    - 预览默认值
"""

# ── 文件上传限制 ──────────────────────────────────
MAX_REF_IMAGE_SIZE = 10 * 1024 * 1024       # 参考图上传上限 10MB
MAX_UPLOAD_FILE_SIZE = 50 * 1024 * 1024     # 通用文件上传上限 50MB
MAX_FILE_PATH_LENGTH = 255                  # 文件路径最大长度（跨平台安全值）

# ── 分镜相关 ────────────────────────────────────
DEFAULT_SCENES_COUNT = 5                     # 默认分镜数
MIN_SCENES_COUNT = 1                         # 最少分镜数
MAX_SCENES_COUNT = 30                        # 最多分镜数（防止 LLM 过度拆分）
SCENES_KEY = "st_scenes"                     # Streamlit session_state 中的分镜存储 key
REF_IMAGES_KEY = "st_refs"                   # Streamlit session_state 中的参考图存储 key
CONFIRMED_KEY = "st_confirmed"               # Streamlit session_state 中的确认状态 key

# ── UI 布局 ─────────────────────────────────────
TEMPLATE_GRID_COLS = 5                       # 模板画廊每行列数
TEMPLATE_THUMBNAIL_HEIGHT = 150              # 模板占位缩略图高度（px）

# ── 视频生成 ───────────────────────────────────
PROGRESS_CAP = 99                            # 进度条百分比上限（完成时直接跳 100）
BATCH_ESTIMATED_MINUTES_PER_VIDEO = 3        # 批量模式下每个视频的预估耗时（分钟）

# ── LLM 调用默认值 ─────────────────────────────
LLM_DEFAULT_TEMPERATURE = 0.7                # 默认采样温度（0=确定性, 2=高随机）
LLM_DEFAULT_MAX_TOKENS = 8192                # 默认最大生成 token 数
LLM_MAX_RETRIES = 3                          # JSON 解析失败时的最大重试次数
LLM_RETRY_BASE_DELAY = 2                     # 指数退避的基础延迟（秒），第 n 次等待 = base * 2^(n-1)

# ── 默认模板路径 ───────────────────────────────
DEFAULT_IMAGE_TEMPLATE = "1080x1920/image_default.html"     # 默认图片模板
DEFAULT_VIDEO_TEMPLATE = "1080x1920/video_default.html"     # 默认视频模板
DEFAULT_STATIC_TEMPLATE = "1080x1920/static_default.html"   # 默认静态模板

# ── 预览默认值 ──────────────────────────────────
DEFAULT_PREVIEW_IMAGE = "resources/example.png"             # 模板预览默认图片
DEFAULT_TTS_PREVIEW_TEXT = "大家好，这是一段测试语音。"       # TTS 预览默认文本
DEFAULT_IMAGE_TEST_PROMPT = "a dog"                         # 图片测试默认 prompt
DEFAULT_VIDEO_TEST_PROMPT = "a peaceful lake, gentle camera movement"  # 视频测试默认 prompt
