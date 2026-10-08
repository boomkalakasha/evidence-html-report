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

证据层：`SOURCE_BUILD` → 源码与构建，`RUNTIME_UI` → 运行与交互，`DATA_BUSINESS` → 数据与业务，`RELEASE_CUTOVER` → 发布与切流。支持旧版自定义 `level`，建议用中文；未知英文层名显示“其他证据”，原始值在资料 JSON 保留。

`evidenceLayers[]` 可显式写 `{level,status,reason}`；`status` 支持 `verified`、`not_run`、`not_applicable`、`unknown` 或中文。如果不提供，生成器对有记录的层只显示“已登记证据”，其余显示“待确认：未登记该层证据或不适用说明”。登记证据不等于验收通过。

兼容状态：`implemented`／`complete` → 已实现／已完成，`partial` → 部分实现，`drift` → 存在偏离，`missing` → 未实现，`unverified` → 待验证；中文状态原样保留。未知英文状态显示“待说明”，可通过 `statusLabels` 对象提供中文含义。证据类型同理，通过 `factLabels` 覆盖自定义分类；不要猜含义。

## 正文章节

`sections[]` 共有 `id`、`title`、`summary`（可选）和 `kind`：

- `cards`（默认）／`checklist`：`items[]` 为字符串，或 `{title,body,meta,status,owner,acceptance,dependency,modules,outcome,scope}`。责任与验收字段完整展示。
- `table`：`columns[]` 为非空中文表头数组，`rows[]` 为等长单元格数组。单元格支持字符串和数字；避免长段落。
- `flow`：`steps[]` 为 `{title,body,edge}`。`edge` 为到下一步的调用方式；最后一步不应带出口标签。步骤顺序与原始契约一致。

`sections` 按输入顺序显示在问题台账之前，导航使用标题。无问题时隐藏台账。

其他兼容字段：

- `responsibilities[]`：`{group,mission,modules,acceptance,owner}`，生成“职责与验收”。
- `modules[]`：`{name,category,priority,owner,gap,outcome,acceptance,dependency}`；`required`／`本次必做` 与 `future`／`后续预留` 分组，其余显示“其他模块”。
- `appendices[]`：`{title,body,items}`，默认折叠，打印展开。
- `sources[]`：`{label,ref,note}`，生成来源索引。
- `glossary[]`：`{term,full?,explanation,aliases?}`；缩写含义必须有来源，别把一般英文结构词列成术语。

## 安全与兼容

值作为纯文本转义，不支持任意 HTML 或脚本。`sources[].ref` 和证据来源默认是引用文本，不会自动打开或执行路径。JSON 嵌入转义 `</script>`；不加载外部资源。

旧字段、旧状态和四层键继续支持；新版本加强内容核验。旧数据缺少问题标题、结论或没有证据也没有 `evidenceGap` 时会报错，按错误补齐即可。严格核验不能替代事实审查和真实浏览器验收。
