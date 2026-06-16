# ylf_Video 代码规范

## 函数注释标准

每个函数/方法必须包含以下注释块：

```python
def function_name(param1: Type1, param2: Type2 = default) -> ReturnType:
    """
    [一句话功能描述]

    Args:
        param1 (Type1): [参数含义、约束条件、合法值范围]
        param2 (Type2, optional): [参数含义]。默认值: default

    Returns:
        ReturnType: [返回值的含义、可能的取值、None 的条件]

    Raises:
        ValueError: [什么情况下抛出]
        RuntimeError: [什么情况下抛出]

    Requires:
        - [外部资源1]: [用途说明]。通过 [pixelle_video.config/ENV/参数] 获取
        - [外部资源2]: [用途说明]

    Side Effects:
        - [文件写入/网络请求/状态变更等副作用]

    Examples:
        >>> result = function_name(x, y)
        >>> print(result)
        "expected output"
    """
```

## 函数设计原则

### 单一职责
- 每个函数只做一件事，函数名准确描述其行为
- 超过 50 行的函数必须拆分
- 超过 3 层嵌套的逻辑必须提取为独立函数

### 纯函数优先
- 无副作用的逻辑优先写成纯函数（放在 utils/ 下）
- 有副作用的逻辑（网络请求、文件 I/O）必须标注 `Side Effects`

### 依赖显式化
- 不在函数内部 `import` 全局配置单例
- 通过参数注入外部依赖，不在函数内隐式获取

## 修改流程

每次代码修改必须按以下顺序执行：

1. **读注释定位**：阅读目标函数及相关函数的注释，通过注释确定修改范围
2. **范围确认**：确认本次修改仅影响目标函数
3. **修改实现**：在目标函数范围内完成修改
4. **回归验证**：`pytest tests/ -x` 确保所有已有测试通过
5. **注释更新**：修改了逻辑必须同步更新注释
