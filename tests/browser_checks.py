"""可选真实浏览器回归；生成器本身不依赖 Playwright。"""
import argparse
import importlib.util
import json
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright, Error

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("builder", ROOT / "scripts/build_report.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def run(output):
    output.mkdir(parents=True, exist_ok=True)
    brief = output / "brief.html"
    builder.build(ROOT / "examples/technical-brief.json", brief)
    reading = output / "reading.html"
    builder.build(ROOT / "examples/reading-layout.json", reading)
    data = json.loads((ROOT / "examples/audit.json").read_text(encoding="utf-8"))
    data["findings"][1]["summary"] = "页面 API 可显示错误，尚待独立业务核对。"
    source, audit = output / "audit-data.json", output / "audit.html"
    source.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    builder.build(source, audit)
    checks = []
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch()
        except Error:
            # Reuse the installed browser binary, with an isolated headless profile.
            browser = playwright.chromium.launch(channel="chrome")
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(audit.as_uri())
        assert page.locator("#finding-rows tr").count() == 3
        assert not page.locator("body").inner_text().count("SOURCE_BUILD")
        ids = page.locator("[id]").evaluate_all("elements => elements.map(element => element.id)")
        assert len(ids) == len(set(ids)), "页面控件编号冲突"
        checks.append("中文标签与唯一控件编号")
        page.get_by_role("button", name="部分实现", exact=True).click()
        assert page.locator("#finding-rows tr:visible").count() == 1
        page.get_by_role("textbox", name="搜索发现").fill("不存在的词")
        assert page.locator("#empty").is_visible()
        page.get_by_role("button", name="清空筛选").click()
        assert page.locator("#finding-rows tr:visible").count() == 3
        page.get_by_role("textbox", name="搜索发现").fill("模拟交互")
        assert page.locator("#finding-rows tr:visible").count() == 1, "搜索需覆盖引用证据"
        page.get_by_role("button", name="清空筛选").click()
        checks.append("搜索、证据搜索、状态筛选与恢复全部")
        trigger = page.locator(".finding").nth(1)
        trigger.click()
        assert page.locator("#drawer").is_visible()
        page.locator("#resize").focus()
        width = page.locator("#drawer").bounding_box()["width"]
        page.keyboard.press("ArrowLeft")
        assert page.locator("#drawer").bounding_box()["width"] > width
        term = page.locator("#drawer .term").first
        term.hover()
        assert page.locator("#term-popover").is_visible()
        assert page.locator("#term-popover").evaluate("element => element.closest('dialog')?.open")
        # Tooltip is intentionally pointer-transparent; enable hit-testing only
        # for this visibility probe, then restore the production behavior.
        assert page.locator("#term-popover").evaluate("element => { const r=element.getBoundingClientRect(), prior=element.style.pointerEvents; element.style.pointerEvents='auto'; const visible=element.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2)); element.style.pointerEvents=prior; return visible; }")
        page.screenshot(path=str(output / "drawer-tooltip.png"))
        term.focus()
        assert "接口" in page.locator("#term-popover").inner_text()
        page.keyboard.press("Escape")
        assert not page.locator("#drawer").is_visible()
        assert trigger.evaluate("element => document.activeElement === element")
        trigger.click()
        page.get_by_role("button", name="关闭", exact=True).click()
        assert not page.locator("#drawer").is_visible()
        checks.append("抽屉、调整宽度、关闭、焦点返回及抽屉内术语提示")
        page.get_by_role("button", name="部分实现", exact=True).click()
        page.evaluate("window.dispatchEvent(new Event('beforeprint'))")
        page.emulate_media(media="print")
        assert page.locator("#print-findings .print-finding").count() == 3
        assert page.locator("#print-findings").is_visible()
        assert page.locator("#print-findings").inner_text().count("纠正与行动") == 3
        assert all(page.locator("details").evaluate_all("elements => elements.map(element => element.open)"))
        page.evaluate("window.dispatchEvent(new Event('afterprint'))")
        assert not any(page.locator("details").evaluate_all("elements => elements.map(element => element.open)"))
        page.pdf(path=str(output / "audit-print.pdf"), format="A4", print_background=True)
        page.emulate_media(media="screen")
        checks.append("筛选后仍打印全部详情、行动与证据，附录展开与恢复")
        page.get_by_role("button", name="清空筛选").click()
        page.screenshot(path=str(output / "audit-desktop.png"), full_page=True)
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "审计页溢出"
        page.screenshot(path=str(output / "audit-mobile.png"), full_page=True)
        page.goto(brief.as_uri())
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "简报页溢出"
        assert page.locator(".flow-edge").count() == 3
        assert all(page.locator(".flow-edge").evaluate_all("elements => elements.map(element => element.getBoundingClientRect().height > 0)"))
        assert "HTTP 请求" in page.locator(".flow").inner_text()
        page.locator('nav a[href="#contracts"]').click()
        assert page.evaluate("location.hash") == "#contracts"
        page.screenshot(path=str(output / "brief-mobile.png"), full_page=True)
        page.set_viewport_size({"width": 1440, "height": 1000})
        page.goto(brief.as_uri())
        page.screenshot(path=str(output / "brief-desktop.png"), full_page=True)
        checks.append("桌面与390px布局、流程边标识、局部表格滚动与导航")
        page.goto(reading.as_uri())
        initial = page.locator('details[data-fold]').evaluate_all('elements => elements.map(element => element.open)')
        assert initial == [False, True, False]
        doc_link = page.get_by_role('link', name='JSON 数据格式说明')
        assert doc_link.get_attribute('href') == 'https://docs.python.org/3/library/json.html'
        assert doc_link.get_attribute('rel') == 'noopener noreferrer'
        assert not page.locator('#roles .table-wrap').is_visible()
        page.get_by_role('button', name='展开全部详情').click()
        assert all(page.locator('details[data-fold]').evaluate_all('elements => elements.map(element => element.open)'))
        page.get_by_role('button', name='收起全部详情').click()
        assert not any(page.locator('details[data-fold]').evaluate_all('elements => elements.map(element => element.open)'))
        page.locator('nav a[href="#roles"]').click()
        assert not any(page.locator('#roles details').evaluate_all('elements => elements.map(element => element.open)')), '章节导航不应打开补充折叠'
        page.locator('nav a[href="#checks"]').click()
        assert page.locator('#checks > details').get_attribute('open') is not None
        prior = page.locator('details[data-fold]').evaluate_all('elements => elements.map(element => element.open)')
        page.evaluate("window.dispatchEvent(new Event('beforeprint')); window.dispatchEvent(new Event('beforeprint'))")
        assert all(page.locator('details[data-fold]').evaluate_all('elements => elements.map(element => element.open)'))
        page.evaluate("window.dispatchEvent(new Event('afterprint'))")
        assert page.locator('details[data-fold]').evaluate_all('elements => elements.map(element => element.open)') == prior
        page.pdf(path=str(output / 'reading-print.pdf'), format='A4', print_background=True)
        assert page.locator('details[data-fold]').evaluate_all('elements => elements.map(element => element.open)') == prior
        page.goto(reading.as_uri())
        page.screenshot(path=str(output / 'reading-desktop.png'), full_page=True)
        page.set_viewport_size({'width':390, 'height':844})
        page.locator('#roles summary').click()
        assert page.locator('#roles .content-table').is_visible()
        assert page.locator('#roles td').nth(1).evaluate("element => getComputedStyle(element, '::before').content") == '"验收条件"'
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), '阅读页溢出'
        page.screenshot(path=str(output / 'reading-mobile.png'), full_page=True)
        checks.append('正文就近折叠、默认开闭、批量展开收起、导航展开、安全链接、手机表头与打印恢复')
        assert not errors, errors
        no_js = browser.new_context(java_script_enabled=False, viewport={"width": 390, "height": 844})
        static = no_js.new_page()
        static.goto(audit.as_uri())
        assert "待补业务与发布证据" in static.locator("body").inner_text()
        static.get_by_text("回滚演练未执行", exact=True).last.click()
        assert "缺少回滚执行与结果核对记录" in static.locator("body").inner_text()
        assert static.locator("#finding-rows tr").count() == 3
        assert static.evaluate("document.documentElement.scrollWidth <= innerWidth")
        static.goto(reading.as_uri())
        static.locator('#roles summary').click()
        assert '无效输入有可理解的提示' in static.locator('body').inner_text()
        assert not static.get_by_role('button', name='展开全部详情').is_visible()
        static.emulate_media(media='print')
        assert static.locator('#checks .fold-body').is_visible(), '无脚本打印仍需呈现收起的内容'
        checks.append("禁用JavaScript仍可阅读正文、台账与展开详情")
        no_js.close()
        browser.close()
    print(json.dumps({"结果": "通过", "浏览器检查": checks, "页面错误": errors}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output:
        run(args.output.resolve())
    else:
        with tempfile.TemporaryDirectory() as directory:
            run(Path(directory))
