# Contributing to YaeLocus

感谢你考虑为 YaeLocus 做贡献！

## 如何贡献

### 报告 Bug

如果你发现了 bug，请通过 [Issues](https://github.com/Yaemikoreal/YaeLocus/issues) 提交，包含：

- 清晰的 bug 描述
- 复现步骤
- 期望行为与实际行为
- 运行环境信息（OS、Python 版本等）
- 相关日志

### 提出新功能

欢迎提出新功能建议！请描述：

- 功能描述
- 使用场景
- 可能的实现方式

### 提交代码

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

### 代码规范

- 遵循 PEP 8 编码规范
- 为新功能添加测试
- 更新相关文档
- 保持代码简洁清晰

### 开发环境设置

```bash
# 克隆仓库
git clone https://github.com/Yaemikoreal/YaeLocus.git
cd YaeLocus

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# 或 .venv\Scripts\activate  # Windows

# 安装开发依赖
pip install -e .[dev]

# 运行测试
pytest tests/

# 代码检查
ruff check geocode/
```

### 分支策略

- `main` - 稳定版本
- `develop` - 开发版本
- `feature/*` - 新功能
- `fix/*` - Bug 修复

## 许可证

提交代码即表示你同意你的贡献将按照 MIT 许可证授权。