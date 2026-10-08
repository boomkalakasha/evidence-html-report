import copy
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = Path(os.environ.get("REPORT_BUILDER", ROOT / "scripts/build_report.py"))
spec = importlib.util.spec_from_file_location("report_builder", SCRIPT)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.skip = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "template"):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "template"):
            self.skip -= 1

    def handle_data(self, text):
        if not self.skip:
            self.parts.append(text)


def sample():
    return {
        "title": "接口交接核验", "generatedAt": "2026-10-08", "reportType": "handoff",
        "verdict": {"label": "待联调", "summary": "实现已登记，尚待业务验收。"},
        "findings": [{"id": "问题一", "title": "结果尚未持久化验证", "status": "partial", "summary": "运行日志不能证明数据入库。", "assessment": ["保留独立业务验收"], "actions": ["核对持久化结果"], "evidence": ["证据一"]}],
        "evidence": [{"id": "证据一", "level": "SOURCE_BUILD", "source": "git:example:src/Result.java:10", "summary": "源码存在结果处理入口。", "date": "2026-10-08", "limitation": "尚未进行真实联调"}],
        "responsibilities": [{"group": "集成组", "mission": "核对回调结果", "acceptance": "成功与异常均可追溯"}],
        "sections": [{"id": "chain", "title": "调用链", "kind": "flow", "steps": [{"title": "/api/run", "edge": "HTTP 请求"}, {"title": "ResultAdapter", "body": "返回处理结果"}]}, {"id": "changes", "title": "改动与确认", "kind": "table", "columns": ["改动", "结果"], "rows": [["接口入口", "可接收请求"]]}],
    }


def render(data):
    with tempfile.TemporaryDirectory() as tmp:
        source, target = Path(tmp) / "in.json", Path(tmp) / "out.html"
        source.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        builder.build(source, target)
        return target.read_text(encoding="utf-8")


class BuilderTests(unittest.TestCase):
    def annotated_sample(self):
        data = sample()
        data['sections'][1]['rows'] = [['A：入口携带能力包', '只启动入口进程']]
        data['glossary'] = [{'term':'A','full':'入口携带能力包','explanation':'启动入口时一起装配公共能力。','original':'A：入口启动，能力包随入口加载。','source':'虚构设计记录第2项','matchMode':'code','evidence':['证据一']}]
        data['requiredTerms'] = ['A']
        return data

    def test_required_definition_preserves_original_source_and_evidence(self):
        output = render(self.annotated_sample())
        self.assertIn('href="#term-detail-1"', output)
        self.assertIn('原文摘录：', output)
        self.assertIn('A：入口启动，能力包随入口加载。', output)
        self.assertIn('虚构设计记录第2项', output)
        self.assertIn('id="term-dialog"', output)
        self.assertIn('href="#evidence-1"', output)

    def test_required_definition_missing_or_unrendered_is_rejected(self):
        for change in ('definition', 'occurrence'):
            data = self.annotated_sample()
            if change == 'definition': data['glossary'] = []
            else: data['sections'][1]['rows'] = [['入口', '进程']]
            with self.subTest(change=change), self.assertRaises(ValueError): render(data)

    def test_required_definition_needs_raw_original_and_source(self):
        for key in ('original','source','full'):
            data = self.annotated_sample()
            del data['glossary'][0][key]
            with self.subTest(key=key), self.assertRaises(ValueError): render(data)

    def test_single_letter_codes_do_not_annotate_paths_decision_or_evidence_ids(self):
        data = self.annotated_sample()
        data['requiredTerms'] = []
        data['glossary'] = [dict(data['glossary'][0],term=code) for code in 'CDE']
        renderer = builder.Renderer(data)
        for text in ['C:/folder/report.md', 'C:\\folder\\report.md', 'D-001', 'E01/E02', 'a code']:
            self.assertNotIn('class="term"', renderer.plain(text))
        self.assertEqual(renderer.plain('C/D/E').count('class="term"'),3)

    def test_null_required_fields_cannot_bypass_definition_gate(self):
        for key in ('full','original','source'):
            data=self.annotated_sample()
            data['glossary'][0][key]=None
            with self.subTest(key=key), self.assertRaises(ValueError): render(data)
        data=self.annotated_sample()
        data['requiredTerms']=[]
        data['glossary'][0]['source']=None
        with self.assertRaises(ValueError): render(data)

    def test_single_letter_requires_explicit_code_mode(self):
        data = self.annotated_sample()
        del data['glossary'][0]['matchMode']
        with self.assertRaises(ValueError): render(data)

    def test_single_letter_alias_uses_same_code_mode_gate(self):
        data=sample()
        data['glossary']=[{'term':'方案丙','aliases':['C'],'explanation':'入口关系'}]
        with self.assertRaises(ValueError): render(data)
        data['glossary'][0]['matchMode']='code'
        builder.validate(data)
        renderer=builder.Renderer(data)
        self.assertNotIn('class="term"',renderer.plain('C:/files/report.md'))
        self.assertNotIn('class="term"',renderer.plain('c：普通字母'))
        self.assertIn('class="term"',renderer.plain('C：方案原词'))

    def test_original_text_is_safe_and_annotation_ids_avoid_collision(self):
        data = self.annotated_sample()
        data['glossary'][0]['original'] = '<script>alert("raw")</script>'
        data['sections'][0]['id'] = 'term-detail-1'
        output = render(data)
        self.assertIn('id="term-detail-1-2"', output)
        self.assertIn('&lt;script&gt;alert', output)
        self.assertNotIn('<script>alert("raw")', output)

    def test_numbered_outline_matches_chapters_and_nested_details(self):
        data = sample()
        data['sections'][0]['folds'] = [{'title': '字段明细', 'items': ['编号'], 'folds': [{'title':'异常明细','items':['超时']}]}]
        output = render(data)
        self.assertIn('data-chapter="2"', output)
        self.assertIn('href="#outline-2-1"', output)
        self.assertIn('href="#outline-2-1-1"', output)
        self.assertIn('id="outline-2-1-1"', output)
        self.assertIn('2.1.1', output)
        self.assertIn('id="reading-position"', output)

    def test_generated_anchors_do_not_collide_with_user_ids(self):
        data = sample()
        data['sections'][1]['id'] = 'outline-2-1'
        data['sections'][0]['folds'] = [{'title':'明细','items':['内容']}]
        class IDs(HTMLParser):
            def __init__(self):
                super().__init__(); self.ids=[]; self.refs=[]
            def handle_starttag(self, tag, attrs):
                values = dict(attrs)
                if 'id' in values: self.ids.append(values['id'])
                if values.get('href','').startswith('#'): self.refs.append(values['href'][1:])
        parser = IDs(); parser.feed(render(data))
        self.assertEqual(len(parser.ids), len(set(parser.ids)))
        self.assertTrue(all(ref in parser.ids for ref in parser.refs))

    def test_original_evidence_links_and_fallback_inventory(self):
        data = sample()
        data['evidence'][0].update(href='https://example.com/commit/123#L10', locator='Result.java 第10行', items=[{'title':'入口存在','body':'仅证明源码入口'}])
        data['evidence'].append({'id':'证据二','level':'SOURCE_BUILD','source':'旧验证记录','summary':'记录了三项检查','locator':'2026-10-07 / 检查1至3','accessNote':'未提供可访问原项，需按日期核对'})
        data['verdict']['evidence'] = ['证据一','证据二']
        output = render(data)
        self.assertIn('href="https://example.com/commit/123#L10"', output)
        self.assertIn('href="#evidence-1"', output)
        self.assertIn('id="evidence-2"', output)
        self.assertIn('未提供可访问原项，需按日期核对', output)
        self.assertIn('2026-10-07 / 检查1至3', output)
        self.assertIn('证据清单与原项入口', output)
        self.assertIn('入口存在', output)

    def test_context_evidence_references_reject_missing_ids(self):
        for location in ('verdict','section','card','layer','fold'):
            data = sample()
            targets={'verdict':data['verdict'],'section':data['sections'][0],'card':data['responsibilities'][0]}
            data['evidenceLayers']=[{'level':'SOURCE_BUILD','status':'verified','reason':'范围说明'}]
            targets['layer']=data['evidenceLayers'][0]
            data['sections'][0]['folds']=[{'title':'明细','items':[]}]
            targets['fold']=data['sections'][0]['folds'][0]
            targets[location]['evidence']=['不存在']
            with self.subTest(location=location), self.assertRaisesRegex(ValueError,'证据'):
                builder.validate(data)

    def test_evidence_links_and_item_shapes_are_validated(self):
        for field,value in [('href','javascript:alert(1)'),('locator',[]),('items',[None])]:
            data=sample(); data['evidence'][0][field]=value
            with self.subTest(field=field), self.assertRaises(ValueError): builder.validate(data)
        data=sample()
        data['evidenceLayers']=[{'level':'RUNTIME_UI','status':'verified','reason':'不能借用源码证明','evidence':['证据一']}]
        with self.assertRaisesRegex(ValueError,'证据'): builder.validate(data)

    def test_evidence_inventory_preserves_each_result_and_limit(self):
        data=sample()
        data['evidence'][0]['items']=[{'title':'成功输入','body':'返回编号','status':'verified'},{'title':'数据核对','body':'尚无执行记录','status':'not_run'}]
        output=render(data)
        table=output.split('class="content-table evidence-table"',1)[1].split('</table>',1)[0]
        for expected in ('成功输入','已验证','数据核对','未执行','尚无执行记录','尚未进行真实联调'): self.assertIn(expected,table)

    def test_content_is_readable_without_javascript_and_structure_is_chinese(self):
        html = render(sample())
        text = VisibleText()
        text.feed(html)
        visible = " ".join(text.parts)
        for expected in ("核心结论", "调用链", "职责与验收", "成功与异常均可追溯", "部分实现", "源码与构建", "HTTP 请求", "/api/run", "ResultAdapter"):
            self.assertIn(expected, visible)
        for unwanted in ("Executive verdict", "Issue ledger", "Unassigned", "SOURCE_BUILD", "partial"):
            self.assertNotIn(unwanted, visible)

    def test_brief_does_not_manufacture_findings_or_metrics(self):
        data = sample()
        data.update(reportType="brief", findings=[], evidence=[])
        html = render(data)
        self.assertNotIn('id="findings-section"', html)
        self.assertNotIn('id="metrics"', html)

    def test_print_contains_every_finding_action_and_evidence(self):
        html = render(sample())
        self.assertIn('id="print-findings"', html)
        printed = html.split('id="print-findings"', 1)[1].split("</section>", 1)[0]
        for expected in ("核对持久化结果", "尚未进行真实联调", "源码与构建"):
            self.assertIn(expected, printed)

    def test_rejects_dangling_or_duplicate_evidence(self):
        data = sample()
        data["findings"][0]["evidence"] = ["不存在"]
        with self.assertRaisesRegex(ValueError, "证据"):
            builder.validate(data)
        data = sample()
        data["evidence"].append(copy.deepcopy(data["evidence"][0]))
        with self.assertRaisesRegex(ValueError, "证据"):
            builder.validate(data)

    def test_evidence_gap_must_be_explicit(self):
        data = sample()
        data["findings"][0]["evidence"] = []
        with self.assertRaises(ValueError):
            builder.validate(data)
        data["findings"][0]["evidenceGap"] = "缺少数据核对记录"
        self.assertIn("缺少数据核对记录", render(data))

    def test_rejects_ragged_table_and_duplicate_section_ids(self):
        data = sample()
        data["sections"][1]["rows"][0] = ["少一格"]
        with self.assertRaises(ValueError):
            builder.validate(data)
        data = sample()
        data["sections"][1]["id"] = "chain"
        with self.assertRaises(ValueError):
            builder.validate(data)

    def test_html_and_script_values_are_inert(self):
        data = sample()
        data["title"] = '</script><img src=x onerror="alert(1)">'
        html = render(data)
        self.assertNotIn('<img src=x', html)
        self.assertIn("&lt;/script&gt;", html)
        self.assertNotIn('</script><img', html)

    def test_old_module_and_responsibility_fields_are_not_dropped(self):
        data = sample()
        data["modules"] = [{"name": "回调登记", "category": "required", "priority": "P1", "owner": "平台组", "gap": "缺少验收", "outcome": "处理可追溯", "acceptance": "结果可核对"}, {"name": "动态注册", "category": "future", "owner": "架构组"}]
        html = render(data)
        for expected in ("本次必做", "后续预留", "平台组", "P1", "结果可核对"):
            self.assertIn(expected, html)

    def test_reserved_control_ids_are_rejected(self):
        for reserved in ("search", "close", "drawer-body", "term-popover", "count"):
            data = sample()
            data["sections"][0]["id"] = reserved
            with self.subTest(reserved=reserved), self.assertRaises(ValueError):
                builder.validate(data)

    def test_invalid_nested_content_gives_validation_errors(self):
        mutations = [
            ("evidence", [{"id": ["非法"], "source": "示例", "level": "SOURCE_BUILD", "summary": "说明"}]),
            ("sections", [{"title": "章节", "items": [1]}]),
            ("responsibilities", ["不是对象"]), ("metrics", [None]),
            ("appendices", [{"title": "附录", "items": "不是数组"}]),
            ("modules", [{"name": "模块", "owner": {"非法": "内容"}}]),
        ]
        for key, value in mutations:
            data = sample()
            data[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                builder.validate(data)

    def test_legacy_verdict_labels_are_chinese(self):
        data = sample()
        data["verdict"]["label"] = "Conditional pass"
        visible = VisibleText()
        visible.feed(render(data))
        self.assertIn("有条件通过", " ".join(visible.parts))

    def test_contextual_folds_preserve_summary_and_static_content(self):
        data = sample()
        data["sections"][1].update(collapsed=True, foldLabel="查看逐项对照", summary="默认先读摘要")
        data["sections"][0]["folds"] = [{"title": "为何按此顺序", "open": True, "items": [{"body": "先登记，再执行", "bullets": ["保留任务编号", "核对结果"]}]}]
        output = render(data)
        self.assertIn('data-fold', output)
        self.assertIn("默认先读摘要", output)
        self.assertIn("查看逐项对照", output)
        self.assertIn('<li>保留任务编号</li>', output)
        self.assertIn(' open', output)

    def test_paragraphs_and_linked_cells_are_readable_and_safe(self):
        data = sample()
        data["sections"][1]["rows"][0][1] = {"paragraphs": ["第一段", "第二段"], "bullets": ["可逐条核对"], "links": [{"label": "接口文档", "href": "https://example.com/docs?a=1&b=2"}, {"label": "本地报告", "href": "../report.html"}]}
        data["sections"][0]["steps"][0]["body"] = "请求到达\n记录编号\n\n完整说明 https://example.com/guide。"
        output = render(data)
        self.assertIn("<p>第一段</p><p>第二段</p>", output)
        self.assertIn('href="https://example.com/docs?a=1&amp;b=2"', output)
        self.assertIn('href="../report.html"', output)
        self.assertIn('href="https://example.com/guide"', output)
        self.assertIn("请求到达<br>记录编号", output)
        for target in ("javascript:alert(1)", "data:text/html,x", "https://user:pass@example.com", "//other.example.com/x", "../run.exe"):
            data["sections"][1]["rows"][0][1]["links"][0]["href"] = target
            with self.subTest(target=target), self.assertRaises(ValueError):
                builder.validate(data)

    def test_comparison_diagram_is_structured_and_not_an_invented_score(self):
        data = sample()
        data["sections"] = [{"id": "inputs", "title": "方案比较", "kind": "comparison", "items": [{"title": "方案甲", "bullets": ["调用具体"]}, {"title": "方案乙", "bullets": ["证据完整"]}], "outcome": "结合两者"}]
        output = render(data)
        for text in ("方案甲", "调用具体", "方案乙", "证据完整", "结合两者"):
            self.assertIn(text, output)
        self.assertIn('<figure', output)
        self.assertNotIn('百分比', output)

    def test_invalid_fold_and_link_shapes_fail_before_rendering(self):
        for field, value in (("collapsed", "true"), ("folds", [None]), ("folds", [{"title": "细节", "open": "false"}]), ("links", [{"href": "https://example.com"}])):
            data = sample()
            data["sections"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                builder.validate(data)

    def test_null_section_id_is_a_validation_error(self):
        data = sample()
        data['sections'][0]['id'] = None
        with self.assertRaises(ValueError):
            builder.validate(data)

    def test_control_labels_never_gain_nested_links(self):
        data = sample()
        data['findings'][0]['title'] = '查看 https://example.com'
        data['sections'][0]['folds'] = [{'title':'网址 https://example.com', 'items':['正文']}]
        output = render(data)
        button = output.split('class="finding"',1)[1].split('</button>',1)[0]
        summary = next(part.rsplit('<summary>',1)[1] for part in output.split('</summary>') if '<summary>' in part and '网址 https://example.com' in part)
        self.assertNotIn('<a ',button)
        self.assertNotIn('<a ',summary)

    def test_query_credentials_are_never_active_links(self):
        for suffix in ('?access_token=fictional-secret', '?password=fictional-secret', '#api_key=fictional-secret'):
            url = 'https://example.com/docs' + suffix
            data = sample()
            data['sections'][0]['steps'][0]['body'] = url
            output = render(data)
            self.assertNotIn('href="' + url + '"', output)
            data['sections'][0]['links'] = [{'label':'材料','href':url}]
            with self.assertRaises(ValueError):
                builder.validate(data)


if __name__ == "__main__":
    unittest.main()
