# 证据型 HTML 报告

一个独立可安装的 Codex Skill：把复杂审计、技术方案和场景交接组织成中文、可追溯、可离线阅读的单文件 HTML。

- 中文结构标题、导航、状态和证据分层；保留专有名词、接口及路径。
- 按用途选结构：审计台账、技术调用链与对照表、交接检查清单。
- 重点常显、相关详情就近展开；并列对比图、分段列表和可点击材料入口。
- 搜索、状态筛选、清空、可调整宽度的详情抽屉及术语解释。
- 正文静态生成，关闭 JavaScript 仍可读；打印包含全部详情与证据。
- 生成器仅使用 Python 标准库，无 CDN、外部字体或运行依赖。

## 安装

将仓库克隆到 Codex 全局技能目录，目标目录应尚不存在：

```powershell
git clone https://github.com/boomkalakasha/evidence-html-report-skill.git "$env:USERPROFILE\.codex\skills\evidence-html-report"
```

其他支持 `SKILL.md` 的工具也可安装完整目录。已有旧版时先备份，再合并更新；不要覆盖自定义文件或在混合修改的目录中直接拉取。新会话可发现更新后的技能。

仓库名是 `evidence-html-report-skill`；技能调用名及安装目录仍为 `evidence-html-report`。

## 使用

在 Codex 中要求：

> 使用 evidence-html-report，把这次技术方案整理成中文 HTML，先说明真实入口和调用链，再列职责与验收，区分本次必做和后续预留。

也可以直接运行生成器：

```text
python scripts/build_report.py examples/technical-brief.json output-report.html
python scripts/build_report.py examples/audit.json output-audit.html
python scripts/build_report.py examples/reading-layout.json output-reading.html
```

生成的 HTML 可以直接双击打开。[技能规则](SKILL.md)、[内容模型](references/content-model.md) 和 [呈现原则](references/report-design.md) 说明字段与边界。示例是虚构设计，不包含内部报告或真实业务证据。

## 本版相对旧模板的变化

v1.1.0 增加正文内折叠、默认开闭、全部展开／收起和章节导航展开；支持短段、要点、表内列表及安全文档链接。并列对比图说明取舍，正文表格在手机上逐行保留列名，打印后恢复原折叠状态。见 [阅读编排示例](examples/reading-layout.json)。

完整变化与回退说明见 [版本变化](CHANGELOG.md)。

移除固定英文结构词；旧状态键和证据层显示中文。增加章节导航、调用步骤、对照表、检查清单及按用途调整结构。补齐责任、验收、模块类别和证据限制的展示；拦截悬空证据、重复编号与错列表格；修复打印遗漏抽屉详情。

旧 JSON 字段与常见枚举继续支持；缺少问题内容、证据或 `evidenceGap` 的数据现在会被拒绝，需按提示补齐。该技能负责报告呈现，不代替研究、产品验收或部署。

## 验证与贡献

```text
python -m unittest discover -s tests -v
python scripts/build_report.py --self-test
node --check assets/report.js
```

可选浏览器回归：安装 `requirements-dev.txt` 并运行 `python -m playwright install chromium`，再执行 `python tests/browser_checks.py`。它检查桌面和 390 px、搜索筛选、抽屉焦点、术语、上下文折叠、链接、手机表头、打印恢复和静态阅读。

问题和改进建议通过仓库 Issues／PR 提交。提交公开样例前请移除内部业务、客户信息、机器路径和凭据；新增组件需覆盖真实阅读及打印行为。发现安全问题请参阅 [安全说明](SECURITY.md)。

## 许可证

Apache License 2.0，见 [LICENSE](LICENSE)。
