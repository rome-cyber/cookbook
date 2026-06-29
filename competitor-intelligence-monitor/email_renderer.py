"""
Renders the competitor digest as an HTML email.
Mirrors the Slack DM structure exactly — same sections, same filtering logic,
just formatted for email instead of Block Kit.
"""

FROM_ADDRESS = "onboarding@resend.dev"
FROM_NAME    = "Nimble Competitor Monitor"
REPLY_TO     = "digest@nimbleway.com"

NIMBLE_BLUE = "#2563eb"
FONT        = "-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif"

COLORS = {
    "bg":            "#f4f5f7",
    "card":          "#ffffff",
    "border":        "#e5e7eb",
    "header_bg":     "#0f1117",
    "header_text":   "#ffffff",
    "header_muted":  "#9ca3af",
    "accent":        NIMBLE_BLUE,
    "muted":         "#6b7280",
    "body_text":     "#111827",
    "item_bg":       "#f9fafb",
    "signal_bg":     "#fefce8",
    "signal_border": "#d97706",
    "signal_label":  "#d97706",
    "footer_bg":     "#f4f5f7",
    "footer_border": "#e5e7eb",
    "footer_text":   "#9ca3af",
}

CATEGORY_COLORS = {
    "Product Launch": "#2563eb",
    "Funding":        "#16a34a",
    "M&A":            "#16a34a",
    "Funding/M&A":    "#16a34a",
    "Partnership":    "#7c3aed",
    "Hiring":         "#d97706",
}
DEFAULT_ITEM_BORDER = "#e5e7eb"


def _cap(s: str, n: int = 300) -> str:
    return (s[:n] + "…") if len(s) > n else s


def _tag(text: str) -> str:
    return (
        f'<span style="display:inline-block;background:{COLORS["card"]};'
        f'border:1px solid {COLORS["border"]};color:{COLORS["muted"]};'
        f'padding:2px 8px;border-radius:4px;font-size:11px;'
        f'font-family:{FONT};margin:2px 4px 0 0;">{text}</span>'
    )


def _category_color(category: str) -> str:
    return CATEGORY_COLORS.get(category, DEFAULT_ITEM_BORDER)


def _finding_row(f: dict) -> str:
    cat     = f.get("category", "")
    title   = (f.get("title") or "")[:100]
    url     = f.get("url", "")
    summary = _cap(f.get("summary") or "")
    plat    = f.get("platform", "")
    src     = f.get("source_type", "")
    color   = _category_color(cat)

    if url:
        title_html = (
            f'<a href="{url}" style="color:{COLORS["accent"]};text-decoration:none;'
            f'font-weight:600;font-size:14px;line-height:1.5;">{title}</a>'
        )
    else:
        title_html = (
            f'<strong style="font-size:14px;color:{COLORS["body_text"]};'
            f'line-height:1.5;">{title}</strong>'
        )
    tags = "".join(_tag(t) for t in [cat, plat, src] if t)

    return f"""<tr><td style="padding:0 0 8px 0;">
  <table width="100%" cellpadding="0" cellspacing="0" role="presentation">
    <tr><td style="background:{COLORS['item_bg']};border:1px solid {COLORS['border']};
         border-left:3px solid {color};border-radius:4px;padding:12px 16px;">
      <div style="margin-bottom:6px;">{title_html}</div>
      <div style="font-size:13px;color:{COLORS['muted']};line-height:1.6;
           font-style:italic;margin-bottom:8px;">{summary}</div>
      <div>{tags}</div>
    </td></tr>
  </table>
</td></tr>"""


def _section_rows(label: str, items_html: str, is_first: bool) -> str:
    divider = (
        "" if is_first else
        f'<tr><td style="padding:0 32px 0;">'
        f'<div style="border-top:1px solid {COLORS["border"]};"></div>'
        f'</td></tr>\n'
    )
    return (
        f'{divider}'
        f'<tr><td style="padding:20px 32px 8px;">'
        f'<span style="font-size:11px;font-weight:700;letter-spacing:0.08em;'
        f'color:{COLORS["muted"]};text-transform:uppercase;font-family:{FONT};">'
        f'{label}</span></td></tr>\n'
        f'<tr><td style="padding:0 32px 0;">'
        f'<table width="100%" cellpadding="0" cellspacing="0" role="presentation">'
        f'{items_html}'
        f'</table></td></tr>'
    )


def build_email_html(
    name: str,
    team: str,
    date_range: str,
    overview: str,
    signal,
    findings: list,
    nimble_findings: list,
    positioning_alerts: list,
    brief: bool,
    sheet_url: str = "",
) -> str:

    name_label = ""
    if name and team:
        name_label = f"For {name} &nbsp;&middot;&nbsp; {team}"
    elif name:
        name_label = f"For {name}"
    elif team:
        name_label = team

    rows = []

    # ── Overview ──────────────────────────────────────────────────────────────
    if overview:
        rows.append(
            f'<tr><td style="padding:28px 32px 20px;">'
            f'<p style="font-size:16px;line-height:1.7;color:{COLORS["body_text"]};'
            f'margin:0;max-width:520px;">{overview}</p>'
            f'</td></tr>'
        )

    # ── Signal of the Day ─────────────────────────────────────────────────────
    if signal and signal.get("title"):
        if rows:
            rows.append(
                f'<tr><td style="padding:0 32px 4px;">'
                f'<div style="border-top:1px solid {COLORS["border"]};"></div>'
                f'</td></tr>'
            )
        sig_url   = signal.get("url", "")
        sig_title = signal.get("title", "")
        if sig_url:
            sig_heading = (
                f'<a href="{sig_url}" style="color:{COLORS["body_text"]};text-decoration:none;'
                f'font-weight:600;font-size:15px;line-height:1.5;">{sig_title}</a>'
            )
        else:
            sig_heading = (
                f'<strong style="font-size:15px;line-height:1.5;'
                f'color:{COLORS["body_text"]};">{sig_title}</strong>'
            )
        rows.append(f"""<tr><td style="padding:16px 32px 24px;">
  <table width="100%" cellpadding="0" cellspacing="0" role="presentation">
    <tr><td style="background:{COLORS['signal_bg']};border:1px solid #fde68a;
         border-left:4px solid {COLORS['signal_border']};border-radius:4px;
         padding:16px 20px;">
      <div style="font-size:10px;font-weight:700;letter-spacing:0.1em;
           color:{COLORS['signal_label']};text-transform:uppercase;
           margin-bottom:8px;font-family:{FONT};">Signal of the Day</div>
      <div style="color:{COLORS['body_text']};">{sig_heading}</div>
    </td></tr>
  </table>
</td></tr>""")

    # ── Competitor + alert sections ────────────────────────────────────────────
    by_comp = {}
    for f in findings:
        by_comp.setdefault(f.get("competitor", "Unknown"), []).append(f)

    has_sections = bool(positioning_alerts or by_comp or nimble_findings)

    if has_sections and rows:
        rows.append(
            f'<tr><td style="padding:4px 32px 0;">'
            f'<div style="border-top:1px solid {COLORS["border"]};"></div>'
            f'</td></tr>'
        )

    sec_idx = 0

    # Positioning alerts — amber-tinted cross-competitor section
    if positioning_alerts:
        divider = (
            "" if sec_idx == 0 else
            f'<tr><td style="padding:0 32px 0;">'
            f'<div style="border-top:1px solid {COLORS["border"]};"></div>'
            f'</td></tr>\n'
        )
        alert_items = ""
        for a in positioning_alerts:
            tag_label = "Nimble Comparison" if a.get("type") == "nimble_comparison" else "Pitch Change"
            a_url = a.get("url", "")
            a_ttl = (a.get("title") or "")[:100]
            a_sum = _cap(a.get("summary", ""))
            if a_url:
                a_heading = (
                    f'<a href="{a_url}" style="color:{COLORS["accent"]};text-decoration:none;'
                    f'font-weight:600;font-size:14px;">{a_ttl}</a>'
                )
            else:
                a_heading = f'<strong style="font-size:14px;">{a_ttl}</strong>'
            alert_items += f"""<tr><td style="padding:0 0 8px 0;">
  <table width="100%" cellpadding="0" cellspacing="0" role="presentation">
    <tr><td style="background:#ffffff;border:1px solid #fde68a;
         border-left:3px solid {COLORS["signal_border"]};border-radius:4px;padding:12px 16px;">
      <div style="margin-bottom:6px;">{a_heading}</div>
      <div style="font-size:13px;color:{COLORS['muted']};line-height:1.6;
           font-style:italic;margin-bottom:8px;">{a_sum}</div>
      <div>{_tag(tag_label)}{_tag("Positioning")}</div>
    </td></tr>
  </table>
</td></tr>"""
        rows.append(
            f'{divider}'
            f'<tr><td style="background:#fffbeb;padding:20px 32px 8px;">'
            f'<span style="font-size:10px;font-weight:700;letter-spacing:0.1em;'
            f'color:{COLORS["signal_label"]};text-transform:uppercase;font-family:{FONT};">'
            f'Positioning Alerts</span></td></tr>\n'
            f'<tr><td style="background:#fffbeb;padding:0 32px 16px;">'
            f'<table width="100%" cellpadding="0" cellspacing="0" role="presentation">'
            f'{alert_items}'
            f'</table></td></tr>'
        )
        sec_idx += 1

    # Competitor findings
    for comp, items in by_comp.items():
        top = items[:1] if brief else items[:3]
        items_html = "".join(_finding_row(f) for f in top)
        rows.append(_section_rows(comp, items_html, sec_idx == 0))
        sec_idx += 1

    # Nimble section
    if nimble_findings:
        top = nimble_findings[:1] if brief else nimble_findings[:3]
        items_html = "".join(_finding_row(f) for f in top)
        rows.append(_section_rows("Nimble — What People Are Saying", items_html, sec_idx == 0))
        sec_idx += 1

    # Bottom spacer before footer
    if sec_idx > 0:
        rows.append('<tr><td style="padding:12px 0 0;"></td></tr>')

    # ── Footer ────────────────────────────────────────────────────────────────
    db_link_html = ""
    if sheet_url:
        db_link_html = (
            f'<div style="margin-top:6px;font-size:11px;">'
            f'<a href="{sheet_url}" style="color:{COLORS["accent"]};'
            f'text-decoration:none;">View full database</a></div>'
        )

    body_html = "\n".join(rows)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>Competitor Digest — {date_range}</title>
</head>
<body style="margin:0;padding:0;background:{COLORS['bg']};font-family:{FONT};">
  <table width="100%" cellpadding="0" cellspacing="0" role="presentation"
         style="background:{COLORS['bg']};padding:32px 16px;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" role="presentation"
             style="max-width:600px;width:600px;">

        <!-- Header -->
        <tr><td style="background:{COLORS['header_bg']};padding:28px 32px;
                border-radius:8px 8px 0 0;">
          <table width="100%" cellpadding="0" cellspacing="0" role="presentation">
            <tr>
              <td valign="bottom">
                <div style="color:{NIMBLE_BLUE};font-size:11px;font-weight:700;
                     letter-spacing:0.1em;text-transform:uppercase;
                     margin-bottom:8px;font-family:{FONT};">Nimble</div>
                <div style="color:{COLORS['header_text']};font-size:20px;
                     font-weight:600;line-height:1.2;font-family:{FONT};">
                  Competitor Digest
                </div>
                {f'<div style="color:{COLORS["header_muted"]};font-size:14px;margin-top:6px;font-weight:400;font-family:{FONT};">{name_label}</div>' if name_label else ""}
              </td>
              <td align="right" valign="top">
                <div style="color:{COLORS['header_muted']};font-size:13px;
                     white-space:nowrap;font-family:{FONT};">{date_range}</div>
              </td>
            </tr>
          </table>
        </td></tr>

        <!-- Body -->
        <tr><td style="background:{COLORS['card']};border:1px solid {COLORS['border']};
                border-top:none;">
          <table width="100%" cellpadding="0" cellspacing="0" role="presentation">

            {body_html}

            <!-- Footer -->
            <tr><td style="background:{COLORS['footer_bg']};padding:20px 32px;
                 border-top:1px solid {COLORS['footer_border']};
                 border-radius:0 0 8px 8px;">
              <table width="100%" cellpadding="0" cellspacing="0" role="presentation">
                <tr>
                  <td>
                    <div style="font-size:12px;color:{COLORS['footer_text']};
                         margin-bottom:4px;font-family:{FONT};">
                      Nimble &nbsp;&middot;&nbsp; Competitor Intelligence
                    </div>
                    <div style="font-size:11px;color:{COLORS['footer_text']};
                         font-family:{FONT};">
                      You're receiving this because you enabled competitor
                      digest in Nimble.
                    </div>
                    {db_link_html}
                  </td>
                  <td align="right" valign="middle">
                    <a href="https://nimbleway.com/unsubscribe"
                       style="font-size:12px;color:{COLORS['footer_text']};
                              text-decoration:underline;font-family:{FONT};">
                      Unsubscribe
                    </a>
                  </td>
                </tr>
              </table>
            </td></tr>

          </table>
        </td></tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""


def build_email_text(
    name: str,
    team: str,
    date_range: str,
    overview: str,
    signal,
    findings: list,
    nimble_findings: list,
    positioning_alerts: list,
) -> str:
    lines = []
    lines.append(f"COMPETITOR DIGEST — {date_range}")
    if name:
        lines.append(f"For {name}" + (f" · {team}" if team else ""))
    lines.append("=" * 60)
    lines.append("")

    if overview:
        lines.append(overview)
        lines.append("")

    if signal and signal.get("title"):
        lines.append("SIGNAL OF THE DAY")
        lines.append(f"  {signal['title']}")
        if signal.get("url"):
            lines.append(f"  {signal['url']}")
        lines.append("")

    if positioning_alerts:
        lines.append("POSITIONING ALERTS")
        for a in positioning_alerts:
            lines.append(f"  • {a.get('competitor', '')}: {(a.get('title') or '')[:80]}")
            if a.get("summary"):
                lines.append(f"    {_cap(a.get('summary', ''), 150)}")
        lines.append("")

    by_comp = {}
    for f in findings:
        by_comp.setdefault(f.get("competitor", "Unknown"), []).append(f)

    for comp, items in by_comp.items():
        lines.append(comp.upper())
        for item in items[:3]:
            lines.append(f"  • {(item.get('title') or '')[:80]}")
            if item.get("summary"):
                lines.append(f"    {_cap(item.get('summary', ''), 150)}")
        lines.append("")

    if nimble_findings:
        lines.append("NIMBLE — WHAT PEOPLE ARE SAYING")
        for item in nimble_findings[:3]:
            lines.append(f"  • {(item.get('title') or '')[:80]}")
            if item.get("summary"):
                lines.append(f"    {_cap(item.get('summary', ''), 150)}")
        lines.append("")

    lines.append("─" * 60)
    lines.append("Nimble · Competitor Intelligence")
    lines.append(
        "You're receiving this because you enabled competitor digest in Nimble."
    )
    lines.append("Unsubscribe: https://nimbleway.com/unsubscribe")

    return "\n".join(lines)


def build_email_subject(date_range: str, signal, n_signals: int = 0) -> str:
    prefix = f"Competitor Digest [{date_range}]"
    if signal and signal.get("title"):
        headline  = signal["title"]
        max_head  = 60 - len(prefix) - 4  # " — " = 4 chars
        if max_head > 10:
            if len(headline) > max_head:
                headline = headline[: max_head - 1] + "…"
            return f"{prefix} — {headline}"
    if n_signals:
        return f"{prefix} — {n_signals} signals this week"
    return prefix


def send_digest_email(
    to_email: str,
    name: str,
    team: str,
    date_range: str,
    overview: str,
    signal,
    findings: list,
    nimble_findings: list,
    positioning_alerts: list,
    brief: bool,
    sheet_url: str = "https://docs.google.com/spreadsheets/d/1LH46EcLK06e17gtRaipHVtXbMBnxrWCveHLxIMfVQ50/edit",
) -> bool:
    """Send the digest email via Resend. Returns True on success."""
    import os, hashlib, resend

    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        print(f"[Email] No RESEND_API_KEY — skipping {to_email}")
        return False

    resend.api_key = api_key

    n_signals = len(findings) + len(nimble_findings) + len(positioning_alerts)

    html    = build_email_html(name, team, date_range, overview, signal,
                               findings, nimble_findings, positioning_alerts,
                               brief, sheet_url)
    text    = build_email_text(name, team, date_range, overview, signal,
                               findings, nimble_findings, positioning_alerts)
    subject = build_email_subject(date_range, signal, n_signals)

    unique_id = hashlib.md5(f"{to_email}{date_range}".encode()).hexdigest()

    try:
        resp = resend.Emails.send({
            "from":     f"{FROM_NAME} <{FROM_ADDRESS}>",
            "to":       [to_email],
            "reply_to": REPLY_TO,
            "subject":  subject,
            "html":     html,
            "text":     text,
            "headers":  {"X-Entity-Ref-ID": unique_id},
        })
        print(f"[Email] → {to_email} ({team}, {date_range}) id={getattr(resp, 'id', resp)}")
        return True
    except Exception as e:
        print(f"[Email] Failed for {to_email}: {e!r}")
        return False
