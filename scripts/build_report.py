#!/usr/bin/env python3
"""从 UTF-8 JSON 生成可离线阅读、交互和打印的中文证据报告，仅依赖标准库。"""
from __future__ import annotations

import argparse
import html
import json
import re
import tempfile
from pathlib import Path
from urllib.parse import urlsplit, unquote, parse_qsl

ROOT = Path(__file__).resolve().parents[1]
LAYERS = {"SOURCE_BUILD": "源码与构建", "RUNTIME_UI": "运行与交互", "DATA_BUSINESS": "数据与业务", "RELEASE_CUTOVER": "发布与切流"}
STATUSES = {"implemented": "已实现", "complete": "已完成", "completed": "已完成", "partial": "部分实现", "drift": "存在偏离", "missing": "未实现", "unverified": "待验证", "verified": "已验证", "not_run": "未执行", "not applicable": "不适用", "not_applicable": "不适用", "unknown": "待确认", "blocked": "受阻"}
FACTS = {"current": "当前事实", "fact": "当前事实", "historical": "历史事实", "inference": "推断", "unverified": "待验证", "planned": "未来方案"}
VERDICTS = {"conditional pass": "有条件通过", "pass": "通过", "fail": "未通过", "assessment": "评估结论"}
RESERVED_IDS = {"overview", "evidence-layers", "findings-section", "print-findings", "appendix", "responsibilities", "required-modules", "future-modules", "other-modules", "metrics", "drawer", "report-data", "search", "close", "resize", "drawer-body", "count", "empty", "status-buttons", "finding-rows", "term-popover", "reset", "fold-status", "report-outline", "reading-position", "term-dialog", "term-dialog-body", "term-close", "term-dialog-title"}


def esc(value) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def safe_url(value):
    """Allow explicit document links; never turn commands or credentials into links."""
    if not isinstance(value, str) or not value or re.search(r'[\s\\<>\x00-\x1f]', value):
        return False
    try:
        url = urlsplit(value)
        if url.scheme in ("https", "http"):
            secret_keys = {"access_token", "token", "auth_token", "api_key", "apikey", "password", "pwd", "secret", "client_secret", "authorization", "credential", "access_key", "signature", "sig"}
            params = parse_qsl(url.query) + parse_qsl(url.fragment)
            if any(key.casefold().replace("-", "_") in secret_keys for key, _ in params):
                return False
            url.port  # Reject malformed port values before emitting the link.
            return bool(url.hostname) and url.username is None and url.password is None
        if value.startswith("#"):
            return bool(re.fullmatch(r"#[\w-]+", value))
        if url.scheme == "file":
            if url.netloc or not url.path.startswith("/"):
                return False
        elif url.scheme or url.netloc or value.startswith("//"):
            return False
        return Path(unquote(url.path)).suffix.lower() in {".html", ".htm", ".pdf", ".md", ".txt", ".json", ".png", ".jpg", ".jpeg", ".svg"}
    except ValueError:
        return False


def translated(value, mapping, fallback, overrides=None) -> str:
    raw = str(value or "")
    if overrides and raw in overrides:
        return str(overrides[raw])
    return mapping.get(raw.lower(), raw if re.search(r"[\u3400-\u9fff]", raw) else fallback)


def validate(data: dict) -> None:
    if not isinstance(data, dict):
        raise ValueError("报告必须是 JSON 对象")
    for key in ("title", "generatedAt"):
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise ValueError(f"缺少非空字段：{key}")
    if not isinstance(data.get("verdict"), dict) or not data["verdict"].get("label") or not data["verdict"].get("summary"):
        raise ValueError("verdict 必须包含 label 和 summary")
    for key in ("findings", "evidence"):
        if not isinstance(data.get(key), list):
            raise ValueError(f"{key} 必须是数组")
    for key in ("scope", "metrics", "sections", "responsibilities", "modules", "appendices", "sources", "glossary", "evidenceLayers"):
        if not isinstance(data.get(key, []), list):
            raise ValueError(f"{key} 必须是数组")
    for key in ("statusLabels", "factLabels"):
        if not isinstance(data.get(key, {}), dict):
            raise ValueError(f"{key} 必须是对象")
    if data.get("reportType", "audit") not in ("audit", "brief", "handoff"):
        raise ValueError("reportType 应为 audit、brief 或 handoff")
    def text_fields(item, keys, location, required=()):
        if not isinstance(item, dict):
            raise ValueError(f"{location} 必须是对象")
        for key in keys:
            value = item.get(key)
            if value is not None and not isinstance(value, str):
                raise ValueError(f"{location}.{key} 必须是文本")
            if key in required and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"{location}.{key} 必须是非空文本")

    def string_list(value, location):
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise ValueError(f"{location} 必须是文本数组")

    def rich_fields(item, location):
        text_fields(item, ("text",), location)
        for key in ("paragraphs", "bullets"):
            string_list(item.get(key, []), f"{location}.{key}")
        links = item.get("links", [])
        if not isinstance(links, list):
            raise ValueError(f"{location}.links 必须是数组")
        for link in links:
            text_fields(link, ("label", "href"), f"{location}.links", ("label", "href"))
            if not safe_url(link["href"]):
                raise ValueError(f"{location} 包含无效或不允许的链接")

    def card_items(values, location):
        if not isinstance(values, list):
            raise ValueError(f"{location} 必须是数组")
        for index, item in enumerate(values):
            if isinstance(item, str):
                continue
            text_fields(item, ("title", "name", "group", "body", "summary", "mission", "gap", "status", "owner", "priority", "meta", "scope", "dependency", "acceptance", "outcome", "category"), f"{location}[{index}]")
            rich_fields(item, f"{location}[{index}]")
            if "modules" in item:
                string_list(item["modules"], f"{location}[{index}].modules")

    text_fields(data, ("title", "generatedAt", "subtitle", "audience"), "报告")
    text_fields(data["verdict"], ("label", "summary", "blocker"), "verdict", ("label", "summary"))
    rich_fields(data["verdict"], "verdict")
    string_list(data.get("scope", []), "scope")
    for key in ("statusLabels", "factLabels"):
        if any(not isinstance(value, str) for value in data.get(key, {}).values()):
            raise ValueError(f"{key} 的展示标签必须是文本")
    for key in ("responsibilities", "modules"):
        if any(not isinstance(item, dict) for item in data.get(key, [])):
            raise ValueError(f"{key} 必须是对象数组")
        card_items(data.get(key, []), key)
    for index, metric in enumerate(data.get("metrics", [])):
        text_fields(metric, ("label", "note"), f"metrics[{index}]", ("label",))
        if "value" not in metric or not isinstance(metric["value"], (str, int, float)) or isinstance(metric["value"], bool):
            raise ValueError(f"metrics[{index}].value 必须是文本或数值")
    for index, appendix in enumerate(data.get("appendices", [])):
        text_fields(appendix, ("title", "body"), f"appendices[{index}]", ("title",))
        rich_fields(appendix, f"appendices[{index}]")
        card_items(appendix.get("items", []), f"appendices[{index}].items")
    for index, source in enumerate(data.get("sources", [])):
        text_fields(source, ("label", "ref", "note", "href"), f"sources[{index}]")
        if source.get("href") and (not source.get("label") or not safe_url(source["href"])):
            raise ValueError("来源链接需有效 href 与描述性 label")
    evidence_ids = set()
    for evidence in data["evidence"]:
        text_fields(evidence, ("id", "level", "source", "summary", "date", "scope", "limitation", "factKind", "href", "locator", "accessNote"), "证据", ("id", "level", "source", "summary"))
        if "href" in evidence and not safe_url(evidence["href"]):
            raise ValueError("证据原项链接无效或不允许")
        card_items(evidence.get("items", []), "证据.items")
        if not isinstance(evidence, dict) or any(not evidence.get(key) for key in ("id", "level", "source", "summary")):
            raise ValueError("每条证据需包含 id、level、source、summary")
        if evidence["id"] in evidence_ids:
            raise ValueError("证据编号重复：" + evidence["id"])
        evidence_ids.add(evidence["id"])
    finding_ids = set()
    for finding in data["findings"]:
        text_fields(finding, ("id", "title", "status", "summary", "priority", "owner", "factKind", "evidenceGap"), "问题", ("id", "title", "status", "summary"))
        if not isinstance(finding, dict) or any(not finding.get(key) for key in ("id", "title", "status", "summary")):
            raise ValueError("每个问题需包含 id、title、status、summary")
        if finding["id"] in finding_ids:
            raise ValueError("问题编号重复：" + finding["id"])
        finding_ids.add(finding["id"])
        refs = finding.get("evidence", [])
        if not isinstance(refs, list) or any(not isinstance(ref, str) for ref in refs):
            raise ValueError("问题 evidence 必须是证据编号数组")
        if any(ref not in evidence_ids for ref in refs):
            raise ValueError(f"{finding['id']} 引用了不存在的证据")
        if not refs and not str(finding.get("evidenceGap", "")).strip():
            raise ValueError(f"{finding['id']} 缺少直接证据，需填写 evidenceGap")
        for key in ("assessment", "actions"):
            string_list(finding.get(key, []), f"问题 {key}")
    def block(section, location, depth=0):
        text_fields(section, ("title", "summary", "kind", "outcome", "foldLabel"), location, ("title",))
        rich_fields(section, location)
        for key in ("collapsed", "open"):
            if key in section and not isinstance(section[key], bool):
                raise ValueError(f"{location}.{key} 必须是布尔值")
        kind = section.get("kind", "cards")
        if kind not in ("cards", "checklist", "table", "flow", "comparison"):
            raise ValueError("未知章节类型：" + str(kind))
        if kind == "table":
            columns, rows = section.get("columns"), section.get("rows")
            if not isinstance(columns, list) or not columns or not isinstance(rows, list):
                raise ValueError("表格需包含 columns 和 rows 数组")
            if any(not isinstance(row, list) or len(row) != len(columns) for row in rows):
                raise ValueError("表格每行列数必须与表头一致")
            string_list(columns, f"{location}.columns")
            for row in rows:
                for cell in row:
                    if isinstance(cell, dict):
                        rich_fields(cell, f"{location}.rows")
                    elif not isinstance(cell, (str, int, float)) or isinstance(cell, bool):
                        raise ValueError("表格单元格必须是文本、数值或段落列表对象")
        elif kind == "flow":
            steps = section.get("steps")
            if not isinstance(steps, list) or not steps or any(not isinstance(step, dict) or not step.get("title") for step in steps):
                raise ValueError("流程需包含非空 steps，每步需有 title")
            if steps[-1].get("edge"):
                raise ValueError("流程最后一步不能包含到下一步的 edge")
            for step_index, step in enumerate(steps):
                text_fields(step, ("title", "body", "edge"), f"{location}.steps[{step_index}]", ("title",))
                rich_fields(step, f"{location}.steps[{step_index}]")
        else:
            card_items(section.get("items", []), f"{location}.items")
            if kind == "comparison" and not 2 <= len(section.get("items", [])) <= 4:
                raise ValueError("对比图需包含 2 至 4 组同维度内容")
        folds = section.get("folds", [])
        if not isinstance(folds, list) or (folds and depth >= 2):
            raise ValueError("folds 应为数组，详情嵌套最多两层")
        for index, fold in enumerate(folds):
            block(fold, f"{location}.folds[{index}]", depth + 1)

    section_ids = set(RESERVED_IDS) | {"fold-status"}
    for index, section in enumerate(data.get("sections", [])):
        text_fields(section, ("id", "title"), f"sections[{index}]", ("title",))
        section_id = section.get("id", f"section-{index + 1}")
        if not isinstance(section_id, str) or not re.fullmatch(r"[\w-]+", section_id) or section_id in section_ids:
            raise ValueError("章节 id 需唯一且仅含字母、数字、中文、下划线或短横线")
        section_ids.add(section_id)
        block(section, f"sections[{index}]")
    labels = set()
    for term in data.get("glossary", []):
        text_fields(term, ("term", "full", "explanation", "original", "source", "scopeNote", "matchMode"), "术语", ("term", "explanation"))
        if term.get('original') and not (isinstance(term.get('source'), str) and term['source'].strip()):
            raise ValueError('原文释义必须填写具体 source，不能把解释冒充原文')
        if term.get('matchMode', 'word') not in ('word', 'code'):
            raise ValueError('术语 matchMode 应为 word 或 code')
        if not isinstance(term, dict) or not term.get("term") or not term.get("explanation") or not isinstance(term.get("aliases", []), list):
            raise ValueError("术语需包含 term、explanation，aliases 应为数组")
        if any(isinstance(label,str) and re.fullmatch('[A-Za-z]',label) for label in [term['term'],*term.get('aliases',[])]) and term.get('matchMode') != 'code':
            raise ValueError('单字母代号必须明确 matchMode: code，避免普通字母误注')
        for label in [term["term"], *term.get("aliases", [])]:
            if not isinstance(label, str) or not label.strip() or label.casefold() in labels:
                raise ValueError("术语或别名为空或重复")
            labels.add(label.casefold())
    string_list(data.get('requiredTerms', []), 'requiredTerms')
    required = data.get('requiredTerms', [])
    if len(required) != len(set(required)):
        raise ValueError('requiredTerms 不能重复')
    definitions = {term['term']: term for term in data.get('glossary', [])}
    for label in required:
        term = definitions.get(label)
        if not term or not all(isinstance(term.get(key), str) and term[key].strip() for key in ('full', 'original', 'source')):
            raise ValueError('必需释义缺少定义、中文全称、原文或来源：' + label)
    seen_layers = set()
    for layer in data.get("evidenceLayers", []):
        text_fields(layer, ("level", "status", "reason"), "证据层", ("level", "status", "reason"))
        if not isinstance(layer, dict) or layer.get("level") not in LAYERS or layer["level"] in seen_layers or not layer.get("status") or not layer.get("reason"):
            raise ValueError("证据层需包含唯一标准 level、status 与 reason")
        seen_layers.add(layer["level"])
        string_list(layer.get('evidence', []), '证据层.evidence')
        if any(next(item['level'] for item in data['evidence'] if item['id'] == ref) != layer['level'] for ref in layer.get('evidence', []) if ref in evidence_ids):
            raise ValueError("证据层不能引用其他层的证据")

    def references(value, location):
        if isinstance(value, dict):
            if 'evidence' in value:
                string_list(value['evidence'], location + '.evidence')
                if any(ref not in evidence_ids for ref in value['evidence']):
                    raise ValueError(location + ' 引用了不存在的证据')
            for key, nested in value.items():
                if key != 'evidence': references(nested, location + '.' + key)
        elif isinstance(value, list):
            for index, nested in enumerate(value): references(nested, f'{location}[{index}]')
    for key, value in data.items():
        if key != 'evidence': references(value, key)
    for evidence in data['evidence']:
        references(evidence.get('items', []), '证据.items')


class Renderer:
    def __init__(self, data):
        self.data = data
        self.evidence = {item["id"]: item for item in data["evidence"]}
        self.ids = set(RESERVED_IDS) | {section.get('id', f'section-{i+1}') for i, section in enumerate(data.get('sections', []))}
        self.evidence_anchors = {item['id']: self.unique_id(f'evidence-{i+1}') for i, item in enumerate(data['evidence'])}
        self.term_anchors = [self.unique_id(f'term-detail-{i+1}') for i, _ in enumerate(data.get('glossary', []))]
        self.annotated = set()
        self.outline = []
        self.terms = {}
        for index, term in enumerate(data.get("glossary", [])):
            for label in [term["term"], *term.get("aliases", [])]:
                self.terms[label.casefold()] = (index, term)
        names = sorted(self.terms, key=len, reverse=True)
        self.pattern = re.compile(r"(?<![A-Za-z0-9_])(" + "|".join(re.escape(name) for name in names) + r")(?![A-Za-z0-9_])", re.I) if names else None

    def unique_id(self, preferred):
        candidate, suffix = preferred, 2
        while candidate in self.ids:
            candidate = f'{preferred}-{suffix}'; suffix += 1
        self.ids.add(candidate)
        return candidate

    def number(self, number):
        return f'<span class="outline-number">{esc(number)}</span> '

    def heading(self, title, sid, number):
        self.outline.append((sid, str(number), title))
        return f'<h2>{self.number(number)}{self.text(title)}</h2>'

    def refs(self, refs):
        if not refs: return ''
        return '<div class="evidence-refs"><span>依据：</span>' + '、'.join(self.link({'label':ref,'href':'#'+self.evidence_anchors[ref]}) for ref in refs) + '</div>'

    def plain(self, value, focusable=True):
        source = str(value if value is not None else "")
        if not self.pattern:
            return esc(source)
        parts, last = [], 0
        for match in self.pattern.finditer(source):
            parts.append(esc(source[last:match.start()]))
            index, term = self.terms[match.group().casefold()]
            if term.get('matchMode') == 'code':
                tail = source[match.end():]
                if match.group() not in [term['term'], *term.get('aliases', [])] or re.match(r'(?:[-_]\w|:[/\\])', tail):
                    parts.append(esc(match.group()))
                    last = match.end()
                    continue
            self.annotated.add(term['term'])
            explanation = "：".join(str(term[key]) for key in ("full", "explanation") if term.get(key))
            if term.get('original'):
                explanation += '\n原文：' + term['original'] + '\n出处：' + term['source']
            title = esc(explanation).replace('\n', '&#10;').replace('\r', '&#13;')
            attributes = f'class="term" data-glossary="{index}" title="{title}"'
            if focusable:
                parts.append(f'<a {attributes} href="#{self.term_anchors[index]}" aria-label="{esc(match.group() + '：' + (term.get('full') or term['explanation']) + '；查看释义')}">{esc(match.group())}</a>')
            else:
                parts.append(f'<abbr {attributes}>{esc(match.group())}</abbr>')
            last = match.end()
        return "".join(parts) + esc(source[last:])

    def definition(self, index, term):
        title = esc(term['term'] + (' · ' + term['full'] if term.get('full') else ''))
        body = '<p><strong>通俗解释：</strong>' + esc(term['explanation']).replace('\n', '<br>') + '</p>'
        if term.get('original'):
            body += '<p><strong>原文摘录：</strong></p><blockquote>' + esc(term['original']).replace('\n', '<br>') + '</blockquote>'
        if term.get('source'):
            body += '<p class="muted"><strong>原文出处：</strong>' + esc(term['source']) + '</p>'
        if term.get('scopeNote'):
            body += '<p><strong>适用边界：</strong>' + esc(term['scopeNote']) + '</p>'
        body += self.refs(term.get('evidence', []))
        return f'<article class="definition" id="{self.term_anchors[index]}"><h3>{title}</h3>{body}</article>'

    def text(self, value, focusable=True):
        source = str(value if value is not None else "")
        if not focusable:
            # Button and summary labels must not acquire nested interactive links.
            return self.plain(source, False).replace("\r\n", "\n").replace("\n", "<br>")
        result, last = [], 0
        for match in re.finditer(r'https?://[^\s<>"，。；、！？）》】]+', source):
            url = match.group().rstrip(".,;:!?)]}")
            result.append(self.plain(source[last:match.start()], focusable))
            result.append(self.link({"label": url, "href": url}) if safe_url(url) else esc(url))
            last = match.start() + len(url)
        result.append(self.plain(source[last:], focusable))
        return "".join(result).replace("\r\n", "\n").replace("\n", "<br>")

    def link(self, link):
        target = link["href"]
        external = ' target="_blank" rel="noopener noreferrer"' if urlsplit(target).scheme in ("http", "https") else ""
        # Labels stay plain so glossary focus targets never nest inside links.
        return f'<a href="{esc(target)}"{external}>{esc(link["label"])}</a>'

    def rich(self, value):
        if not isinstance(value, dict):
            return "".join(f'<p>{self.text(part)}</p>' for part in str(value if value is not None else "").split("\n\n") if part)
        result = self.rich(value.get("text", ""))
        result += "".join(self.rich(part) for part in value.get("paragraphs", []))
        if value.get("bullets"):
            result += self.items(value["bullets"])
        if value.get("links"):
            result += '<ul class="links">' + "".join(f'<li>{self.link(link)}</li>' for link in value["links"]) + "</ul>"
        result += self.refs(value.get('evidence', []))
        return result

    def status(self, value):
        return translated(value, STATUSES, "待说明", self.data.get("statusLabels"))

    def badge(self, value):
        status = self.status(value)
        cls = "good" if status in ("已实现", "已完成", "已验证") else "warn" if "部分" in status else "bad" if status in ("未实现", "存在偏离", "受阻") else "pending"
        return f'<span class="badge {cls}">{esc(status)}</span>'

    def fact(self, value):
        return translated(value, FACTS, "待说明", self.data.get("factLabels"))

    def items(self, values):
        return "<ul>" + "".join(f"<li>{self.text(value) if not isinstance(value, dict) else self.rich(value.get('body', value.get('title', ''))) + self.rich(value)}</li>" for value in values) + "</ul>" if values else ""

    def card(self, item):
        if isinstance(item, str):
            return f'<article class="item">{self.rich(item)}</article>'
        title = item.get("title", item.get("name", item.get("group", "")))
        body = item.get("body", item.get("summary", item.get("mission", item.get("gap", ""))))
        content = (f"<h3>{self.text(title)}</h3>" if title else "") + self.rich(body) + self.rich(item)
        if item.get("status"):
            content += self.badge(item["status"])
        for key, label in (("owner", "责任方"), ("priority", "优先级"), ("meta", "说明"), ("scope", "范围"), ("dependency", "依赖"), ("acceptance", "验收"), ("outcome", "目标")):
            if item.get(key):
                content += f'<p class="item-meta"><strong>{label}：</strong>{self.text(item[key])}</p>'
        if item.get("modules"):
            content += self.items(item["modules"])
        return f'<article class="item">{content}</article>'

    def block(self, section, number=''):
        kind = section.get("kind", "cards")
        if kind == "table":
            head = "".join(f"<th scope=\"col\">{self.text(cell)}</th>" for cell in section["columns"])
            rows = "".join("<tr>" + "".join(f'<td data-label="{esc(section["columns"][index])}">{self.rich(cell)}</td>' for index, cell in enumerate(row)) + "</tr>" for row in section["rows"])
            body = f'<div class="table-wrap" tabindex="0" role="region" aria-label="{esc(section["title"])}"><table class="content-table"><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table></div>'
        elif kind == "flow":
            steps = []
            for index, step in enumerate(section["steps"]):
                edge = f'<span class="flow-edge"><span>{self.text(step.get("edge", "下一步"))}</span><b aria-hidden="true">→</b></span>' if index < len(section["steps"]) - 1 else ""
                steps.append(f'<li><div class="flow-node"><strong>{index + 1}. {self.text(step["title"])}</strong>{self.rich(step.get("body", ""))}{self.rich(step)}</div>{edge}</li>')
            body = '<ol class="flow">' + "".join(steps) + "</ol>"
        elif kind == "comparison":
            arrow = '<svg class="merge-arrow" viewBox="0 0 24 24" width="24" height="24" aria-hidden="true"><path d="M12 3v17m-6-6 6 6 6-6" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>'
            body = '<figure class="comparison"><div class="compare-lanes">' + "".join(self.card(item) for item in section["items"]) + "</div>"
            if section.get("outcome"):
                body += f'{arrow}<figcaption class="compare-outcome">{self.text(section["outcome"])}</figcaption>'
            body += "</figure>"
        else:
            body = f'<div class="grid {"checklist" if kind == "checklist" else ""}">' + "".join(self.card(item) for item in section.get("items", [])) + "</div>"
        body += self.rich(section)
        for index, fold in enumerate(section.get("folds", [])):
            subnumber = f'{number}.{index+1}'
            sid = self.unique_id('outline-' + subnumber.replace('.', '-'))
            self.outline.append((sid, subnumber, fold['title']))
            summary = self.rich(fold.get("summary", ""))
            body += self.fold(fold["title"], summary + self.block(fold, subnumber), fold.get("open", False), sid=sid, number=subnumber)
        return body

    def fold(self, title, body, opened=False, primary=False, sid=None, number=''):
        anchor = f' id="{esc(sid)}"' if sid else ''
        label = self.number(number) if number else ''
        return f'<details class="fold"{anchor} data-fold{" data-primary" if primary else ""}{" open" if opened else ""}><summary>{label}{self.text(title, False)}</summary><div class="fold-body">{body}</div></details>'

    def section(self, section, section_id, number):
        heading = self.heading(section['title'], section_id, number)
        body = self.block(section, str(number))
        if section.get("collapsed"):
            body = self.fold(section.get("foldLabel", "查看完整内容"), body, primary=True, number=str(number))
        return f'<section class="section" id="{esc(section_id)}" data-chapter="{number}">{heading}<div class="section-summary">{self.rich(section.get("summary", ""))}</div>{body}</section>'

    def evidence_html(self, evidence):
        layer = LAYERS.get(evidence["level"], translated(evidence["level"], {}, "其他证据"))
        meta = [evidence["source"]] + [f"{label}：{evidence[key]}" for key, label in (("locator", "定位"), ("date", "日期"), ("scope", "范围"), ("limitation", "限制")) if evidence.get(key)]
        if evidence.get("factKind"):
            meta.append("性质：" + self.fact(evidence["factKind"]))
        entry = self.link({'label':'打开原项详情','href':evidence['href']}) if evidence.get('href') else self.text(evidence.get('accessNote') or '未提供可跳转原项；请按来源与定位核对。')
        return f'<article class="evidence"><strong>{self.text(evidence["id"])} · {esc(layer)}</strong><p>{self.text(evidence["summary"])}</p>' + "".join(f'<p class="evidence-meta muted">{self.text(value)}</p>' for value in meta) + f'<p>{entry}</p>' + self.evidence_items(evidence.get('items', [])) + "</article>"

    def evidence_items(self, items):
        if not items: return ''
        return '<ol class="evidence-items">' + ''.join('<li>'+self.card(item)+'</li>' for item in items) + '</ol>'

    def evidence_index(self):
        columns = ['编号与证明内容', '来源与原项入口', '范围与限制']
        rows = []
        for evidence in self.data['evidence']:
            items = self.evidence_items(evidence.get('items', []))
            first = f'<strong>{self.text(evidence["id"])}</strong>{self.rich(evidence["summary"])}{items}'
            entry = self.link({'label':'打开原项详情','href':evidence['href']}) if evidence.get('href') else self.text(evidence.get('accessNote') or '未提供可跳转原项；请按来源与定位核对。')
            second = self.rich(evidence['source']) + self.rich(evidence.get('locator', '')) + f'<p>{entry}</p>'
            if evidence.get('href') and evidence.get('accessNote'): second += self.rich(evidence['accessNote'])
            meta = [LAYERS.get(evidence['level'], '其他证据')]
            meta += [f'{label}：{evidence[key]}' for key, label in (('date','日期'),('scope','范围'),('limitation','限制')) if evidence.get(key)]
            if evidence.get('factKind'): meta.append('性质：' + self.fact(evidence['factKind']))
            cells = ''.join(f'<td data-label="{esc(label)}">{value}</td>' for label,value in zip(columns,(first,second,self.items(meta))))
            rows.append(f'<tr id="{self.evidence_anchors[evidence["id"]]}" tabindex="-1">{cells}</tr>')
        head = ''.join(f'<th scope="col">{label}</th>' for label in columns)
        return '<div class="table-wrap" role="region" aria-label="证据清单" tabindex="0"><table class="content-table evidence-table"><thead><tr>'+head+'</tr></thead><tbody>'+''.join(rows)+'</tbody></table></div>'

    def detail(self, finding):
        body = f'<article class="detail"><h2>{self.text(finding["id"] + " · " + finding["title"])}</h2><p>{self.badge(finding["status"])} {self.text(finding.get("owner", "待指定责任方"))} · {self.text(finding.get("priority", "待定优先级"))}</p><p>{self.text(finding["summary"])}</p>'
        if finding.get("factKind"):
            body += f'<p>判断性质：{esc(self.fact(finding["factKind"]))}</p>'
        for key, label in (("assessment", "判断依据"), ("actions", "纠正与行动")):
            if finding.get(key):
                body += f"<h3>{label}</h3>" + self.items(finding[key])
        body += "<h3>直接证据与边界</h3>"
        body += "".join(self.evidence_html(self.evidence[ref]) for ref in finding.get("evidence", []))
        if finding.get("evidenceGap"):
            body += f'<p class="muted">证据缺口：{self.text(finding["evidenceGap"])}</p>'
        return body + "</article>"

    def render(self):
        data, verdict = self.data, self.data["verdict"]
        sections = [(section, section.get("id", f"section-{index + 1}")) for index, section in enumerate(data.get("sections", []))]
        if data.get("responsibilities"):
            sections.append(({"title": "职责与验收", "items": data["responsibilities"]}, "responsibilities"))
        groups = {"required": [], "future": [], "other": []}
        for module in data.get("modules", []):
            category = module.get("category")
            groups["required" if category in ("required", "本次必做") else "future" if category in ("future", "后续预留") else "other"].append(module)
        for key, title in (("required", "本次必做"), ("future", "后续预留"), ("other", "其他模块")):
            if groups[key]:
                sections.append(({"title": title, "items": groups[key]}, f"{key}-modules"))
        nav = [("overview", "核心结论"), *[(sid, section["title"]) for section, sid in sections]]
        if data["findings"]:
            nav.append(("findings-section", "发现与行动"))
        nav.extend([("evidence-layers", "证据范围"), ("appendix", "背景与证据附录")])
        chapters = {sid: index+1 for index, (sid, _) in enumerate(nav)}
        report_type = {"audit": "审计评估", "brief": "技术方案简报", "handoff": "场景交接"}[data.get("reportType", "audit")]
        meta = ["生成时间：" + data["generatedAt"]] + (["读者：" + data["audience"]] if data.get("audience") else []) + data.get("scope", [])
        content = f'<header class="hero"><h1>{self.text(data["title"])}</h1>{self.rich(data.get("subtitle", ""))}<div class="meta"><span>{report_type}</span>' + "".join(f"<span>{self.text(value)}</span>" for value in meta) + "</div></header>"
        content += '<div class="report-navigation no-print"><div class="reading-position js-only" id="reading-position" role="status">阅读位置 1 / '+str(len(nav))+' · 核心结论</div><nav class="nav" aria-label="报告章节">' + "".join(f'<a href="#{esc(sid)}">{self.number(chapters[sid])}{esc(title)}</a>' for sid, title in nav) + "</nav></div>"
        content += '<!-- report-outline -->'
        verdict_label = VERDICTS.get(verdict["label"].lower(), verdict["label"])
        content += f'<section class="verdict" id="overview" data-chapter="1"><article class="card">{self.heading("核心结论","overview",1)}<div class="verdict-label">{self.text(verdict_label)}</div>{self.rich(verdict["summary"])}{self.rich(verdict)}</article><article class="card blocker"><h3>当前最大阻断</h3>{self.rich(verdict.get("blocker") or "未登记阻断；请结合证据范围判断。")}</article></section>'
        if data.get("metrics"):
            content += '<section class="metrics" id="metrics" aria-label="实测统计">' + "".join(f'<article class="card metric"><small>{self.text(metric["label"])}</small><strong>{self.text(metric["value"])}</strong><span class="muted">{self.text(metric.get("note", ""))}</span></article>' for metric in data["metrics"]) + "</section>"
        content += "".join(self.section(section, sid, chapters[sid]) for section, sid in sections)
        templates, print_content = [], []
        if data["findings"]:
            statuses = list(dict.fromkeys(self.status(finding["status"]) for finding in data["findings"]))
            buttons = "".join(f'<button data-status-filter="{esc(status)}" aria-pressed="false">{esc(status)}</button>' for status in statuses)
            rows = []
            for finding in data["findings"]:
                search = json.dumps([finding, *[self.evidence[ref] for ref in finding.get("evidence", [])]], ensure_ascii=False)
                rows.append(f'<tr data-status="{esc(self.status(finding["status"]))}" data-search="{esc(search)}"><td><button class="finding" data-id="{esc(finding["id"])}">{self.text(finding["id"] + " · " + finding["title"], False)}</button></td><td>{self.badge(finding["status"])}</td><td>{self.text(finding["summary"])}</td><td>{self.text(finding.get("owner", "待指定责任方"))}<br><small>{self.text(finding.get("priority", "待定优先级"))}</small></td></tr>')
                detail = self.detail(finding)
                templates.append(f'<template data-finding="{esc(finding["id"])}">{detail}</template>')
                print_content.append(f'<div class="print-finding">{detail}</div>')
            content += f'<section class="section" id="findings-section" data-chapter="{chapters["findings-section"]}"><div class="section-head">{self.heading("发现与行动", "findings-section", chapters["findings-section"])}<small id="count">显示 {len(rows)} / {len(rows)} 项</small></div><div class="tools no-print"><input id="search" aria-label="搜索发现" placeholder="搜索标题、结论、责任方或证据"><button data-status-filter="" class="active" aria-pressed="true">全部</button><span id="status-buttons">{buttons}</span><button id="reset">清空筛选</button></div><div class="table-wrap" role="region" aria-label="问题台账" tabindex="0"><table><thead><tr><th scope="col">问题</th><th scope="col">状态</th><th scope="col">判断</th><th scope="col">责任与优先级</th></tr></thead><tbody id="finding-rows">{"".join(rows)}</tbody></table><p class="empty muted" id="empty" hidden>没有匹配项，请清空筛选后重试。</p></div></section>'
            content += '<section class="section print-only" id="print-findings"><h2>问题详情、行动与证据</h2>' + "".join(print_content) + "</section>"
            content += '<noscript><section class="section no-print"><h2>问题详情、行动与证据</h2>' + "".join(f'<details class="fold"><summary>{esc(finding["title"])}</summary><div class="fold-body">{self.detail(finding)}</div></details>' for finding in data["findings"]) + "</section></noscript>"
        explicit_layers = {layer["level"]: layer for layer in data.get("evidenceLayers", [])}
        layers = []
        for key, title in LAYERS.items():
            layer = explicit_layers.get(key)
            count = sum(evidence["level"] == key for evidence in data["evidence"])
            status = self.status(layer["status"]) if layer else "已登记证据" if count else "待确认"
            reason = layer["reason"] if layer else f"登记 {count} 条证据；不等于该层验收通过。" if count else "未登记该层证据或不适用说明。"
            refs = layer.get('evidence') if layer and 'evidence' in layer else [item['id'] for item in data['evidence'] if item['level'] == key]
            reference = self.refs(refs) if refs else '<p class="muted">未登记逐项证据；以上仅为范围说明。</p>'
            layers.append(f'<article class="layer"><strong>{title}</strong><span class="badge">{esc(status)}</span><p>{self.text(reason)}</p>{reference}</article>')
        number = chapters['evidence-layers']
        content += f'<section class="section" id="evidence-layers" data-chapter="{number}">{self.heading("证据范围","evidence-layers",number)}<div class="layer-grid">' + "".join(layers) + "</div>"
        if data['evidence']:
            subnumber = str(number) + '.1'
            sid = self.unique_id('outline-' + subnumber.replace('.', '-'))
            self.outline.append((sid,subnumber,'证据清单与原项入口'))
            content += self.fold('证据清单与原项入口', '<p class="muted">逐项列出证明内容、原始入口与限制；点击结论旁的依据编号可直接定位本表。</p>' + self.evidence_index(), sid=sid, number=subnumber)
        content += '</section>'
        missing = set(data.get('requiredTerms', [])) - self.annotated
        if missing:
            raise ValueError('必需释义未呈现在正文、表格或详情中：' + '、'.join(sorted(missing)))
        appendices = list(data.get("appendices", []))
        glossary_appendix = None
        if data.get("glossary"):
            glossary_appendix = {"title": "代号与术语原文释义", "body": "下划线原词可悬停或聚焦预览，点击查看完整原文、解释与出处。无脚本时跳到本表；打印保留全部释义。"}
            appendices.append(glossary_appendix)
        if data.get("sources"):
            appendices.append({"title": "来源索引", "items": [{"body": " · ".join(source[key] for key in ("ref", "note") if source.get(key)), "links": [{"label": source["label"], "href": source["href"]}]} if source.get("href") else " · ".join(source[key] for key in ("label", "ref", "note") if source.get(key)) for source in data["sources"]]})
        appendix_number = chapters['appendix']
        appendix_heading = self.heading('背景与证据附录','appendix',appendix_number)
        folds = []
        for index, appendix in enumerate(appendices):
            subnumber = f'{appendix_number}.{index+1}'
            sid = self.unique_id('outline-' + subnumber.replace('.', '-'))
            self.outline.append((sid,subnumber,appendix['title']))
            body = self.rich(appendix.get("body", "")) + self.rich(appendix) + self.items(appendix.get("items", []))
            if appendix is glossary_appendix:
                body += ''.join(self.definition(i, term) for i, term in enumerate(data['glossary']))
            folds.append(self.fold(appendix["title"], body, sid=sid, number=subnumber))
        content += f'<section class="section" id="appendix" data-chapter="{appendix_number}">{appendix_heading}' + ("".join(folds) or '<p class="muted">未提供附录材料。</p>') + "</section>"
        entries = ''.join(f'<li class="outline-depth-{number.count(".")}"><a href="#{esc(sid)}">{self.number(number)}{esc(title)}</a></li>' for sid,number,title in self.outline)
        outline = '<details class="report-outline no-print" id="report-outline"><summary>查看完整目录 · 共'+str(len(nav))+'章</summary><nav aria-label="完整目录"><ul>'+entries+'</ul></nav></details>'
        content = content.replace('<!-- report-outline -->', outline)
        content += f'<footer>{self.text(data["title"])} · {self.text(data["generatedAt"])} · 判断以顶部范围及证据限制为准。</footer>'
        if 'data-fold' in content:
            controls = '<div class="reading-tools js-only no-print"><span id="fold-status" aria-live="polite"></span><button data-fold-action="expand">展开全部详情</button><button data-fold-action="collapse">收起全部详情</button></div>'
            content = content.replace('</details>', '</details>' + controls, 1)
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
        css = (ROOT / "assets/report.css").read_text(encoding="utf-8")
        js = (ROOT / "assets/report.js").read_text(encoding="utf-8")
        return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="icon" href="data:,"><title>{esc(data["title"])}</title><style>{css}</style></head><body>
<main class="shell">{content}</main>{"".join(templates)}
<dialog id="drawer" aria-label="详情与证据"><div class="drawer"><div class="drawer-head"><strong>详情与证据</strong><button class="close" id="close">关闭</button></div><div class="resize" id="resize" role="separator" tabindex="0" aria-label="调整详情宽度" aria-orientation="vertical"></div><div class="drawer-body" id="drawer-body"></div></div></dialog>
<dialog id="term-dialog" class="term-dialog" aria-labelledby="term-dialog-title"><div class="drawer-head"><strong id="term-dialog-title">原文与释义</strong><button id="term-close">关闭释义</button></div><div class="drawer-body" id="term-dialog-body"></div></dialog>
<div class="term-popover" id="term-popover" role="tooltip" hidden></div><script type="application/json" id="report-data">{payload}</script><script>{js}</script></body></html>'''


def build(source: Path, target: Path) -> None:
    data = json.loads(source.read_text(encoding="utf-8-sig"))
    validate(data)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(Renderer(data).render(), encoding="utf-8")


def self_test() -> None:
    data = {"title": "生成器自检", "generatedAt": "示例", "verdict": {"label": "待验证", "summary": "仅检验报告生成。"}, "findings": [], "evidence": []}
    with tempfile.TemporaryDirectory() as directory:
        source, target = Path(directory) / "in.json", Path(directory) / "out.html"
        source.write_text(json.dumps(data), encoding="utf-8")
        build(source, target)
        assert "生成器自检" in target.read_text(encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="生成离线中文 HTML 报告")
    parser.add_argument("source", nargs="?", type=Path, help="输入 JSON")
    parser.add_argument("target", nargs="?", type=Path, help="输出 HTML")
    parser.add_argument("--self-test", action="store_true", help="运行生成器自检")
    args = parser.parse_args()
    try:
        if args.self_test:
            self_test()
            print("生成器自检：通过")
        elif args.source and args.target:
            build(args.source, args.target)
            print(args.target.resolve())
        else:
            parser.error("请提供输入 JSON 与输出 HTML")
    except (ValueError, OSError) as error:
        parser.exit(1, f"生成失败：{error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
