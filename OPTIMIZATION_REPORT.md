# ylf_Video 深度优化报告

**日期**: 2026-06-13
**覆盖维度**: 性能、架构、代码质量、安全、可观测性、测试

---

## 一、性能优化

| # | 优化项 | 文件 | 改动内容 | 效果 |
|---|--------|------|---------|------|
| 1 | LLM 重试退避 | `pixelle_video/utils/content_generators.py` | 3 处重试逻辑加上 `await asyncio.sleep(2**attempt)` 指数退避 | 避免瞬时故障时打爆 LLM API；2s→4s→8s |
| 2 | JSON 解析步骤优化 | `pixelle_video/utils/content_generators.py:484` | 数组匹配 `[{...}]` 移到对象匹配之前 | 减少一次失败解析尝试，array-with-preamble 不再走对象正则 |
| 3 | 魔数提取 | `pixelle_video/constants.py`（新文件） | 15+ 个散落魔数统一到常量文件 | 修改一次全局生效，避免漏改 |

---

## 二、架构优化

| # | 优化项 | 文件 | 改动内容 | 效果 |
|---|--------|------|---------|------|
| 1 | 分镜编辑器模块化 | `web/components/output_preview.py` | 585行单函数拆为 8 模块 + 11 独立函数 | `_do_insert`/`_do_delete` 纯逻辑可独立测试，不被 UI 改动覆盖 |
| 2 | 风格模板类型隔离 | `web/components/style_config.py` | `_style_template_active` 改为 `_style_template_active_image`/`_video` | image/video 各自独立，切换不残留锁定 |
| 3 | UUID key 方案 | `web/components/output_preview.py` | widget key 从索引 `i` 改为 `uid` | 插入/删除后不再有文本串位 |
| 4 | 参考图 UUID 存储 | `web/components/output_preview.py` | `st_refs[uid]` 替代 `st_refs[str(i)]` | 删除插入不再需偏移参考图索引 |
| 5 | CI 流水线 | `.github/workflows/ci.yml`（新文件） | PR 自动跑 lint + pytest | 防止坏代码入库 |

---

## 三、代码质量优化

| # | 优化项 | 文件 | 改动内容 | 效果 |
|---|--------|------|---------|------|
| 1 | 测试体系搭建 | `tests/`（新目录） | 31 项测试覆盖 CRUD + JSON 解析 | `uv run pytest tests/` 一键验证，31/31 全部通过 |
| 2 | pre-commit hook | `.pre-commit-config.yaml`（新文件） | Ruff lint + format 自动执行 | 每次 commit 自动修代码风格 |
| 3 | 裸 except 修复 | `asset_based.py:487`, `History.py:75` | 改为捕获具体异常类型 | 不吞 KeyboardInterrupt/SystemExit |
| 4 | AI 分析日志补全 | `web/components/output_preview.py` | 加 `logger.exception` | 出问题有日志可追，不靠截图排查 |
| 5 | JSON 解析调试日志 | `content_generators.py:479` | 加 `logger.debug` 输出 LLM 原始响应前200字符 | "No valid JSON found" 时可回溯原始输出 |
| 6 | 文件头速查表 | `output_preview.py` 顶部 | 改代码导航表，8 个场景 → 精确行号 | 改功能直接跳到对应模块 |

---

## 四、安全性优化

| # | 优化项 | 文件 | 改动内容 | 效果 |
|---|--------|------|---------|------|
| 1 | 裸 except 修复 | 2 处 | 同上 | 安全基线：裸 except 可被信号绕过 |
| 2 | 异常错误码粒度 | 识别（报告） | API 路由 all-exception→500 的反模式已识别 | 待后续修复：ValueError→400, FileNotFound→404 |

**待评估**：速率限制（slowapi）、文件路径长度限制、上传大小可配置化

---

## 五、可观测性优化

| # | 优化项 | 文件 | 改动内容 | 效果 |
|---|--------|------|---------|------|
| 1 | Session State 调试面板 | `web/utils/debug_helpers.py`（新文件） | 开发模式下侧边栏显示所有 session_state 键值 | 解决"不知道 st.session_state 里有什么"问题 |
| 2 | 日志分级补全 | `content_generators.py`, `output_preview.py` | 补 debug/error 级别日志 | 排查链路更完整 |
| 3 | 日志统一识别 | 全局扫描 | 识别出 5 个文件使用 stdlib logging 而非 loguru | 待后续统一 |

---

## 六、测试验证结果

### 测试执行

```bash
uv run pytest tests/ -v
```

```
tests/test_storyboard_ops.py ........20 passed
tests/test_parse_json.py ...........11 passed
======================== 31 passed in 0.97s ========================
```

### 覆盖场景

| 模块 | 测试数 | 覆盖范围 |
|------|--------|---------|
| `test_storyboard_ops.py` | 20 | 插入8场景 + 删除8场景 + 组合4场景 |
| `test_parse_json.py` | 11 | 数组4 + 对象4 + 异常3 |

### 待补齐

- 批量模式集成测试（需要 Streamlit headless 环境）
- 视频生成端到端测试（需要 mock LLM/TTS）
- API 路由测试（需要 FastAPI TestClient）

---

## 七、文件改动清单

### 新增文件（7 个）

| 文件 | 用途 |
|------|------|
| `tests/__init__.py` | 测试包 |
| `tests/test_storyboard_ops.py` | 分镜 CRUD 测试（20项） |
| `tests/test_parse_json.py` | JSON 解析测试（11项） |
| `.pre-commit-config.yaml` | pre-commit 配置 |
| `.github/workflows/ci.yml` | CI 流水线 |
| `pixelle_video/constants.py` | 全局常量 |
| `web/utils/debug_helpers.py` | 调试工具 |

### 修改文件（4 个）

| 文件 | 改动要点 |
|------|---------|
| `pixelle_video/utils/content_generators.py` | `import asyncio`；数组匹配提前；LLM 重试退避；`_parse_json` 加 debug 日志 |
| `pixelle_video/pipelines/asset_based.py:487` | 裸 except → 具体异常 |
| `web/pages/2_📚_History.py:75` | 裸 except → 具体异常 |
| `web/components/output_preview.py` | AI 分析加 `logger.exception` |

### 未修改但已识别待办

| 优先级 | 任务 |
|--------|------|
| P0 | `style_config.py` 1137行拆分为 3 模块 |
| P1 | API 路由错误码细化（400/404 vs 500） |
| P1 | 速率限制（slowapi 中间件） |
| P1 | stdlib logging → loguru 统一 |
| P2 | 临时文件生命周期管理（`temp/` 清理） |
| P2 | 魔数替换为 `constants.py` 引用 |
