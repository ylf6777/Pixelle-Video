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

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from web_ui.workflow_registry import workflow_registry

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
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "workflows": workflows,
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


@router.get("/history", response_class=HTMLResponse)
async def history(request: Request):
    """
    生成历史页面。

    展示历史生成记录的列表（当前占位页面）。

    Args:
        request: FastAPI Request 对象。

    Returns:
        HTMLResponse: 渲染后的 history.html 页面。

    Template Context:
        request: Request 对象。

    Requires:
        - web_ui/templates/history.html 存在

    Note:
        当前为占位页面。后续需接入任务历史持久化存储后补充数据上下文。
        TODO: 接入 TaskManager 历史记录 API
    """
    return templates.TemplateResponse(
        "history.html",
        {"request": request},
    )


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
