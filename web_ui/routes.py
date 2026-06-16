"""
Web UI 路由模块 — FastAPI Router，挂载到现有 api/app.py。

提供两类端点：
1. 页面路由（HTML）: /, /workflow/{id}, /history → Jinja2 模板渲染
2. API 路由（JSON）: /api/workflows, /api/workflows/categories → 工作流数据

依赖：
    - web_ui.workflow_registry.workflow_registry — 工作流元数据缓存
    - web_ui/templates/ 目录 — Jinja2 模板文件

集成方式（在 api/app.py 中）：:

    from web_ui.routes import router as web_ui_router
    app.include_router(web_ui_router, prefix="/web")
"""

from pathlib import Path
import asyncio
import json
import uuid

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from loguru import logger

from web_ui.workflow_registry import workflow_registry
from web_ui.workflow_executor import EXECUTORS

# ── Router 与模板引擎初始化 ─────────────────────────────────────

router = APIRouter(
    tags=["Web UI"],
    responses={
        404: {"description": "工作流未找到"},
        500: {"description": "服务器内部错误"},
    },
)

_templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(_templates_dir))


# ── 页面路由（HTML） ────────────────────────────────────────────


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """
    首页 — 工作流浏览器。

    展示所有已注册工作流的卡片列表，按分类分组。包含搜索框和分类筛选器。

    Args:
        request: FastAPI Request 对象（模板渲染必需）。

    Returns:
        HTMLResponse: 渲染后的 index.html 页面。

    Template Context:
        request:    Request 对象。
        workflows:  list[WorkflowMeta] — 全部工作流列表。
        categories: list[str] — 已排序的去重分类列表。

    Requires:
        - web_ui/templates/index.html 存在
        - workflow_registry 已完成首次扫描

    SideEffects:
        - 若缓存未初始化，触发首次磁盘扫描
    """
    workflows = workflow_registry.get_all()
    categories = sorted(set(w.category for w in workflows))
    # 转为 dict 列表以便 Jinja2 tojson 序列化
    workflow_dicts = [
        {k: v for k, v in w.__dict__.items() if not k.startswith("_")}
        for w in workflows
    ]
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "workflows": workflow_dicts,
            "categories": categories,
        },
    )


@router.get("/workflow/{workflow_id}", response_class=HTMLResponse)
async def workflow_detail(request: Request, workflow_id: str):
    """
    工作流详情页。

    展示单个工作流的完整信息，包括输入参数表单和执行按钮。

    Args:
        request:     FastAPI Request 对象。
        workflow_id: 工作流唯一标识符，如 "image_flux"。

    Returns:
        HTMLResponse: 渲染后的 workflow_detail.html 页面。

    Raises:
        HTTPException(404): 若 workflow_id 不在注册表中。

    Template Context:
        request:  Request 对象。
        workflow: WorkflowMeta 实例。

    Requires:
        - web_ui/templates/workflow_detail.html 存在
    """
    wf = workflow_registry.get_by_id(workflow_id)
    if not wf:
        raise HTTPException(
            status_code=404,
            detail=f"工作流不存在: {workflow_id}",
        )
    return templates.TemplateResponse(
        "workflow_detail.html",
        {"request": request, "workflow": wf},
    )


@router.get("/history")
async def history_redirect():
    """
    301 永久重定向：/history → /notes

    原历史页面已迁移到 /notes。
    此重定向保留至少 30 天以确保兼容性。
    """
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/notes", status_code=301)


# ── API 路由（JSON） ────────────────────────────────────────────


@router.get("/api/workflows")
async def api_workflows(category: str = "", q: str = ""):
    """
    获取工作流列表（JSON API）。

    支持按分类和关键词筛选。

    Args:
        category: 分类名称（可选）。若提供，仅返回匹配分类的工作流。
        q:        搜索关键词（可选）。若提供，在 name 中做大小写不敏感的模糊匹配。

    Returns:
        list[dict]: 工作流信息列表，每个字典包含:
            - id:          工作流 ID
            - name:        展示名称
            - category:    分类
            - source:      来源
            - description: 描述
            - tags:        标签列表
            - media_type:  媒体类型

    Example:
        GET /web/api/workflows?category=image
        GET /web/api/workflows?q=flux
        GET /web/api/workflows?category=video&q=wan

    Requires:
        - workflow_registry 已完成首次扫描

    SideEffects:
        - 若缓存未初始化，触发首次磁盘扫描
    """
    workflows = workflow_registry.get_all()
    if category:
        workflows = [w for w in workflows if w.category == category]
    if q:
        q_lower = q.lower()
        workflows = [w for w in workflows if q_lower in w.name.lower()]
    return [
        {
            "id": w.id,
            "name": w.name,
            "category": w.category,
            "source": w.source,
            "description": w.description,
            "tags": w.tags,
            "media_type": w.media_type,
        }
        for w in workflows
    ]


@router.get("/api/workflows/categories")
async def api_categories():
    """
    获取所有工作流分类列表（JSON API）。

    从已注册工作流中提取去重、排序的分类名称。

    Returns:
        list[dict]: 分类列表，每个字典包含:
            - id:   分类 ID（与 category 字段相同）
            - name: 分类名称

    Example:
        GET /web/api/workflows/categories
        → [{"id": "action", "name": "action"}, {"id": "image", "name": "image"}, ...]

    Requires:
        - workflow_registry 已完成首次扫描

    SideEffects:
        - 若缓存未初始化，触发首次磁盘扫描
    """
    cats = sorted(set(w.category for w in workflow_registry.get_all()))
    return [{"id": c, "name": c} for c in cats]


# ── 工作流执行 API ─────────────────────────────────────────────

@router.post("/api/workflows/{workflow_id}/execute")
async def api_execute_workflow(workflow_id: str, request: Request):
    """
    执行工作流，返回 task_id

    Args:
        workflow_id: 工作流 ID
        request: FastAPI Request（读取 JSON body）

    Returns:
        {"task_id": str, "status": "submitted"}

    Raises:
        HTTPException(404): 工作流不存在
        HTTPException(400): 参数校验失败
    """
    wf = workflow_registry.get_by_id(workflow_id)
    if not wf:
        raise HTTPException(404, f"工作流不存在: {workflow_id}")

    from web_ui.security import rate_limit_execute
    rate_limit_execute(request)

    executor = EXECUTORS.get(wf.source)
    if not executor:
        raise HTTPException(400, f"不支持的来源: {wf.source}")

    try:
        body = await request.json()
    except Exception:
        body = {}

    params = await executor.validate(wf, body)
    task_id = await executor.execute(wf, params)

    return JSONResponse({"task_id": task_id, "status": "submitted"})


@router.get("/api/workflows/{workflow_id}/progress/{task_id}")
async def api_progress_sse(workflow_id: str, task_id: str):
    """
    SSE 端点 — 推送工作流执行进度

    Args:
        workflow_id: 工作流 ID
        task_id: execute 返回的任务 ID

    Returns:
        StreamingResponse: text/event-stream 流
    """
    wf = workflow_registry.get_by_id(workflow_id)
    executor = EXECUTORS.get(wf.source) if wf else None
    if not executor:
        raise HTTPException(404, "工作流或执行器不存在")

    async def event_stream():
        for _ in range(60):  # 最多轮询 60 次
            try:
                progress = await executor.get_progress(task_id)
                yield f"data: {json.dumps(progress, ensure_ascii=False)}\n\n"
                if progress.get("status") in ("completed", "failed"):
                    break
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                break
            await asyncio.sleep(2)
        yield "data: {\"status\": \"disconnected\"}\n\n"

@router.get("/api/progress/{task_id}")
async def api_progress_poll(workflow_id: str = "", task_id: str = ""):
    """
    轮询模式 — 直接返回 JSON 进度

    Args:
        task_id: execute 返回的任务 ID
        workflow_id: 工作流 ID（可选，用于查找 executor）

    Returns:
        JSONResponse: {"progress": int, "step": str, "status": str}
    """
    executor = None
    if workflow_id:
        wf = workflow_registry.get_by_id(workflow_id)
        if wf:
            executor = EXECUTORS.get(wf.source)

    if not executor:
        # fallback: try all executors
        for ex in EXECUTORS.values():
            progress = await ex.get_progress(task_id)
            if progress.get("step") != "unknown":
                return JSONResponse(progress)
        return JSONResponse({"progress": 0, "step": "unknown", "status": "running"})

    progress = await executor.get_progress(task_id)
    return JSONResponse(progress)


# ── 设置页面 ──────────────────────────────────────────────────

@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """
    系统配置管理页面

    权限控制: 如果环境变量 SETTINGS_PASSWORD 已设置，则需要
    URL 参数 ?key=xxx 或 Cookie settings_key 匹配才能访问。
    未设置密码时直接开放（开发模式）。
    """
    import os
    req_password = os.getenv("SETTINGS_PASSWORD", "")
    if req_password:
        provided = request.query_params.get("key") or request.cookies.get("settings_key", "")
        if provided != req_password:
            return HTMLResponse(
                "<h2 style='color:#fff;text-align:center;margin-top:100px'>需要授权</h2>"
                "<form style='text-align:center;margin-top:20px'>"
                "<input name='key' type='password' placeholder='输入访问密码' "
                "style='padding:8px 16px;border-radius:8px;border:1px solid #555;background:#222;color:#fff'>"
                "<button type='submit' style='padding:8px 20px;margin-left:8px;border-radius:8px;"
                "background:#00d4ff;color:#000;border:none;cursor:pointer'>提交</button></form>",
                status_code=403
            )

    from pixelle_video.config import config_manager
    config = config_manager.config.to_dict()
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "config": config,
    })


# ── 配置 API ─────────────────────────────────────────────────

@router.get("/api/config")
async def api_get_config():
    """获取完整配置"""
    from pixelle_video.config import config_manager
    return config_manager.config.to_dict()


@router.put("/api/config")
async def api_update_config(request: Request):
    """更新配置并保存到 config.yaml"""
    from pixelle_video.config import config_manager
    body = await request.json()
    config_manager.update(body)
    config_manager.save()
    config_manager.reload()
    return {"status": "saved"}


@router.post("/api/config/test-llm")
async def api_test_llm(request: Request):
    """测试 LLM 连接"""
    from pixelle_video.config import config_manager
    from openai import AsyncOpenAI
    body = await request.json()
    try:
        client = AsyncOpenAI(
            api_key=body.get("api_key") or config_manager.config.llm.api_key,
            base_url=body.get("base_url") or config_manager.config.llm.base_url,
        )
        r = await client.chat.completions.create(
            model=body.get("model") or config_manager.config.llm.model or "gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=10,
        )
        return {"status": "ok", "model": r.model, "response": r.choices[0].message.content}
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=400)


@router.post("/api/config/test-comfyui")
async def api_test_comfyui(request: Request):
    """测试 ComfyUI 连接"""
    import httpx
    body = await request.json()
    url = (body.get("comfyui_url") or "").strip()
    if not url:
        return JSONResponse({"status": "error", "message": "ComfyUI URL 未配置"}, status_code=400)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{url}/system_stats")
            if r.status_code == 200:
                data = r.json()
                return {"status": "ok", "device": data.get("system", {}).get("device", "unknown")}
            return JSONResponse({"status": "error", "message": f"HTTP {r.status_code}"}, status_code=400)
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=400)


@router.post("/api/preview/tts")
async def api_preview_tts(request: Request):
    """TTS 预览 — 生成语音并返回音频"""
    from pixelle_video.service import pixelle_video
    body = await request.json()
    text = (body.get("text") or "").strip()
    if not text:
        raise HTTPException(400, "text 不能为空")
    try:
        await pixelle_video.initialize()
        voice = body.get("voice", "zh-CN-YunjianNeural")
        speed = body.get("speed", 1.2)
        result = await pixelle_video.tts(text=text, voice_id=voice, speed=speed)
        if result and result.audio_path:
            from fastapi.responses import FileResponse
            return FileResponse(result.audio_path, media_type="audio/mpeg")
        return JSONResponse({"status": "error", "message": "TTS 生成失败"}, status_code=500)
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


# ── 上传作品页面 ────────────────────────────────────────────

@router.get("/quick", response_class=HTMLResponse)
async def quick_create_page(request: Request):
    """快捷创作页面"""
    return templates.TemplateResponse("quick.html", {"request": request})


@router.get("/styles", response_class=HTMLResponse)
async def styles_page(request: Request):
    """风格模板展示页 — 25 种画面模板"""
    TEMPLATE_INFO = {
        "image_default": ("默认图片", "标准竖屏排版，适合通用视频", "图片"),
        "image_blur_card": ("毛玻璃卡片", "背景模糊+文字卡片，现代简洁", "图片"),
        "image_book": ("书本翻页", "仿书本排版，适合知识类内容", "图片"),
        "image_cartoon": ("卡通动漫", "卡通风格装饰，活泼可爱", "图片"),
        "image_elegant": ("优雅简约", "大留白+衬线字体，高端质感", "图片"),
        "image_excerpt": ("文摘卡片", "半透明卡片叠加，文艺清新", "图片"),
        "image_fashion_vintage": ("时尚复古", "复古色调+怀旧纹理", "图片"),
        "image_full": ("全屏大图", "图片全屏铺满，沉浸式视觉", "图片"),
        "image_healing": ("治愈温暖", "暖色调+柔和边框，治愈系", "图片"),
        "image_health_preservation": ("养生保健", "养生主题配色", "图片"),
        "image_life_insights": ("生活感悟", "生活哲理类排版，温暖走心", "图片"),
        "image_life_insights_light": ("生活感悟浅色", "浅色版，清爽明亮", "图片"),
        "image_long_text": ("长文本", "适合大段文字，阅读优先", "图片"),
        "image_modern": ("现代简约", "几何线条+无衬线，现代感", "图片"),
        "image_neon": ("霓虹灯", "赛博朋克霓虹风格", "图片"),
        "image_psychology_card": ("心理卡片", "心理学主题配色", "图片"),
        "image_purple": ("紫色梦幻", "紫色渐变+梦幻元素", "图片"),
        "image_satirical_cartoon": ("讽刺漫画", "漫画分格排版", "图片"),
        "image_simple_black": ("极简黑", "纯黑背景+白字", "图片"),
        "image_simple_line_drawing": ("简笔画", "手绘线条风格，清新可爱", "图片"),
        "video_default": ("默认视频", "横屏视频模板", "视频"),
        "video_healing": ("治愈视频", "暖色叠加+柔和动画", "视频"),
        "static_default": ("静态默认", "纯文字静态模板", "静态"),
        "static_excerpt": ("静态文摘", "文摘卡片静态版", "静态"),
        "asset_default": ("素材默认", "自定义素材模板", "其他"),
    }
    import os as _os
    style_list = []
    for key, (name, desc, cat) in TEMPLATE_INFO.items():
        # 找预览图片（原网站已预生成 48 张截图）
        preview = ""
        for ext in [".jpg", ".png"]:
            for suffix in ["", "_en"]:
                p = f"docs/images/1080x1920/{key}{suffix}{ext}"
                if _os.path.exists(p):
                    preview = "/" + p
                    break
            if preview: break
        style_list.append({
            "key": key, "name": name, "desc": desc, "category": cat, "preview": preview,
        })
    return templates.TemplateResponse("styles.html", {"request": request, "styles": style_list})


@router.get("/templates/{size}/{name}")
async def serve_template(size: str, name: str):
    """提供模板 HTML，替换占位符 + 添加 viewport 适配"""
    import re
    tpl_path = Path(f"templates/{size}/{name}")
    if not tpl_path.exists():
        raise HTTPException(404, "模板不存在")
    html = tpl_path.read_text(encoding="utf-8")
    # 替换占位符
    for old, new in {
        "{{title}}":"示例标题","{{subtitle}}":"示例副标题",
        "{{narration}}":"示例旁白文本，用于展示模板排版效果。",
        "{{image}}":"","{{author}}":"作者名","{{brand}}":"品牌名",
        "{{describe}}":"示例描述文字","{{text}}":"示例文本",
        "{{subtitle=作者}}":"作者名",
    }.items():
        html = html.replace(old, new)
    html = re.sub(r"\{\{\w+=(.+?)\}\}", r"\1", html)
    html = re.sub(r"\{\{.*?\}\}", "", html)
    # 注入 viewport 缩放：让 1080x1920 的模板适应浏览器窗口
    html = html.replace("</head>",
        '<meta name="viewport" content="width=1080,initial-scale=0.4">'
        '<style>body{background:#fafafa!important}'
        '.pv-template-wrapper{max-width:1080px;margin:0 auto;overflow-x:hidden}'
        '</style></head>')
    return HTMLResponse(html)


@router.get("/storyboard", response_class=HTMLResponse)
async def storyboard_page(request: Request, style: str = ""):
    """分镜脚本生成页面 — 可选 style 参数传入风格模板"""
    style_prompt = ""
    if style:
        from web.prompt_templates import BUILTIN_TEMPLATES
        tpl = BUILTIN_TEMPLATES.get(style)
        if tpl:
            style_prompt = tpl.prompt
    return templates.TemplateResponse("storyboard.html", {
        "request": request,
        "style_key": style,
        "style_prompt": style_prompt,
    })


@router.get("/debug/storyboard", response_class=HTMLResponse)
async def debug_storyboard_page(request: Request):
    """分镜调试页面"""
    return templates.TemplateResponse("debug_storyboard.html", {"request": request})


@router.post("/api/storyboard/generate")
async def api_generate_storyboard(request: Request):
    """LLM 生成分镜脚本"""
    from pixelle_video.service import pixelle_video
    from pixelle_video.utils.content_generators import generate_scene_breakdown
    body = await request.json()
    article = body.get("article", "").strip()
    media_type = body.get("media_type", "image")

    if not article:
        raise HTTPException(400, "请输入文章内容")

    try:
        await pixelle_video.initialize()
        scenes = await generate_scene_breakdown(
            llm_service=pixelle_video.llm,
            article=article,
            media_type=media_type,
        )
        return JSONResponse({"scenes": scenes, "total": len(scenes)})
    except Exception as e:
        logger.error(f"Storyboard generation failed: {e}")
        raise HTTPException(500, str(e))


# ── 纯文本记录 ──────────────────────────────────────────────

@router.get("/notes", response_class=HTMLResponse)
async def notes_page(request: Request, page: int = 1):
    """纯文本记录页面 — 15条/页"""
    from web_ui.notes_storage import list_notes
    all_notes = list_notes()
    total = len(all_notes)
    page_size = 15
    total_pages = max(1, (total + page_size - 1) // page_size)
    start = (page - 1) * page_size
    return templates.TemplateResponse("notes.html", {
        "request": request,
        "notes": all_notes[start:start + page_size],
        "page": page, "total_pages": total_pages, "total": total,
    })


@router.post("/api/notes")
async def api_add_note(request: Request):
    """新增记录"""
    from web_ui.notes_storage import add_note
    body = await request.json()
    note = add_note(body.get("title", ""), body.get("content", ""))
    return JSONResponse(note)


@router.put("/api/notes/{note_id}")
async def api_update_note(note_id: str, request: Request):
    """编辑记录"""
    from web_ui.notes_storage import update_note
    body = await request.json()
    result = update_note(note_id, body.get("title", ""), body.get("content", ""))
    if not result:
        raise HTTPException(404, "记录不存在")
    return JSONResponse(result)


@router.delete("/api/notes/{note_id}")
async def api_delete_note(note_id: str):
    """删除记录"""
    from web_ui.notes_storage import delete_note
    if not delete_note(note_id):
        raise HTTPException(404, "记录不存在")
    return JSONResponse({"deleted": True})


@router.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request):
    """独立上传作品页面"""
    return templates.TemplateResponse("upload.html", {"request": request})


@router.get("/category/{category_name}", response_class=HTMLResponse)
async def category_page(request: Request, category_name: str):
    """分类作品页面 — 仅展示该分类的作品"""
    from web_ui.works_storage import get_by_category, get_uploaded
    works_data = get_by_category(category_name)
    total_all = get_uploaded().get("total", 0)
    cat_labels = {"数字人": "digital_human", "图片生成": "image", "视频生成": "video", "动作模仿": "action"}
    display_name = {v: k for k, v in cat_labels.items()}.get(category_name, category_name)
    return templates.TemplateResponse("category.html", {
        "request": request,
        "category_name": category_name,
        "display_name": display_name,
        "total": works_data["total"],
        "works": works_data["works"],
        "total_all": total_all,
    })


# ── 作品 API ────────────────────────────────────────────────

@router.post("/api/works/upload")
async def api_upload_work(request: Request):
    """上传作品（multipart/form-data），上传成功即发布"""
    from web_ui.works_storage import add_work

    form = await request.form()
    title = str(form.get("title", "未命名作品"))
    author = str(form.get("author", "匿名"))
    category = str(form.get("category", ""))
    description = str(form.get("description", ""))
    file = form.get("file")
    if not file or not hasattr(file, "filename"):
        raise HTTPException(400, "请上传作品文件")

    filename = file.filename or "untitled"
    work_id = str(uuid.uuid4())[:12]
    work_dir = Path("works") / work_id
    work_dir.mkdir(parents=True, exist_ok=True)
    ext = Path(filename).suffix.lower()
    media_type = "video" if ext in (".mp4", ".mov", ".webm", ".avi") else "image"
    file_path = str(work_dir / filename)

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    work = add_work(title=title, author=author, file_path=file_path,
                    media_type=media_type, category=category, description=description)
    return JSONResponse({"status": "uploaded", "work_id": work["work_id"]})


@router.get("/api/works/uploaded")
async def api_uploaded_works(page: int = 1, page_size: int = 12):
    """获取上传成功的作品列表（分页）"""
    from web_ui.works_storage import get_uploaded
    return get_uploaded(page=page, page_size=page_size)


@router.get("/api/notes")
async def api_notes_new(page: int = 1, page_size: int = 20, status: str = ""):
    """获取历史记录（新路径 /api/notes）"""
    try:
        from pixelle_video.service import pixelle_video
        await pixelle_video.initialize()
        return await pixelle_video.persistence.list_tasks_paginated(
            page=page, page_size=page_size, status=status or None,
        )
    except Exception as e:
        logger.error(f"Failed to load history: {e}")
        return {"tasks": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 0}


@router.get("/api/history")
async def api_history(page: int = 1, page_size: int = 20, status: str = ""):
    """
    获取历史记录列表

    Args:
        page: 页码（从 1 开始）
        page_size: 每页条数
        status: 状态筛选（可选）

    Returns:
        {"tasks": list, "total": int, "page": int, "page_size": int, "total_pages": int}
    """
    try:
        from pixelle_video.service import pixelle_video

        await pixelle_video.initialize()
        persistence = pixelle_video.persistence
        result = await persistence.list_tasks_paginated(
            page=page, page_size=page_size,
            status=status or None,
        )
        return result
    except Exception as e:
        logger.error(f"Failed to load history: {e}")
        return {"tasks": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 0}


@router.delete("/api/history/{task_id}")
async def api_delete_history(task_id: str):
    """
    删除历史记录

    Args:
        task_id: 任务 ID

    Returns:
        {"deleted": bool}
    """
    try:
        from pixelle_video.service import pixelle_video
        await pixelle_video.initialize()
        ok = await pixelle_video.persistence.delete_task(task_id)
        return {"deleted": ok}
    except Exception as e:
        raise HTTPException(500, str(e))
