"""
Pixelle-Video 全局常量定义
将散落在各处的魔数统一管理，方便修改和引用
"""

# ── 文件上传限制 ──────────────────────────────────
MAX_REF_IMAGE_SIZE = 10 * 1024 * 1024       # 参考图上传上限 10MB
MAX_UPLOAD_FILE_SIZE = 50 * 1024 * 1024     # 通用文件上传上限 50MB
MAX_FILE_PATH_LENGTH = 255                  # 文件路径最大长度

# ── 分镜相关 ────────────────────────────────────
DEFAULT_SCENES_COUNT = 5                     # 默认分镜数
MIN_SCENES_COUNT = 1                         # 最少分镜数
MAX_SCENES_COUNT = 30                        # 最多分镜数
SCENES_KEY = "st_scenes"                     # session_state key
REF_IMAGES_KEY = "st_refs"                   # 参考图 session_state key
CONFIRMED_KEY = "st_confirmed"               # 确认状态 key

# ── UI 布局 ─────────────────────────────────────
TEMPLATE_GRID_COLS = 5                       # 模板画廊列数
TEMPLATE_THUMBNAIL_HEIGHT = 150              # 模板占位缩略图高度(px)

# ── 视频生成 ───────────────────────────────────
PROGRESS_CAP = 99                            # 进度条百分比上限（完成时跳100）
BATCH_ESTIMATED_MINUTES_PER_VIDEO = 3        # 批量模式每个视频预估耗时

# ── LLM 调用 ───────────────────────────────────
LLM_DEFAULT_TEMPERATURE = 0.7
LLM_DEFAULT_MAX_TOKENS = 8192
LLM_MAX_RETRIES = 3                          # JSON 解析失败最大重试次数
LLM_RETRY_BASE_DELAY = 2                     # 退避基础延迟(秒)

# ── 默认模板路径 ───────────────────────────────
DEFAULT_IMAGE_TEMPLATE = "1080x1920/image_default.html"
DEFAULT_VIDEO_TEMPLATE = "1080x1920/video_default.html"
DEFAULT_STATIC_TEMPLATE = "1080x1920/static_default.html"

# ── 预览默认值 ──────────────────────────────────
DEFAULT_PREVIEW_IMAGE = "resources/example.png"
DEFAULT_TTS_PREVIEW_TEXT = "大家好，这是一段测试语音。"
DEFAULT_IMAGE_TEST_PROMPT = "a dog"
DEFAULT_VIDEO_TEST_PROMPT = "a peaceful lake, gentle camera movement"
