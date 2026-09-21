#!/usr/bin/env python3
"""Render a deterministic HTML Source Scout report from a JSON report file."""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from typing import Any


def esc(value: Any) -> str:
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def first_value(data: dict[str, Any], keys: list[str], default: str = "") -> str:
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return str(value)
    return default


def list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def file_or_url(value: str) -> str:
    if not value:
        return ""
    if value.startswith(("http://", "https://", "data:")):
        return value
    path = Path(value)
    if path.exists():
        return path.resolve().as_uri()
    return value


def default_template_path() -> Path:
    return Path(__file__).resolve().parent.parent / "templates" / "report-template.html"


def load_template(template_path: str | Path | None = None) -> str:
    path = Path(template_path) if template_path else default_template_path()
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def render_template(template_text: str, context: dict[str, str]) -> str:
    rendered = template_text
    for key, value in context.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", value)
        rendered = rendered.replace(f"{{{{ {key} }}}}", value)
    return rendered


def image_html(item: dict[str, Any], alt: str) -> str:
    src = first_value(item, ["image_path", "local_image", "image_url", "image"])
    source = first_value(item, ["image_note", "image_source", "image_provenance"])
    if src:
        note_html = f'<span class="image-note">{esc(source)}</span>' if source else ""
        return (
            f'<img class="product-image" src="{esc(file_or_url(src))}" '
            f'alt="{esc(alt)}" loading="lazy">'
            f'{note_html}'
        )
    return '<div class="image-placeholder">Image required before final delivery</div>'


def link_html(url: str, label: str = "Open") -> str:
    if not url:
        return '<span class="muted link-status">趋势级线索：按搜索词验证</span>'
    return f'<a href="{esc(url)}" target="_blank" rel="noopener noreferrer">{esc(label)}</a>'


def action_link(url: str, label: str, kind: str = "") -> str:
    if not url:
        return ""
    class_name = f"link-chip {kind}".strip()
    return f'<a class="{esc(class_name)}" href="{esc(url)}" target="_blank" rel="noopener noreferrer">{esc(label)}</a>'


def pill(text: str) -> str:
    return f'<span class="pill">{esc(text)}</span>' if text else ""


def card(item: dict[str, Any], badge: str = "") -> str:
    name = first_value(item, ["name", "product", "title", "supplier"], "Unnamed candidate")
    platform = first_value(item, ["platform", "source_platform"])
    price = first_value(item, ["price", "cost", "supplier_price", "price_moq"])
    margin = first_value(item, ["margin", "estimated_margin"])
    match = first_value(item, ["match", "match_level", "conclusion", "confidence"])
    supplier = first_value(item, ["supplier", "company"])
    reason = first_value(item, ["reason", "evidence", "substitute_reason", "judgment"])
    risk = first_value(item, ["risk", "risks"])
    url = first_value(item, ["verified_url"])
    sourcing_url = first_value(item, ["sourcing_url", "source_search_url", "supplier_url", "source_url"])
    sourcing_label = first_value(item, ["sourcing_label", "source_link_label"], "货源链接")
    alternative_url = first_value(item, ["alternative_url", "substitute_url", "alternative_search_url"])
    alternative_label = first_value(item, ["alternative_label", "substitute_link_label"], "平替链接")
    contact = first_value(item, ["contact", "contact_path", "contact_url"])
    image_note = first_value(item, ["image_note", "image_source", "image_provenance"])
    badges = "".join([pill(badge), pill(platform), pill(match)])
    rows = [
        ("Price / MOQ", price),
        ("Estimated margin", margin),
        ("Supplier", supplier),
        ("Contact", contact),
        ("Image", image_note),
        ("Evidence / reason", reason),
        ("Risk", risk),
    ]
    detail = "\n".join(
        f'<div class="detail-row"><span>{esc(label)}</span><strong>{esc(value)}</strong></div>'
        for label, value in rows
        if value
    )
    links = "".join(
        [
            action_link(url, "商品链接", "primary") if url else "",
            action_link(sourcing_url, sourcing_label, "source"),
            action_link(alternative_url, alternative_label, "alternative"),
        ]
    )
    return f"""
    <article class="product-card">
      <div class="image-wrap">{image_html(item, name)}</div>
      <div class="card-body">
        <div class="badges">{badges}</div>
        <h3>{esc(name)}</h3>
        <div class="details">{detail}</div>
        <div class="card-link">{links or link_html(url, "Verified link" if url else "")}</div>
      </div>
    </article>
    """


def table(items: list[dict[str, Any]], columns: list[tuple[str, list[str]]]) -> str:
    if not items:
        return '<p class="muted">No rows.</p>'
    head = "".join(f"<th>{esc(label)}</th>" for label, _ in columns)
    rows = []
    for item in items:
        cells = []
        for label, keys in columns:
            value = first_value(item, keys)
            if "link" in label.lower() or "url" in label.lower() or "\u94fe\u63a5" in label:
                value = link_html(value, "Open")
                cells.append(f"<td>{value}</td>")
            else:
                cells.append(f"<td>{esc(value)}</td>")
        rows.append(f"<tr>{''.join(cells)}</tr>")
    return f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'


def render(data: dict[str, Any], template_path: str | Path | None = None) -> str:
    title = first_value(data, ["title", "report_title"], "Source Scout Report")
    query_date = first_value(data, ["query_date", "date"])
    market = first_value(data, ["market", "country"])
    window = first_value(data, ["window", "time_window", "observed_window"])
    platforms = ", ".join(str(x) for x in list_value(data.get("platforms")))
    original = data.get("original") or data.get("original_product") or {}
    exact = list_value(data.get("exact_matches"))
    alternatives = list_value(data.get("alternatives")) or list_value(data.get("substitutes"))
    categories = list_value(data.get("trend_categories")) or list_value(data.get("categories"))
    sources = list_value(data.get("sources")) or list_value(data.get("references"))
    notes = list_value(data.get("notes")) + list_value(data.get("risks"))
    original_link = first_value(original, ["verified_url", "url", "link", "original_url", "product_url"]) if isinstance(original, dict) else ""
    original_title = first_value(original, ["name", "title"]) if isinstance(original, dict) else ""
    original_platform = first_value(original, ["platform"]) if isinstance(original, dict) else ""
    original_price = first_value(original, ["price", "selling_price"]) if isinstance(original, dict) else ""
    is_trend_report = bool(categories) and not original_link
    if categories and (
        "趋势" in original_title
        or "trend" in original_title.lower()
        or "多平台" in original_platform
        or original_price.strip().lower() in {"不适用", "n/a", "na", "not applicable"}
    ):
        is_trend_report = True

    hero_meta = "".join(
        pill(value)
        for value in [query_date and f"Checked {query_date}", market, window, platforms]
        if value
    )

    original_block = ""
    if isinstance(original, dict) and original and not is_trend_report:
        original_block = f"""
        <section class="band">
          <div class="section-head"><h2>原商品</h2></div>
          <div class="original">
            <div class="image-wrap">{image_html(original, first_value(original, ["name", "title"], "Original item"))}</div>
            <div>
              <h3>{esc(first_value(original, ["name", "title"], "Original item"))}</h3>
              <p>{esc(first_value(original, ["summary", "description"]))}</p>
              <div class="details">
                <div class="detail-row"><span>Platform</span><strong>{esc(first_value(original, ["platform"]))}</strong></div>
                <div class="detail-row"><span>Price</span><strong>{esc(first_value(original, ["price", "selling_price"]))}</strong></div>
                <div class="detail-row"><span>Link</span><strong>{link_html(first_value(original, ["verified_url", "url", "link"]), "Open")}</strong></div>
                <div class="detail-row"><span>货源链接</span><strong>{link_html(first_value(original, ["sourcing_url", "source_search_url", "supplier_url", "source_url"]), first_value(original, ["sourcing_label"], "Open"))}</strong></div>
                <div class="detail-row"><span>平替链接</span><strong>{link_html(first_value(original, ["alternative_url", "substitute_url", "alternative_search_url"]), first_value(original, ["alternative_label"], "Open"))}</strong></div>
              </div>
            </div>
          </div>
        </section>
        """

    exact_cards = "\n".join(card(item, "同款/高相似") for item in exact)
    alt_cards = "\n".join(card(item, "平替") for item in alternatives)
    exact_section = ""
    if exact or not is_trend_report:
        exact_section = f"""
    <section class="band">
      <div class="section-head"><h2>同款 / 高相似货源</h2><p>仅展示已通过验证的直链或 Alibaba 搜索入口。</p></div>
      <div class="grid">{exact_cards or '<p class="muted">No verified exact matches.</p>'}</div>
    </section>"""

    category_blocks = []
    for category in categories:
        if not isinstance(category, dict):
            continue
        name = first_value(category, ["category", "name"], "Category")
        signal = first_value(category, ["signal", "trend_signal", "summary"])
        items = list_value(category.get("items")) or list_value(category.get("top_products"))
        cards = "\n".join(card(item, f"{name} Top") for item in items if isinstance(item, dict))
        category_blocks.append(
            f"""
            <section class="band">
              <div class="section-head"><h2>{esc(name)}</h2><p>{esc(signal)}</p></div>
              <div class="grid">{cards or '<p class="muted">No candidates.</p>'}</div>
            </section>
            """
        )

    source_items = []
    for source in sources:
        if isinstance(source, dict):
            source_items.append(
                f"<li>{esc(first_value(source, ['name', 'title'], 'Source'))}: "
                f"{link_html(first_value(source, ['url', 'link']), 'Open')}</li>"
            )
        else:
            source_items.append(f"<li>{esc(source)}</li>")

    note_items = "".join(f"<li>{esc(note)}</li>" for note in notes if note)

    alternatives_section = ""
    if not is_trend_report:
        alternatives_section = f"""
    <section class="band">
      <div class="section-head"><h2>平替商品 Top 3</h2><p>按采购成本、功能相似度、可验证链接和风险综合排序。</p></div>
      <div class="grid">{alt_cards or '<p class="muted">No verified alternatives.</p>'}</div>
    </section>
    """

    template_text = load_template(template_path)
    if template_text:
        return render_template(
            template_text,
            {
                "title": esc(title),
                "hero_meta": hero_meta,
                "summary_html": esc(
                    first_value(
                        data,
                        ["summary", "executive_summary"],
                        "Verified sourcing candidates, alternatives, margins, and risks.",
                    )
                ),
                "original_block": original_block,
                "exact_section": exact_section,
                "alternatives_section": alternatives_section,
                "category_sections": "".join(category_blocks),
                "note_items": note_items or "<li>No additional notes.</li>",
                "source_items": "".join(source_items) or "<li>No sources listed.</li>",
            },
        )

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)}</title>
  <style>
    :root {{
      --bg: #f6f7f9;
      --ink: #18202a;
      --muted: #627084;
      --line: #dce2ea;
      --panel: #ffffff;
      --accent: #0b6bcb;
      --accent-soft: #e7f1fd;
      --risk: #9f3a20;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.55;
    }}
    a {{ color: var(--accent); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .shell {{ max-width: 1180px; margin: 0 auto; padding: 28px 20px 56px; }}
    .hero {{
      display: grid;
      gap: 16px;
      padding: 28px 0 18px;
      border-bottom: 1px solid var(--line);
    }}
    .hero h1 {{ margin: 0; font-size: 34px; line-height: 1.1; letter-spacing: 0; }}
    .hero p {{ margin: 0; max-width: 820px; color: var(--muted); }}
    .toolbar {{ display: flex; gap: 10px; flex-wrap: wrap; }}
    button {{
      border: 1px solid var(--line);
      background: var(--panel);
      color: var(--ink);
      padding: 9px 12px;
      border-radius: 6px;
      cursor: pointer;
    }}
    .badges, .meta {{ display: flex; gap: 8px; flex-wrap: wrap; }}
    .pill {{
      display: inline-flex;
      align-items: center;
      border: 1px solid var(--line);
      background: var(--accent-soft);
      color: #164f8f;
      border-radius: 999px;
      padding: 3px 9px;
      font-size: 12px;
      font-weight: 650;
      max-width: 100%;
      white-space: nowrap;
      overflow-wrap: normal;
      word-break: normal;
    }}
    .pill.long-pill {{
      display: inline-block;
      flex-basis: 100%;
      white-space: normal;
      line-height: 1.45;
      border-radius: 8px;
      padding: 7px 10px;
    }}
    .meta .pill.long-pill {{
      flex-basis: auto;
      max-width: 100%;
    }}
    .band {{ padding: 28px 0; border-bottom: 1px solid var(--line); }}
    .section-head {{ display: flex; justify-content: space-between; gap: 16px; align-items: end; margin-bottom: 16px; }}
    .section-head h2 {{ margin: 0; font-size: 22px; letter-spacing: 0; }}
    .section-head p {{ margin: 0; color: var(--muted); max-width: 680px; }}
    .grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }}
    .grid > *,
    .product-card,
    .card-body,
    .details,
    .detail-row,
    .detail-row strong {{
      min-width: 0;
    }}
    .product-card, .original {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }}
    .product-card {{ display: grid; grid-template-rows: auto 1fr; }}
    .original {{ display: grid; grid-template-columns: 260px 1fr; gap: 18px; padding: 14px; }}
    .image-wrap {{ background: #eef2f6; height: 210px; width: 100%; display: grid; place-items: center; overflow: hidden; }}
    .product-image {{ width: 100%; height: 100%; max-width: 100%; max-height: 100%; object-fit: contain; object-position: center; background: #fff; }}
    .image-note {{
      align-self: end;
      justify-self: stretch;
      padding: 5px 8px;
      background: rgba(24, 32, 42, .72);
      color: #fff;
      font-size: 11px;
      text-align: center;
    }}
    .image-placeholder {{
      width: 100%;
      height: 210px;
      display: grid;
      place-items: center;
      padding: 20px;
      color: var(--muted);
      font-size: 13px;
      border: 1px dashed #b8c4d2;
      background: repeating-linear-gradient(45deg, #f8fafc, #f8fafc 10px, #eef2f6 10px, #eef2f6 20px);
    }}
    .card-body {{ padding: 14px; display: grid; gap: 10px; align-content: start; }}
    .card-body h3, .original h3 {{ margin: 0; font-size: 17px; line-height: 1.3; letter-spacing: 0; }}
    .details {{ display: grid; gap: 6px; }}
    .detail-row {{ display: grid; grid-template-columns: 112px 1fr; gap: 10px; font-size: 13px; }}
    .detail-row span {{ color: var(--muted); }}
    .detail-row strong {{
      font-weight: 600;
      overflow-wrap: anywhere;
      word-break: break-word;
      max-width: 100%;
    }}
    .card-link {{ margin-top: 4px; }}
    .card-link,
    .link-actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
    }}
    .link-chip {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 30px;
      border-radius: 7px;
      padding: 5px 10px;
      border: 1px solid #bfd8ff;
      background: #e8f1ff;
      color: #1457a8;
      font-size: 12px;
      font-weight: 760;
      line-height: 1.2;
      text-decoration: none;
    }}
    .link-chip:hover {{ text-decoration: none; filter: brightness(.98); }}
    .link-chip.source {{
      border-color: #a9ddd4;
      background: #e3f7f4;
      color: #006b68;
    }}
    .link-chip.alternative {{
      border-color: #b7e7c9;
      background: #e8f8ef;
      color: #08713f;
    }}
    .link-status {{
      display: inline-flex;
      align-items: center;
      min-height: 26px;
      border-radius: 6px;
      padding: 3px 8px;
      background: #eef3f8;
      color: #506176;
      font-weight: 650;
      line-height: 1.35;
    }}
    .table-wrap {{ overflow: hidden; max-width: 100%; background: var(--panel); border: 1px solid var(--line); border-radius: 8px; }}
    table {{ width: 100%; border-collapse: collapse; table-layout: fixed; }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; font-size: 13px; overflow-wrap: anywhere; word-break: break-word; }}
    td a, td code {{ overflow-wrap: anywhere; word-break: break-word; }}
    th {{ background: #f0f4f8; font-size: 12px; text-transform: uppercase; letter-spacing: .02em; color: var(--muted); }}
    .muted {{ color: var(--muted); }}
    .notes {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 16px 18px; }}
    .focus-legend {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
      margin-top: 2px;
    }}
    .focus-legend span,
    .mark-platform,
    .mark-money,
    .mark-margin,
    .mark-source,
    .mark-search,
    .mark-risk,
    .mark-caution {{
      display: inline;
      border-radius: 5px;
      padding: 1px 4px;
      font-weight: 760;
      overflow-wrap: anywhere;
      word-break: break-word;
      box-decoration-break: clone;
      -webkit-box-decoration-break: clone;
    }}
    .focus-legend span {{
      display: inline-flex;
      align-items: center;
      min-height: 24px;
      font-size: 12px;
      border: 1px solid transparent;
      padding: 3px 8px;
    }}
    .legend-platform,
    .mark-platform {{
      color: #1457a8;
      background: #e8f1ff;
      border-color: #bfd8ff;
    }}
    .legend-money,
    .mark-money,
    .mark-margin {{
      color: #08713f;
      background: #e8f8ef;
      border-color: #b7e7c9;
    }}
    .legend-source,
    .mark-source,
    .mark-search {{
      color: #006b68;
      background: #e3f7f4;
      border-color: #b5e5de;
    }}
    .legend-risk,
    .mark-risk,
    .mark-caution {{
      color: #a33b17;
      background: #fff0e7;
      border-color: #ffd0b7;
    }}
    .mark-caution {{
      color: #8a1f11;
      background: #ffe9e7;
    }}
    .row-margin,
    .row-price,
    .row-reason,
    .row-risk {{
      border-radius: 6px;
      padding: 4px 6px;
      margin: -4px 0;
    }}
    .row-margin {{ background: linear-gradient(90deg, rgba(15, 154, 89, .11), transparent 78%); }}
    .row-price {{ background: linear-gradient(90deg, rgba(11, 107, 203, .09), transparent 78%); }}
    .row-reason {{ background: linear-gradient(90deg, rgba(0, 107, 104, .09), transparent 78%); }}
    .row-risk {{ background: linear-gradient(90deg, rgba(163, 59, 23, .12), transparent 82%); }}
    .row-margin > span,
    .row-price > span,
    .row-reason > span,
    .row-risk > span {{
      font-weight: 750;
    }}
    .row-margin > span {{ color: #08713f; }}
    .row-price > span {{ color: #1457a8; }}
    .row-reason > span {{ color: #006b68; }}
    .row-risk > span {{ color: #a33b17; }}
    .notes li {{
      margin: 8px 0;
    }}
    @media (max-width: 900px) {{
      .grid {{ grid-template-columns: 1fr; }}
      .original {{ grid-template-columns: 1fr; }}
      .hero h1 {{ font-size: 28px; }}
    }}
    @media print {{
      body {{ background: #fff; }}
      .shell {{ max-width: none; padding: 0; }}
      .toolbar {{ display: none; }}
      .band {{ break-inside: avoid; }}
      a {{ color: #000; text-decoration: underline; }}
      .mark-platform,
      .mark-money,
      .mark-margin,
      .mark-source,
      .mark-search,
      .mark-risk,
      .mark-caution {{
        color: #000;
        border: 1px solid #ddd;
        background: #f7f7f7;
      }}
    }}
  </style>
</head>
<body>
  <main class="shell">
    <header class="hero">
      <div class="toolbar"><button onclick="window.print()">Print / Save PDF</button></div>
      <h1>{esc(title)}</h1>
      <div class="meta">{hero_meta}</div>
      <p>{esc(first_value(data, ["summary", "executive_summary"], "Verified sourcing candidates, alternatives, margins, and risks."))}</p>
      <div class="focus-legend" aria-label="阅读重点图例">
        <span class="legend-platform">平台/渠道</span>
        <span class="legend-money">价格/利润率</span>
        <span class="legend-source">中国货源/搜索词</span>
        <span class="legend-risk">风险/合规</span>
      </div>
    </header>
    {original_block}
    {exact_section}
    {alternatives_section}
    {''.join(category_blocks)}
    <section class="band">
      <div class="section-head"><h2>Risks And Notes</h2></div>
      <div class="notes"><ul>{note_items or '<li>No additional notes.</li>'}</ul></div>
    </section>
    <section class="band">
      <div class="section-head"><h2>Sources</h2></div>
      <div class="notes"><ul>{''.join(source_items) or '<li>No sources listed.</li>'}</ul></div>
    </section>
    <script>
      (() => {{
        const rules = [
          {{
            className: "mark-platform",
            pattern: /(Amazon|Walmart|Target|eBay|Etsy|TikTok Shop|TikTok|Temu|SHEIN|AliExpress|Shopify\\/DTC|Shopify|Zalando|Vinted|OTTO|Cdiscount|ManoMano|bol\\.com|Best Buy|Chewy|Wayfair|Alibaba)/g
          }},
          {{
            className: "mark-source",
            pattern: /(中国货源|中国供应链|工厂|源头工厂|贴牌|OEM|ODM|private label|manufacturer|factory|wholesale|批发|定制|搜索)/gi
          }},
          {{
            className: "mark-margin",
            pattern: /(约\\s*\\d+(?:\\.\\d+)?%-\\d+(?:\\.\\d+)?%|目标粗算利润率\\s*\\d+%\\+?|利润率\\s*\\d+%\\+?)/g
          }},
          {{
            className: "mark-money",
            pattern: /(\\$\\d+(?:\\.\\d+)?(?:-\\$?\\d+(?:\\.\\d+)?)?|\\d+(?:\\.\\d+)?%\\s*|\\b\\d+\\s*pack\\b|\\b\\d+mAh\\b)/gi
          }},
          {{
            className: "mark-risk",
            pattern: /(风险|避免|不建议|必须|需要|核验|认证|侵权|合规|退货|售后|商标|专利|版权|FDA|OTC|FCC|CE|RoHS|UN38\\.3|MSDS|ETL|UL|UKCA|COA|INCI|平台政策|运输限制|仿冒)/g
          }}
        ];

        const escapeHtml = (value) => value
          .replace(/&/g, "&amp;")
          .replace(/</g, "&lt;")
          .replace(/>/g, "&gt;");

        const shouldSkip = (node) => {{
          const parent = node.parentElement;
          return !parent || parent.closest("a, script, style, .pill, .badges, .meta, .image-note, .focus-legend, [data-highlighted='true']");
        }};

        const highlightNode = (node) => {{
          const text = node.nodeValue;
          if (!text || !rules.some((rule) => rule.pattern.test(text))) {{
            rules.forEach((rule) => {{ rule.pattern.lastIndex = 0; }});
            return;
          }}

          let html = escapeHtml(text);
          for (const rule of rules) {{
            rule.pattern.lastIndex = 0;
            html = html.replace(rule.pattern, (match) => {{
              const caution = rule.className === "mark-margin" && match.includes("-") ? " mark-caution" : "";
              return `<span class="${{rule.className}}${{caution}}">${{match}}</span>`;
            }});
          }}

          const template = document.createElement("template");
          template.innerHTML = html;
          template.content.querySelectorAll("span").forEach((span) => {{
            span.dataset.highlighted = "true";
          }});
          node.replaceWith(template.content);
        }};

        document.querySelectorAll(".meta .pill:last-child, .badges .pill:nth-child(2)").forEach((pill) => {{
          pill.classList.add("long-pill");
        }});

        const targets = document.querySelectorAll(".hero p, .card-body strong, .notes li, td, h3, .section-head p");
        for (const target of targets) {{
          const walker = document.createTreeWalker(target, NodeFilter.SHOW_TEXT);
          const nodes = [];
          while (walker.nextNode()) nodes.push(walker.currentNode);
          nodes.forEach((node) => {{
            if (!shouldSkip(node)) highlightNode(node);
          }});
        }}

        document.querySelectorAll(".detail-row").forEach((row) => {{
          const label = row.querySelector("span")?.textContent || "";
          if (label.includes("Estimated margin")) row.classList.add("row-margin");
          if (label.includes("Price")) row.classList.add("row-price");
          if (label.includes("Evidence")) row.classList.add("row-reason");
          if (label.includes("Risk")) row.classList.add("row-risk");
        }});
      }})();
    </script>
  </main>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a fixed-layout Source Scout HTML report.")
    parser.add_argument("--input", required=True, help="Report JSON path.")
    parser.add_argument("--output", required=True, help="HTML output path.")
    parser.add_argument(
        "--template",
        default="",
        help="Optional HTML template path. Defaults to templates/report-template.html next to the skill.",
    )
    args = parser.parse_args()
    data = json.loads(Path(args.input).read_text(encoding="utf-8-sig"))
    html_text = render(data, args.template or None)
    Path(args.output).write_text(html_text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
