# 内容模型

生成器只依赖 Python 标准库，输入为 UTF-8 JSON，输出为一个内联样式和脚本的 HTML。内部字段名保持英文，正文和界面默认中文。旧版数据无需改名即可生成。

## 基本字段

| 字段 | 要求／用途 |
| --- | --- |
| `title`、`generatedAt` | 必填非空字符串；标题和生成时间 |
| `subtitle`、`audience`、`scope` | 可选；副标题、读者、固定版本／环境等范围数组 |
| `reportType` | `audit`（默认）、`brief` 或 `handoff`；展示为“审计评估”“技术方案简报”“场景交接” |
| `verdict` | 必填对象：`label`、`summary`；`blocker` 可空，空时显示“未登记阻断；请结合证据范围判断” |
| `findings`、`evidence` | 必填数组，允许为空；简报与交接不必制造问题 |
| `metrics` | 可选 `{label,value,note}` 数组；只放有意义的实测统计，不自动制造完成率 |

## 问题与证据

`findings[]`：`id`、`title`、`status`、`summary` 必填，`priority`、`owner`、`assessment[]`、`actions[]` 可选。`evidence[]` 为证据编号数组；没有证据时必须写非空 `evidenceGap`。`factKind` 可标 `current`、`historical`、`inference`、`unverified` 或 `planned`，显示中文。

`evidence[]`：`id`、`level`、`source`、`summary` 必填；`date`、`scope`、`limitation`、`factKind` 可选。证据编号不得重复，悬空引用阻止生成。来源用描述性引用，必要完整路径放在证据或来源索引。

原项入口可选字段：`href` 是安全的文档／网页链接，`locator` 是文件行、记录号、方法名、日期等具体定位；`accessNote` 说明权限或无法跳转的原因。没有 `href` 时清单显示来源、定位及访问说明，旧数据仍可用。`items[]` 支持字符串或普通条目对象（含 `body`、`status`、`links` 等），用于列出一组验证的具体项目和结果。不要用总数替代逐项凭证。

`verdict`、章节及详情、条目、步骤、表格富文本单元格、附录都可用 `evidence: ["证据一"]` 就近引用已登记编号。所有引用统一指向“证据范围”下的清单行；跳转会展开清单并定位该项。`evidenceLayers[].evidence[]` 可选择同层记录，省略则列出该层全部记录；不能借用其他证据层的通过结果。缺失编号或跨层引用阻止生成。空登记表不会制造凭证，界面明确提示没有逐项证据。

```json
{"id":"证据一","level":"SOURCE_BUILD","source":"固定版本测试记录","summary":"入口校验的两项测试通过","href":"./test-results.txt","locator":"记录中的成功与无效输入检查","items":[{"title":"成功路径","body":"结果字段与输入一致","status":"verified"},{"title":"无效输入","body":"拒绝缺失字段","status":"verified"}],"limitation":"不证明业务数据已经入库"}
```

证据层：`SOURCE_BUILD` → 源码与构建，`RUNTIME_UI` → 运行与交互，`DATA_BUSINESS` → 数据与业务，`RELEASE_CUTOVER` → 发布与切流。支持旧版自定义 `level`，建议用中文；未知英文层名显示“其他证据”，原始值在资料 JSON 保留。

`evidenceLayers[]` 可显式写 `{level,status,reason}`；`status` 支持 `verified`、`not_run`、`not_applicable`、`unknown` 或中文。如果不提供，生成器对有记录的层只显示“已登记证据”，其余显示“待确认：未登记该层证据或不适用说明”。登记证据不等于验收通过。

兼容状态：`implemented`／`complete` → 已实现／已完成，`partial` → 部分实现，`drift` → 存在偏离，`missing` → 未实现，`unverified` → 待验证；中文状态原样保留。未知英文状态显示“待说明”，可通过 `statusLabels` 对象提供中文含义。证据类型同理，通过 `factLabels` 覆盖自定义分类；不要猜含义。

## 正文章节

`sections[]` 共有 `id`、`title`、`summary`（可选）和 `kind`：

- `cards`（默认）／`checklist`：`items[]` 为字符串，或 `{title,body,meta,status,owner,acceptance,dependency,modules,outcome,scope}`。责任与验收字段完整展示。
- `table`：`columns[]` 为非空中文表头数组，`rows[]` 为等长单元格数组。单元格支持字符串、数字或下述段落列表对象；避免长段落。
- `flow`：`steps[]` 为 `{title,body,edge}`。`edge` 为到下一步的调用方式；最后一步不应带出口标签。步骤顺序与原始契约一致。
- `comparison`：`items[]` 为 2 至 4 组同维度内容，结构同普通条目；可用 `outcome` 描述它们的共同结果或取舍。这是并列关系图，不生成评分。

### 段落、列表与链接

条目、步骤、结论、章节与附录都可添加 `paragraphs[]`、`bullets[]`、`links[]`。`body` 仍支持字符串；单换行保留停顿，双换行分段。表格单元格也可写为 `{text,paragraphs,bullets,links}`，替代长字符串。所有内容安全转义，不支持原始 HTML。

```json
{"paragraphs": ["先说明结果。", "再说明限制。"], "bullets": ["逐项核对。"], "links": [{"label": "打开原始报告", "href": "../original.html"}]}
```

显式链接必须包含非空 `label`、`href`。允许不带凭据的 HTTP／HTTPS、章节锚点、本地文档相对路径及本地 `file` URI；相对路径与 file 路径仅支持 HTML、PDF、Markdown、文本、JSON、常见图片等文档后缀。禁止命令协议、脚本 URL、协议相对地址和可执行文件。文件不会被生成器读取，存在性及分享后的可达性由报告作者核对。公开示例不要包含本机路径。

正文中的裸 HTTP／HTTPS 地址自动生成链接；末尾中文标点不计入地址。外部网页在新标签页打开，附带 `noopener noreferrer`；离线阅读正文不需要访问这些网址。`sources[]` 可额外带 `href`，配合 `label` 生成描述性材料入口。

链接检查覆盖用户信息和常见敏感参数，例如 `access_token`、`password`、`api_key`；无法猜测任意参数的业务含义。被排除的裸网址保持纯文本，显式链接报错。报告内容仍需在输入前脱敏，此检查不能替代完整的公开内容审查。

### 正文内折叠

`sections[].folds[]` 复用同样的 `title`、`summary`、`kind` 和内容字段，放在本章节主体之后。`open: true` 可默认展开，否则收起；详情嵌套最多两层。章节 `collapsed: true` 将主体整体收起，可用 `foldLabel` 说明内容；该章标题和摘要仍可见，适用于补充清单而非核心结论。

```json
{"id":"contracts","title":"职责与契约","summary":"先看职责摘要。","items":[{"title":"集成组","body":"关联请求与结果。"}],"folds":[{"title":"查看字段与验收明细","kind":"table","columns":["字段","含义"],"rows":[["taskId","关联请求与回调"]]}]}
```

有折叠时页面提供“展开全部详情／收起全部详情”；无 JavaScript 时原生折叠仍可用。章节导航展开该章主体，不展开全部补充块。打印统一展开并恢复打印前的开闭状态。完整例子见 [阅读编排示例](../examples/reading-layout.json)。

`sections` 按输入顺序显示在问题台账之前，导航使用标题。无问题时隐藏台账。生成器统一编号章与详情（如 `2`、`2.1`、`2.1.1`），无需在输入标题手写编号；顶部“完整目录”包含各层链接，正文与打印保留相同编号。内部详情锚点自动避开用户章节 ID；选择某个详情只展开它及其必要父级。当前阅读位置为章节序号／总章数，不表示已阅读完成。

其他兼容字段：

- `responsibilities[]`：`{group,mission,modules,acceptance,owner}`，生成“职责与验收”。
- `modules[]`：`{name,category,priority,owner,gap,outcome,acceptance,dependency}`；`required`／`本次必做` 与 `future`／`后续预留` 分组，其余显示“其他模块”。
- `appendices[]`：`{title,body,items}`，默认折叠，打印展开。
- `sources[]`：`{label,ref,note}`，生成来源索引。
- `glossary[]`：`{term,full?,explanation,aliases?,original?,source?,scopeNote?,evidence?,matchMode?}`。`explanation` 是通俗解释，`original` 是忠实原文摘录，填写原文必须有非空 `source`；`scopeNote` 说明归纳命名或时效等边界。`evidence` 引用同一证据清单并通向原项。所有字段是纯文本，不支持 HTML。
- `requiredTerms[]`：明确承诺原文释义的关键项，以 `glossary[].term` 精确名称列出。每项须有非空 `full`（中文名称）、`original`、`source`；缺定义或没有在正文、表格／详情实际注释时阻止生成。术语表自身不计覆盖；没有列入本清单的旧术语继续兼容。这个门禁不能自动发现作者未登记的约定，作者仍须从用户请求逐项建立清单。

单字母代号必须显式设置 `matchMode: "code"`，区分大小写，排除盘符 `C:/`／`C:\\`、带连字符或下划线的编号 `D-001`／`D_001`，一般边界也排除 `E01` 等证据编号。仍需核对同字母在不同语境中的含义；同一代号有冲突时改用完整名称／明确别名或定制就地说明，不把多种定义合并成一个术语。默认 `word` 模式保留普通术语及别名的完整单词匹配。

```json
{"requiredTerms":["A"],"glossary":[{"term":"A","full":"入口携带公共包","matchMode":"code","original":"A：入口启动时加载公共包。","explanation":"只启动入口进程，公共能力随入口加载。","source":"虚构设计说明第1项","scopeNote":"示例归纳的方案代号；不是正式版本。","evidence":["证据一"]}]}
```

原词下划线支持悬停、键盘聚焦和点击；短浮层提供预览，长内容可在释义弹窗完整阅读。弹窗可打开依据清单，关闭回到原词；无脚本点击原词跳到完整释义表。正文首次出现仍需常显中文名称及一句话关系。原文详情在打印展开，不能依赖悬停。完整虚构示例见 [关键代号释义示例](../examples/annotated-options.json)。

## 安全与兼容

值作为纯文本转义，不支持任意 HTML 或脚本。非 URL 的 `sources[].ref` 和证据来源仍是引用文本，不自动执行路径；文档入口显式用 `href`。JSON 嵌入转义 `</script>`；页面不加载外部资源。

旧字段、旧状态和四层键继续支持；新版本加强内容核验。旧数据缺少问题标题、结论或没有证据也没有 `evidenceGap` 时会报错，按错误补齐即可。严格核验不能替代事实审查和真实浏览器验收。
