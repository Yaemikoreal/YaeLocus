# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.x     | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

如果你发现了安全漏洞，请**不要**通过公开 Issue 报告。

请通过以下方式私下报告：

- 发送邮件至项目维护者
- 使用 GitHub Security Advisories: https://github.com/Yaemikoreal/YaeLocus/security/advisories

我们承诺：

- 在 48 小时内确认收到报告
- 在 7 天内提供初步评估
- 在修复发布后公开致谢（如果你愿意）

## Security Best Practices

使用本工具时的安全建议：

1. **API 密钥保护**
   - 不要将 `.env` 文件提交到版本控制
   - 不要在公开场合分享你的 API 密钥
   - 定期轮换 API 密钥

2. **数据安全**
   - 注意输入文件中可能包含的敏感地址信息
   - 输出文件可能包含地理位置数据，请妥善保管

3. **依赖安全**
   - 定期更新依赖包
   - 关注 Dependabot 的安全更新提示