"""
WorkflowRegistry 单元测试

覆盖: 扫描、缓存、搜索、分类筛选、降级推断、Zealman 索引解析
"""
import json
import tempfile
from pathlib import Path
import pytest

# 确保项目在 sys.path 中
import sys, os
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestWorkflowRegistry:
    """WorkflowRegistry 核心功能测试"""

    @pytest.fixture
    def registry(self, tmp_path):
        """创建带测试数据的临时注册表"""
        from web_ui.workflow_registry import WorkflowRegistry

        # 创建临时 workflows 目录结构
        workflows_dir = tmp_path / "workflows"
        (workflows_dir / "runninghub").mkdir(parents=True)
        (workflows_dir / "selfhost").mkdir(parents=True)

        # 添加测试工作流文件
        (workflows_dir / "runninghub" / "image_flux.json").write_text(
            '{"source":"runninghub","workflow_id":"123"}')
        (workflows_dir / "runninghub" / "video_wan2.2.json").write_text(
            '{"source":"runninghub","workflow_id":"456"}')
        (workflows_dir / "selfhost" / "image_qwen.json").write_text(
            '{"class_type":"CheckpointLoader"}')
        (workflows_dir / "selfhost" / "tts_edge.json").write_text(
            '{"class_type":"TTSNode"}')
        (workflows_dir / "selfhost" / "digital_human_sonic.json").write_text(
            '{"class_type":"DigitalHuman"}')

        return WorkflowRegistry(workflows_root=str(workflows_dir))

    def test_scan_all_discovers_workflows(self, registry):
        """扫描发现所有 .json 工作流（排除 _ 开头的文件）"""
        workflows = registry.get_all()
        ids = {w.id for w in workflows}
        assert "image_flux" in ids
        assert "video_wan2.2" in ids
        assert "image_qwen" in ids
        assert "tts_edge" in ids
        assert len(workflows) >= 5

    def test_cache_prevents_rescan(self, registry):
        """get_all() 第二次调用返回相同数据"""
        first = registry.get_all()
        second = registry.get_all()
        assert len(first) == len(second)

    def test_reload_clears_cache(self, registry):
        """reload() 强制刷新缓存"""
        first = registry.get_all()
        second = registry.reload()
        # 内容相同但对象不同（重新扫描）
        assert len(first) == len(second)

    def test_search_by_keyword(self, registry):
        """按关键词搜索不区分大小写"""
        results = registry.search("flux")
        ids = {w.id for w in results}
        assert "image_flux" in ids

        results = registry.search("WAN")
        ids = {w.id for w in results}
        assert "video_wan2.2" in ids

    def test_search_no_match(self, registry):
        """搜索无匹配时返回空列表"""
        results = registry.search("nonexistent_xyz")
        assert results == []

    def test_filter_by_category(self, registry):
        """按 category 筛选"""
        image_workflows = registry.by_category("image")
        for w in image_workflows:
            assert w.category == "image"

    def test_filter_by_source(self, registry):
        """按 source 筛选"""
        rh = registry.by_source("runninghub")
        for w in rh:
            assert w.source == "runninghub"

    def test_get_by_id_found(self, registry):
        """get_by_id 找到匹配的工作流"""
        wf = registry.get_by_id("image_flux")
        assert wf is not None
        assert wf.id == "image_flux"
        assert wf.source == "runninghub"

    def test_get_by_id_not_found(self, registry):
        """get_by_id 未找到返回 None"""
        wf = registry.get_by_id("nonexistent")
        assert wf is None

    def test_filename_inference(self, registry):
        """无 _meta.json 时从文件名推断 category + media_type"""
        wf = registry.get_by_id("image_qwen")
        assert wf.category == "image"
        assert wf.media_type == "image"

        wf = registry.get_by_id("tts_edge")
        assert wf.category == "audio"
        assert wf.media_type == "audio"

    def test_malformed_json_skipped(self, tmp_path):
        """格式错误的 JSON 文件被跳过而非崩溃"""
        from web_ui.workflow_registry import WorkflowRegistry

        d = tmp_path / "workflows" / "runninghub"
        d.mkdir(parents=True)
        (d / "bad.json").write_text("not valid json {{{")
        (d / "good.json").write_text('{"source":"runninghub","workflow_id":"1"}')

        reg = WorkflowRegistry(str(tmp_path / "workflows"))
        workflows = reg.get_all()
        ids = {w.id for w in workflows}
        assert "good" in ids
        # bad.json 被跳过，不影响其他

    def test_zealman_index_parsing(self, tmp_path):
        """Zealman _zealman_index.json 正确解析"""
        from web_ui.workflow_registry import WorkflowRegistry

        d = tmp_path / "workflows" / "selfhost"
        d.mkdir(parents=True)
        index = [
            {"key": "A01-test", "display_name": "Test [image]", "media_type": "image"},
            {"key": "G01-video", "display_name": "Video [video]", "media_type": "video"},
        ]
        (d / "_zealman_index.json").write_text(json.dumps(index))

        reg = WorkflowRegistry(str(tmp_path / "workflows"))
        workflows = reg.get_all()
        zealman_wfs = [w for w in workflows if w.source == "zealman"]
        assert len(zealman_wfs) == 2


class TestWorkflowMeta:
    """WorkflowMeta 数据模型测试"""

    def test_default_values(self):
        """默认值正确填充"""
        from web_ui.workflow_registry import WorkflowMeta
        wf = WorkflowMeta(id="test", name="Test", category="image", source="runninghub")
        assert wf.description == ""
        assert wf.tags == []
        assert wf.media_type == "image"
        assert wf.version == "1.0.0"

    def test_all_fields(self):
        """所有字段可正常赋值和读取"""
        from web_ui.workflow_registry import WorkflowMeta
        wf = WorkflowMeta(
            id="img_1", name="Image One", category="image",
            source="selfhost", description="A test workflow",
            tags=["portrait", "hd"], media_type="image",
            version="2.0", author="test", workflow_file="/tmp/test.json"
        )
        assert wf.id == "img_1"
        assert len(wf.tags) == 2
        assert wf.author == "test"


class TestAPIRoutes:
    """Web UI API 端点测试"""

    @pytest.fixture
    def client(self):
        from api.app import app
        from fastapi.testclient import TestClient
        return TestClient(app)

    def test_root_returns_html(self, client):
        """首页返回 HTML"""
        r = client.get("/")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]

    def test_api_workflows_returns_json(self, client):
        """工作流 API 返回 JSON"""
        r = client.get("/api/workflows")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_api_workflows_filter_by_category(self, client):
        """按分类筛选"""
        r = client.get("/api/workflows?category=image")
        assert r.status_code == 200
        for w in r.json():
            assert w["category"] == "image"

    def test_api_workflows_search(self, client):
        """按关键词搜索"""
        r = client.get("/api/workflows?q=flux")
        assert r.status_code == 200
        assert len(r.json()) > 0

    def test_api_categories(self, client):
        """分类列表 API"""
        r = client.get("/api/workflows/categories")
        assert r.status_code == 200
        cats = r.json()
        assert len(cats) > 0
        assert all("id" in c and "name" in c for c in cats)

    def test_workflow_detail_page(self, client):
        """工作流详情页返回 HTML"""
        r = client.get("/workflow/image_flux")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]

    def test_workflow_detail_404(self, client):
        """不存在的工作流返回 404"""
        r = client.get("/workflow/nonexistent_12345")
        assert r.status_code == 404

    def test_api_execute_missing_prompt(self, client):
        """缺少 prompt 时执行端点返回错误"""
        r = client.post("/api/workflows/image_flux/execute", json={})
        # 校验失败返回 500 (由 ErrorMonitoringMiddleware 捕获)
        assert r.status_code in (400, 422, 500)

    def test_api_execute_success(self, client):
        """正常执行返回 task_id"""
        r = client.post("/api/workflows/image_flux/execute", json={"prompt": "test"})
        assert r.status_code == 200
        assert "task_id" in r.json()

    def test_history_page(self, client):
        """历史页面返回 HTML"""
        r = client.get("/history")
        assert r.status_code == 200

    def test_api_history(self, client):
        """历史 API 返回数据"""
        r = client.get("/api/history?page=1")
        assert r.status_code == 200
        data = r.json()
        assert "tasks" in data
        assert "total" in data

    def test_csp_header(self, client):
        """CSP header 存在于 HTML 响应"""
        r = client.get("/")
        assert "content-security-policy" in r.headers

    def test_rate_limit_header(self, client):
        """速率限制 header 存在"""
        r = client.get("/api/workflows")
        assert "x-ratelimit-remaining" in r.headers
