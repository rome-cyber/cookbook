import os
import json
import base64
import html as html_lib
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import timedelta
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials

load_dotenv(override=True)

# ─── Load config ─────────────────────────────────────────────────────────────
_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
with open(_CONFIG_PATH) as _f:
    _CONFIG = json.load(_f)

YOUR_COMPANY = _CONFIG["your_company"]["name"]
_comps       = _CONFIG["competitors"]

COMPETITOR_COLORS = {c["name"]: c["color"] for c in _comps}
COMPETITORS       = [c["name"] for c in _comps]
ALL_COLORS        = {**COMPETITOR_COLORS, YOUR_COMPANY: "#1a3a5c"}

st.set_page_config(page_title=f"{YOUR_COMPANY} Competitor Intelligence", page_icon=YOUR_COMPANY[0].upper(), layout="wide")

SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
SCOPES   = ["https://www.googleapis.com/auth/spreadsheets"]
IMPACT_WEIGHTS = {"High": 3, "Medium": 2, "Low": 1}
IMPACT_ORDER   = {"High": 0, "Medium": 1, "Low": 2, "?": 3}
IMPACT_BG      = {"High": "#fdecea", "Medium": "#fff3e0", "Low": "#f5f5f5"}
IMPACT_FG      = {"High": "#c0392b", "Medium": "#e67e22", "Low": "#888"}
SENT_COLOR     = {"positive": "#27ae60", "negative": "#e74c3c", "neutral": "#95a5a6"}
CHART_BASE     = dict(
    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    margin=dict(t=24, b=20, l=0, r=0), font=dict(family="sans-serif", size=12),
)

# "Use this when..." map for battlecards
USE_WHEN = {
    "Pricing":           "a prospect raises cost concerns or asks how competitors compare on price",
    "Reliability":       "a prospect asks about API uptime, stability, or has been burned by outages before",
    "Customer Feedback": "a prospect asks for references or has heard mixed things about this vendor",
    "Community":         "a technical buyer or developer asks what the market thinks of this vendor",
    "Funding":           "a prospect asks why they should choose Nimble over a well-funded competitor",
    "Product Launch":    "a prospect brings up this competitor's new feature or capability",
    "Hiring":            "you need to create urgency — they are scaling their sales team right now",
    "Partnership":       "a prospect asks about ecosystem integrations or platform compatibility",
}

# "How to position Nimble" map for talking points
HOW_TO_POSITION = {
    ("Funding",           "positive"): "A funding round signals ambition but also complexity. Ask: 'What does a 12-18 month integration roadmap mean for your launch timeline?' Nimble is production-ready today.",
    ("Product Launch",    "positive"): "Open your demo with Nimble's equivalent capability. Focus on reliability and data quality — areas where new launches consistently underdeliver in the first 6 months.",
    ("Pricing",           "negative"): "Lead discovery with: 'We've heard [competitor] is changing pricing — has that come up for you?' If yes, lock in a long-term Nimble contract now.",
    ("Reliability",       "negative"): "Turn this into a risk question: 'What's your fallback plan if [competitor]'s API goes down mid-run?' Walk through Nimble's SLA and incident response.",
    ("Customer Feedback", "negative"): "Offer to connect the prospect with a Nimble customer in their vertical. Real references close faster than any demo.",
    ("Community",         "negative"): "Share the developer signal openly with technical buyers. Transparency is a differentiator — it builds trust that competitors can't fake.",
    ("Hiring",            "positive"): "Note internally: their sales team is growing. Expect heavier competitive pressure in the next 90 days. Prioritize open pipeline velocity now.",
    ("Partnership",       "positive"): "Map their new coverage against your prospect's stack. If there's overlap, lead with Nimble's existing depth and track record on that platform.",
}
DEFAULT_POSITION = "Get specific fast. Pull one concrete Nimble advantage relevant to this prospect's use case — uptime record, data quality SLA, or support response time. Avoid generic claims."

HOW_TO_POSITION = {k: v.replace("Nimble", YOUR_COMPANY) for k, v in HOW_TO_POSITION.items()}
DEFAULT_POSITION = DEFAULT_POSITION.replace("Nimble", YOUR_COMPANY)


# ─── Data ─────────────────────────────────────────────────────────────────────

@st.cache_resource(ttl=300)
def get_client():
    creds_b64  = os.getenv("GOOGLE_SHEETS_CREDENTIALS")
    creds_file = os.getenv("GOOGLE_SHEETS_CREDS_FILE")
    if creds_b64:
        creds = Credentials.from_service_account_info(
            json.loads(base64.b64decode(creds_b64)), scopes=SCOPES)
    elif creds_file:
        creds = Credentials.from_service_account_file(creds_file, scopes=SCOPES)
    else:
        st.error("No Google Sheets credentials found.")
        st.stop()
    return gspread.authorize(creds)


@st.cache_data(ttl=300)
def load_findings() -> pd.DataFrame:
    sh   = get_client().open_by_key(SHEET_ID)
    rows = sh.worksheet("All Findings").get_all_values()
    if len(rows) < 2:
        return pd.DataFrame()
    raw = pd.DataFrame(rows[1:], columns=rows[0])
    raw = raw[raw["URL"].str.startswith("http", na=False)].copy()
    raw["Event Date"]   = pd.to_datetime(raw["Event Date"],  errors="coerce")
    raw["Week Of"]      = pd.to_datetime(raw["Week Of"],     errors="coerce")
    raw["Sentiment"]    = raw["Sentiment"].str.lower().str.strip()
    raw["Impact"]       = raw["Impact"].str.strip()
    raw["Competitor"]   = raw["Competitor"].str.strip()
    raw["Category"]     = raw["Category"].str.strip()
    raw["Source Type"]  = raw["Source Type"].str.strip()
    raw["Platform"]     = (raw["Platform"].str.strip()
                           if "Platform" in raw.columns else "Unknown")
    raw["impact_order"] = raw["Impact"].map(IMPACT_ORDER).fillna(3)
    raw["momentum_pts"] = raw["Impact"].map(IMPACT_WEIGHTS).fillna(0)
    return raw


@st.cache_data(ttl=300)
def load_metrics() -> pd.DataFrame:
    try:
        sh   = get_client().open_by_key(SHEET_ID)
        rows = sh.worksheet("Metrics").get_all_values()
        if len(rows) < 2:
            return pd.DataFrame()
        mdf = pd.DataFrame(rows[1:], columns=rows[0])
        mdf["Date"] = pd.to_datetime(mdf["Date"], errors="coerce")
        for col in ["GitHub Stars", "GitHub Forks", "PyPI Downloads (last month)", "Open Jobs"]:
            mdf[col] = pd.to_numeric(mdf[col], errors="coerce")
        return mdf
    except Exception:
        return pd.DataFrame()


# ─── Helpers ──────────────────────────────────────────────────────────────────

def fmt(n):
    if pd.isna(n): return "—"
    n = int(n)
    if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
    if n >= 1_000:     return f"{n/1_000:.1f}K"
    return f"{n:,}"


def h(v): return html_lib.escape(str(v))


def age_label(ts):
    if pd.isna(ts): return ""
    days = (pd.Timestamp.now() - ts).days
    if days == 0:   return "today"
    if days == 1:   return "yesterday"
    if days < 7:    return f"{days}d ago"
    return ts.strftime("%b %d")


def section(title, subtitle=""):
    st.markdown(f"### {title}")
    if subtitle:
        st.markdown(
            f"<p style='color:#888;font-size:13px;margin-top:-10px;"
            f"margin-bottom:16px'>{subtitle}</p>",
            unsafe_allow_html=True,
        )


def stat_card(label, value, delta=None, delta_color="#27ae60"):
    delta_html = (
        f"<div style='font-size:12px;font-weight:600;color:{delta_color};"
        f"margin-top:2px'>{h(delta)}</div>"
        if delta else ""
    )
    st.markdown(
        f"<div style='background:#f8f9fa;border-radius:8px;padding:14px 16px;"
        f"border:1px solid #eee'>"
        f"<div style='font-size:11px;color:#888;font-weight:600;"
        f"text-transform:uppercase;letter-spacing:.5px'>{h(label)}</div>"
        f"<div style='font-size:24px;font-weight:800;color:#1a1a2e;margin-top:4px'>"
        f"{h(value)}</div>"
        f"{delta_html}</div>",
        unsafe_allow_html=True,
    )


def render_finding(row, show_comp=True, show_source=True):
    comp   = row["Competitor"]
    color  = ALL_COLORS.get(comp, "#888")
    ibg    = IMPACT_BG.get(row["Impact"], "#f5f5f5")
    ifg    = IMPACT_FG.get(row["Impact"], "#888")
    sc     = SENT_COLOR.get(row["Sentiment"], "#95a5a6")
    clbl   = f"<b style='color:{color}'>{h(comp)}</b>&ensp;" if show_comp else ""
    age    = age_label(row.get("Event Date"))
    age_h  = f"<span style='color:#bbb;font-size:11px;margin-left:8px'>{h(age)}</span>" if age else ""
    src    = (f"<a href='{row['URL']}' target='_blank' style='font-size:11px;color:#3498db;"
              f"font-weight:600;text-decoration:none;margin-top:6px;display:inline-block'>"
              f"View source &rarr;</a>") if show_source else ""
    st.markdown(
        f"<div style='border-left:3px solid {color};padding:10px 16px;margin-bottom:10px;"
        f"background:#fafafa;border-radius:0 6px 6px 0'>"
        f"<div style='margin-bottom:5px'>{clbl}"
        f"<span style='background:{ibg};color:{ifg};padding:2px 7px;border-radius:4px;"
        f"font-size:11px;font-weight:700'>{h(row['Impact'])}</span>&nbsp;"
        f"<span style='background:#eee;color:#555;padding:2px 7px;border-radius:4px;"
        f"font-size:11px;font-weight:600'>{h(row['Category'])}</span>&nbsp;"
        f"<span style='color:{sc};font-size:11px;font-weight:600'>{h(row['Sentiment'])}</span>"
        f"{age_h}</div>"
        f"<div style='font-size:14px;font-weight:700;color:#1a1a2e;margin-bottom:4px'>"
        f"{h(row['Title'])}</div>"
        f"<p style='margin:0 0 6px;color:#444;font-size:13px;line-height:1.6'>"
        f"{h(row['Summary'])}</p>"
        f"{src}</div>",
        unsafe_allow_html=True,
    )


def insufficient(n_have, n_need, label="This chart"):
    if n_have < n_need:
        st.caption(
            f"{label} needs {n_need}+ weeks of data — have {n_have} so far. "
            f"Fills in automatically each daily run."
        )
        return True
    return False


def trajectory(score, baseline):
    if baseline == 0:  return "new",       "#27ae60"
    r = score / baseline
    if r >= 1.3:       return "rising",    "#27ae60"
    if r <= 0.7:       return "declining", "#e74c3c"
    return "stable",   "#888"


# ─── Load ─────────────────────────────────────────────────────────────────────

with st.spinner("Loading..."):
    df  = load_findings()
    mdf = load_metrics()

if df.empty:
    st.warning("No findings yet. Run the agent first.")
    st.stop()

today       = pd.Timestamp.now().normalize()
week_start  = today - timedelta(days=today.weekday())
n_weeks     = df["Week Of"].nunique()
comp_df     = df[df["Competitor"].isin(COMPETITORS)]
all_weeks   = sorted(df["Week Of"].dropna().unique(), reverse=True)
wk_labels   = [w.strftime("Week of %b %d, %Y") for w in all_weeks]

weekly_momentum = (
    df[df["Competitor"].isin(COMPETITORS + [YOUR_COMPANY])]
    .groupby(["Week Of", "Competitor"])["momentum_pts"]
    .sum().reset_index(name="Score").sort_values("Week Of")
)


# ─── Sidebar ──────────────────────────────────────────────────────────────────

PAGES = [
    "Executive Summary",
    "1. Momentum",
    "2. Organic Share of Voice",
    "3. Where Is Nimble Absent?",
    "4. Category Heatmap",
    "5. Sales Battlecards",
    "6. Sentiment Trends",
    "7. Platform Breakdown",
    "8. Sales Talking Points",
    "9. Signal Velocity",
]

with st.sidebar:
    st.markdown(
        "<div style='background:#1a3a5c;padding:14px 16px;border-radius:8px;"
        "text-align:center;margin-bottom:18px'>"
        f"<p style='color:white;font-size:15px;font-weight:700;margin:0'>{YOUR_COMPANY} Intel</p>"
        "<p style='color:#aac4e0;font-size:11px;margin:4px 0 0'>"
        "Competitive Intelligence</p></div>",
        unsafe_allow_html=True,
    )
    page = st.radio("", PAGES, label_visibility="collapsed")
    st.markdown("---")
    if st.button("Refresh data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.markdown(
        f"<p style='color:#aaa;font-size:11px;text-align:center;margin-top:6px'>"
        f"{n_weeks} week{'s' if n_weeks != 1 else ''} of history"
        f"&nbsp;·&nbsp;{len(comp_df)} signals</p>",
        unsafe_allow_html=True,
    )

# Scroll to top whenever the page changes
if "prev_page" not in st.session_state:
    st.session_state.prev_page = page
if st.session_state.prev_page != page:
    st.session_state.prev_page = page
    components.html(
        f"""<script>
        /* page={page} */
        function scrollUp() {{
            var el = window.parent.document.querySelector('[data-testid="stMain"]');
            if (el) el.scrollTop = 0;
        }}
        scrollUp();
        setTimeout(scrollUp, 100);
        setTimeout(scrollUp, 300);
        </script>""",
        height=1,
    )


# ══════════════════════════════════════════════════════════════════════════════
# EXECUTIVE SUMMARY
# ══════════════════════════════════════════════════════════════════════════════

if page == "Executive Summary":
    st.markdown("## Competitive Landscape at a Glance")
    st.caption("The view a CMO opens Monday morning. Ranked by activity score — who generated the most notable events this week.")

    sel_lbl  = st.selectbox("", wk_labels, label_visibility="collapsed") if wk_labels else None
    sel_week = all_weeks[wk_labels.index(sel_lbl)] if sel_lbl else week_start
    sel_df   = df[df["Week Of"] == sel_week]
    prior_4  = df[(df["Week Of"] >= sel_week - timedelta(weeks=4)) &
                  (df["Week Of"] <  sel_week)]

    # Activity scores
    this_m = (sel_df[sel_df["Competitor"].isin(COMPETITORS)]
              .groupby("Competitor")["momentum_pts"].sum()
              .reset_index(name="Score"))
    avg_m  = (prior_4[prior_4["Competitor"].isin(COMPETITORS)]
              .groupby(["Week Of", "Competitor"])["momentum_pts"].sum()
              .groupby("Competitor").mean()
              .reset_index(name="Avg"))
    top_s  = (sel_df[sel_df["Competitor"].isin(COMPETITORS)]
              .sort_values("impact_order")
              .groupby("Competitor").first()
              .reset_index()[["Competitor","Title","Summary","Impact","Category","URL","Event Date"]])
    exec_df = (this_m
               .merge(avg_m,  on="Competitor", how="left")
               .merge(top_s,  on="Competitor", how="left")
               .fillna({"Avg": 0, "Score": 0})
               .sort_values("Score", ascending=False))

    # Nimble organic share header stats
    org_this  = df[(df["Week Of"] == sel_week) & (df["Source Type"] == "Organic")]
    org_prev  = df[(df["Week Of"] == sel_week - timedelta(weeks=1)) & (df["Source Type"] == "Organic")]
    n_share   = len(org_this[org_this["Competitor"] == YOUR_COMPANY]) / max(len(org_this), 1) * 100
    n_share_p = len(org_prev[org_prev["Competitor"] == YOUR_COMPANY]) / max(len(org_prev), 1) * 100
    sd        = n_share - n_share_p

    c1, c2, c3 = st.columns(3)
    with c1:
        leader = exec_df.iloc[0]["Competitor"] if not exec_df.empty else "—"
        stat_card("Activity Leader This Week", leader)
    with c2:
        stat_card(
            f"{YOUR_COMPANY} Organic Share of Voice",
            f"{n_share:.1f}%",
            delta=f"{sd:+.1f}pp vs last week" if n_share_p > 0 else "first week",
            delta_color="#27ae60" if sd >= 0 else "#e74c3c",
        )
    with c3:
        total_sig = len(sel_df[sel_df["Competitor"].isin(COMPETITORS)])
        stat_card("Competitor Signals This Week", total_sig)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    if exec_df.empty:
        st.info("No findings for this week.")
    else:
        for rank, (_, row) in enumerate(exec_df.iterrows(), 1):
            comp   = row["Competitor"]
            score  = int(row.get("Score", 0))
            avg    = float(row.get("Avg", 0))
            color  = COMPETITOR_COLORS.get(comp, "#888")
            traj, tc = trajectory(score, avg)
            impact = str(row.get("Impact", ""))
            ibg    = IMPACT_BG.get(impact, "#f5f5f5")
            ifg    = IMPACT_FG.get(impact, "#888")
            age    = age_label(row.get("Event Date"))
            url    = str(row.get("URL", "#"))
            traj_explain = {
                "rising":   "More activity than their recent average — something is happening.",
                "declining":"Less activity than their recent average — may be quiet period.",
                "stable":   "Activity in line with their recent average.",
                "new":      "First week of data — no baseline yet.",
            }.get(traj, "")

            st.markdown(
                f"<div style='border:1px solid #eee;border-left:4px solid {color};"
                f"border-radius:6px;padding:16px 20px;margin-bottom:12px;background:white'>"
                f"<div style='display:flex;justify-content:space-between;"
                f"align-items:flex-start;margin-bottom:10px'>"
                f"<div>"
                f"<span style='font-size:12px;color:#bbb;font-weight:600'>#{rank}</span>&ensp;"
                f"<span style='font-size:19px;font-weight:800;color:{color}'>{h(comp)}</span>"
                f"</div>"
                f"<div style='text-align:right'>"
                f"<div style='font-size:11px;color:#aaa;font-weight:600;"
                f"text-transform:uppercase;letter-spacing:.4px;margin-bottom:2px'>"
                f"Activity Score</div>"
                f"<div style='font-size:26px;font-weight:900;color:#1a1a2e;line-height:1'>"
                f"{score}</div>"
                f"<div style='font-size:11px;font-weight:700;color:{tc};margin-top:3px'>"
                f"{traj} &nbsp;<span style='color:#aaa;font-weight:400'>"
                f"{h(traj_explain)}</span></div>"
                f"</div></div>"
                f"<div style='margin-bottom:7px'>"
                f"<span style='background:{ibg};color:{ifg};padding:2px 7px;border-radius:4px;"
                f"font-size:11px;font-weight:700'>{h(impact)}</span>&nbsp;"
                f"<span style='background:#eee;color:#555;padding:2px 7px;border-radius:4px;"
                f"font-size:11px;font-weight:600'>{h(row.get('Category',''))}</span>"
                f"<span style='color:#bbb;font-size:11px;margin-left:8px'>{h(age)}</span>"
                f"</div>"
                f"<div style='font-size:14px;font-weight:700;color:#1a1a2e;margin-bottom:4px'>"
                f"{h(row.get('Title', 'No findings this week'))}</div>"
                f"<p style='margin:0 0 8px;color:#555;font-size:13px;line-height:1.5'>"
                f"{h(row.get('Summary',''))}</p>"
                f"<a href='{url}' target='_blank' style='font-size:12px;color:#3498db;"
                f"font-weight:600;text-decoration:none'>View source &rarr;</a>"
                f"</div>",
                unsafe_allow_html=True,
            )

    # Your company's own mentions this week
    nimble_this = sel_df[sel_df["Competitor"] == YOUR_COMPANY].sort_values("impact_order")
    if not nimble_this.empty:
        st.markdown("---")
        st.markdown(f"### {YOUR_COMPANY} in the market this week")
        st.caption(f"Mentions of {YOUR_COMPANY} captured in the same scan — how the market sees {YOUR_COMPANY} right now.")
        for _, row in nimble_this.iterrows():
            render_finding(row, show_comp=False)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 1 — MOMENTUM
# ══════════════════════════════════════════════════════════════════════════════

elif page == "1. Momentum":
    st.markdown("## Who Is Winning the Week?")
    st.caption(
        "Activity Score = how much notable competitor activity happened this week, weighted by importance. "
        "A High-impact event (funding round, major launch) scores 3. Medium scores 2. Low scores 1. "
        "Higher score = more significant competitive activity."
    )

    if wk_labels:
        sel_lbl  = st.selectbox("Week", wk_labels, label_visibility="visible")
        sel_week = all_weeks[wk_labels.index(sel_lbl)]
    else:
        sel_week = week_start
    prev_week = sel_week - timedelta(weeks=1)

    this_m = weekly_momentum[weekly_momentum["Week Of"] == sel_week].set_index("Competitor")["Score"]
    last_m = weekly_momentum[weekly_momentum["Week Of"] == prev_week].set_index("Competitor")["Score"]

    bar_rows = []
    for comp in COMPETITORS + [YOUR_COMPANY]:
        t = int(this_m.get(comp, 0))
        l = int(last_m.get(comp, 0))
        bar_rows += [
            {"Competitor": comp, "Score": t, "Period": "Selected week"},
            {"Competitor": comp, "Score": l, "Period": "Prior week"},
        ]
    bar_df = pd.DataFrame(bar_rows)

    fig = px.bar(
        bar_df, x="Competitor", y="Score", color="Period", barmode="group",
        color_discrete_map={"Selected week": "#1a3a5c", "Prior week": "#d5dde8"},
        custom_data=["Period"],
    )
    fig.update_traces(
        hovertemplate="<b>%{x}</b> — %{customdata[0]}<br>"
                      "Activity Score: <b>%{y}</b><br>"
                      "<i>Higher = more notable events</i><extra></extra>",
    )
    fig.update_layout(
        **CHART_BASE, height=300,
        legend=dict(orientation="h", y=1.02, x=1, xanchor="right", yanchor="bottom"),
        xaxis_title="", yaxis_title="Activity score",
        yaxis=dict(showgrid=True, gridcolor="#f0f0f0"),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Compact score row (no metric boxes)
    row_html = "<div style='display:flex;gap:8px;margin-bottom:24px;flex-wrap:wrap'>"
    for comp in COMPETITORS + [YOUR_COMPANY]:
        t = int(this_m.get(comp, 0))
        l = int(last_m.get(comp, 0))
        d = t - l
        color  = ALL_COLORS.get(comp, "#888")
        dc     = "#27ae60" if d > 0 else ("#e74c3c" if d < 0 else "#888")
        dstr   = f"+{d}" if d > 0 else (str(d) if d != 0 else "—")
        nimble_tag = "<div style='font-size:9px;color:#aaa;text-transform:uppercase;letter-spacing:.5px'>you</div>" if comp == YOUR_COMPANY else ""
        row_html += (
            f"<div style='flex:1;min-width:80px;background:white;border:1px solid #eee;"
            f"border-top:3px solid {color};border-radius:6px;padding:10px 12px;text-align:center'>"
            f"<div style='font-size:11px;font-weight:700;color:{color};margin-bottom:2px'>"
            f"{h(comp)}</div>"
            f"{nimble_tag}"
            f"<div style='font-size:22px;font-weight:900;color:#1a1a2e'>{t}</div>"
            f"<div style='font-size:11px;color:{dc};font-weight:600'>{dstr} vs prior</div>"
            f"</div>"
        )
    row_html += "</div>"
    st.markdown(row_html, unsafe_allow_html=True)

    # What drove this week's score
    st.markdown("---")
    section("What drove this week's scores?",
             "The findings behind each competitor's activity score. High-impact findings count most.")

    sel_df = df[df["Week Of"] == sel_week]
    for comp in sorted(COMPETITORS + [YOUR_COMPANY], key=lambda c: -int(this_m.get(c, 0))):
        score = int(this_m.get(comp, 0))
        if score == 0:
            continue
        color    = ALL_COLORS.get(comp, "#888")
        comp_fnd = sel_df[sel_df["Competitor"] == comp].sort_values("impact_order")
        with st.expander(f"{comp} — score {score} ({len(comp_fnd)} events)", expanded=False):
            for _, row in comp_fnd.iterrows():
                render_finding(row, show_comp=False)

    # Trend chart
    st.markdown("---")
    section("Activity score trend — all weeks")
    if not insufficient(n_weeks, 2, "Trend chart"):
        fig2 = px.line(
            weekly_momentum, x="Week Of", y="Score", color="Competitor",
            color_discrete_map=ALL_COLORS, markers=True,
        )
        fig2.update_traces(
            hovertemplate=(
                "<b>%{fullData.name}</b><br>Week of %{x|%b %d}<br>"
                "Activity Score: <b>%{y}</b><br>"
                "<i>High-impact events count 3x, Medium 2x, Low 1x</i><extra></extra>"
            ),
            line=dict(width=2), marker=dict(size=6),
        )
        fig2.update_layout(
            **CHART_BASE, height=300,
            legend=dict(orientation="h", y=1.02, x=1, xanchor="right", yanchor="bottom"),
            xaxis_title="", yaxis_title="Activity score",
        )
        fig2.update_xaxes(tickformat="%b %d", showgrid=False)
        fig2.update_yaxes(showgrid=True, gridcolor="#f0f0f0")
        st.plotly_chart(fig2, use_container_width=True)
        st.caption(
            "How to read this: A spike means something significant happened — a launch, funding round, "
            "or PR push. A flat line means business as usual. A declining line means they've gone quiet."
        )


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2 — ORGANIC SHARE OF VOICE
# ══════════════════════════════════════════════════════════════════════════════

elif page == "2. Organic Share of Voice":
    st.markdown("## Organic Share of Voice")
    st.caption(
        "**What this measures:** What percentage of all organic (third-party) competitor coverage "
        "belongs to each company — including Nimble. "
        "Self-promoted content (blogs, press releases, official social posts) is excluded. "
        "**Why it matters:** Organic share of voice is the single best leading indicator of future mindshare. "
        "A rising share means the market is talking about you without being prompted."
    )

    organic = df[
        (df["Source Type"] == "Organic") &
        (df["Competitor"].isin(COMPETITORS + [YOUR_COMPANY]))
    ]
    weekly_org = (
        organic.groupby(["Week Of", "Competitor"]).size().reset_index(name="Count")
    )
    wk_tot = weekly_org.groupby("Week Of")["Count"].transform("sum")
    weekly_org["Share"] = (weekly_org["Count"] / wk_tot * 100).round(2)

    # Your company SOV callout
    nim_sov = weekly_org[weekly_org["Competitor"] == YOUR_COMPANY].sort_values("Week Of")
    latest_week_total = int(weekly_org[weekly_org["Week Of"] == all_weeks[0]]["Count"].sum()) if all_weeks else 0
    n_players = weekly_org[weekly_org["Week Of"] == all_weeks[0]]["Competitor"].nunique() if all_weeks else 0
    sparse = latest_week_total < 10

    if len(nim_sov) >= 1:
        cur_s = nim_sov.iloc[-1]["Share"]
        cur_count = int(nim_sov.iloc[-1]["Count"])
        # Rank Nimble vs all competitors this week
        this_week_snap = weekly_org[weekly_org["Week Of"] == all_weeks[0]].sort_values("Share", ascending=False) if all_weeks else pd.DataFrame()
        rank_list = list(this_week_snap["Competitor"])
        rank = rank_list.index(YOUR_COMPANY) + 1 if YOUR_COMPANY in rank_list else "—"

        if len(nim_sov) >= 2:
            prev_s = nim_sov.iloc[-2]["Share"]
            delta  = cur_s - prev_s
            dc = "#27ae60" if delta > 0 else ("#e74c3c" if delta < 0 else "#888")
            dir_text = f"{delta:+.1f} pp vs last week"
            note = (f"Gaining organic share — more third-party conversation about {YOUR_COMPANY}." if delta > 0
                    else (f"Losing organic share — competitors capturing more unprompted coverage." if delta < 0
                          else "Share unchanged week-over-week."))
        else:
            dc, dir_text, note = "#888", "first week of data", "Baseline established — trends appear next week."

        sparse_note = f" <i style='color:#aaa;font-size:11px'>(only {latest_week_total} total organic signals this week — percentages shift significantly with each new signal)</i>" if sparse else ""
        st.markdown(
            f"<div style='background:white;border:1px solid #eee;border-left:3px solid {dc};"
            f"border-radius:0 6px 6px 0;padding:12px 16px;margin-bottom:16px'>"
            f"<span style='font-size:14px;font-weight:700;color:{dc}'>"
            f"{YOUR_COMPANY}: {cur_s:.1f}% organic share (#{rank} of {n_players}) — {dir_text}.</span>"
            f"<span style='color:#555;font-size:13px;margin-left:8px'>{note}</span>"
            f"{sparse_note}</div>",
            unsafe_allow_html=True,
        )

    # Area trend
    if not insufficient(n_weeks, 2, "Share of voice trend"):
        fig = px.area(
            weekly_org.sort_values("Week Of"),
            x="Week Of", y="Share", color="Competitor",
            color_discrete_map=ALL_COLORS,
        )
        fig.update_traces(
            hovertemplate=(
                "<b>%{fullData.name}</b><br>Week of %{x|%b %d}<br>"
                "<b>%{y:.1f}%</b> of all organic signals<br>"
                "<i>Organic only — excludes company's own content</i><extra></extra>"
            ),
        )
        fig.update_layout(
            **CHART_BASE, height=320,
            yaxis=dict(ticksuffix="%", showgrid=True, gridcolor="#f0f0f0"),
            xaxis_title="", yaxis_title="% of organic signals",
            legend=dict(orientation="h", y=1.02, x=1, xanchor="right", yanchor="bottom"),
        )
        fig.update_xaxes(tickformat="%b %d", showgrid=False)
        st.plotly_chart(fig, use_container_width=True)

    # Plotly horizontal bar snapshot (fixes white bar, adds hover)
    st.markdown("---")
    section("Current snapshot",
            "Hover each bar to see the exact count and share. "
            "A competitor with no organic bar has zero third-party coverage this period.")
    if all_weeks:
        snap = weekly_org[weekly_org["Week Of"] == all_weeks[0]].sort_values("Share", ascending=True)
        # Ensure all competitors + Nimble appear even at 0%
        all_comps = COMPETITORS + [YOUR_COMPANY]
        missing   = [c for c in all_comps if c not in snap["Competitor"].values]
        if missing:
            pad = pd.DataFrame({"Week Of": all_weeks[0], "Competitor": missing, "Count": 0, "Share": 0.0})
            snap = pd.concat([snap, pad], ignore_index=True).sort_values("Share", ascending=True)

        fig_snap = px.bar(
            snap, x="Share", y="Competitor", orientation="h",
            color="Competitor", color_discrete_map=ALL_COLORS,
            text="Share",
        )
        fig_snap.update_traces(
            texttemplate="%{text:.1f}%",
            textposition="outside",
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Organic share: <b>%{x:.1f}%</b><br>"
                "Organic signals: %{customdata[0]}<br>"
                "<i>% of all organic coverage this week</i><extra></extra>"
            ),
            customdata=snap[["Count"]].values,
            showlegend=False,
        )
        fig_snap.update_layout(
            **CHART_BASE, height=max(200, len(snap) * 42),
            xaxis=dict(range=[0, snap["Share"].max() * 1.3 + 5],
                       ticksuffix="%", showgrid=True, gridcolor="#f0f0f0"),
            yaxis_title="",
        )
        st.plotly_chart(fig_snap, use_container_width=True)

    # Show organic findings for selected competitor
    st.markdown("---")
    section("Explore organic findings")
    comp_filter = st.selectbox("Competitor", ["All"] + COMPETITORS + [YOUR_COMPANY])
    org_findings = organic.sort_values(["Week Of", "impact_order"], ascending=[False, True])
    if comp_filter != "All":
        org_findings = org_findings[org_findings["Competitor"] == comp_filter]
    for _, row in org_findings.head(20).iterrows():
        render_finding(row, show_comp=(comp_filter == "All"))


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3 — WHERE IS NIMBLE ABSENT?
# ══════════════════════════════════════════════════════════════════════════════

elif page == "3. Where Is Nimble Absent?":
    st.markdown(f"## Where Is {YOUR_COMPANY} Absent From Conversations?")
    st.caption(
        "Every row below is an organic developer or community conversation where a competitor appears "
        "but Nimble does not. These are the conversations that shape tool decisions in 30–90 days. "
        "The gap number = how many of their conversations Nimble is not part of."
    )

    comm_org = df[
        (df["Source Type"] == "Organic") &
        (df["Category"].isin(["Community", "Customer Feedback"]))
    ]
    comp_comm = (
        comm_org[comm_org["Competitor"].isin(COMPETITORS)]
        .groupby(["Week Of", "Competitor"]).size().reset_index(name="Comp")
    )
    nim_comm = (
        comm_org[comm_org["Competitor"] == YOUR_COMPANY]
        .groupby("Week Of").size().reset_index(name=YOUR_COMPANY)
    )
    gap_df = comp_comm.merge(nim_comm, on="Week Of", how="left").fillna(0)
    gap_df[YOUR_COMPANY] = gap_df[YOUR_COMPANY].astype(int)
    gap_df["Gap"]    = (gap_df["Comp"].astype(int) - gap_df[YOUR_COMPANY]).clip(lower=0)

    if gap_df.empty:
        st.info("No community organic signals yet. This populates as the agent runs.")
    else:
        # This week snapshot
        if all_weeks:
            latest_gap = gap_df[gap_df["Week Of"] == all_weeks[0]].sort_values("Gap", ascending=False)
            total_gap  = int(latest_gap["Gap"].sum())
            total_comp_mentions = int(latest_gap["Comp"].sum())
            total_nim_mentions  = int(latest_gap[YOUR_COMPANY].sum())

            if total_gap > 0:
                dc_gap, msg_gap = "#e74c3c", (
                    f"Competitors have <b>{total_comp_mentions}</b> organic community mentions vs "
                    f"<b>{total_nim_mentions}</b> for {YOUR_COMPANY} — a gap of <b>{total_gap}</b> conversations "
                    f"this week. These are the discussions shaping developer tool decisions in 30–90 days."
                )
            else:
                dc_gap, msg_gap = "#27ae60", (
                    f"{YOUR_COMPANY}'s community volume ({total_nim_mentions} mentions) matches or exceeds "
                    f"competitors ({total_comp_mentions} total) this week. "
                    f"Still review the conversations below — volume parity doesn't mean the same audiences."
                )
            st.markdown(
                f"<div style='background:white;border:1px solid #eee;"
                f"border-left:3px solid {dc_gap};border-radius:0 6px 6px 0;"
                f"padding:12px 16px;margin-bottom:16px;font-size:13px'>{msg_gap}</div>",
                unsafe_allow_html=True,
            )

            rows_html = ""
            for _, r in latest_gap.iterrows():
                gap_v = int(r["Gap"])
                if gap_v <= 0: continue
                comp  = r["Competitor"]
                color = COMPETITOR_COLORS.get(comp, "#888")
                rows_html += (
                    f"<tr style='border-bottom:1px solid #f0f0f0'>"
                    f"<td style='padding:8px 12px;font-weight:700;color:{color}'>{h(comp)}</td>"
                    f"<td style='padding:8px 12px;text-align:center'>{int(r['Comp'])}</td>"
                    f"<td style='padding:8px 12px;text-align:center'>{int(r[YOUR_COMPANY])}</td>"
                    f"<td style='padding:8px 12px;text-align:center;font-weight:700;"
                    f"color:#e74c3c'>{gap_v}</td>"
                    f"</tr>"
                )
            if rows_html:
                st.markdown(
                    f"<table style='width:100%;border-collapse:collapse;font-size:13px;margin-bottom:20px'>"
                    f"<thead><tr style='background:#f8f8f8'>"
                    f"<th style='padding:8px 12px;text-align:left'>Competitor</th>"
                    f"<th style='padding:8px 12px;text-align:center' title='Organic community signals for this competitor this week'>Their Organic Community Signals</th>"
                    f"<th style='padding:8px 12px;text-align:center' title='Organic community signals for {YOUR_COMPANY} this week'>{YOUR_COMPANY} Organic Community Signals</th>"
                    f"<th style='padding:8px 12px;text-align:center'>Gap (conversations Nimble is missing)</th>"
                    f"</tr></thead><tbody>{rows_html}</tbody></table>",
                    unsafe_allow_html=True,
                )

        # Competitor community conversations this week
        st.markdown("---")
        section("Competitor community conversations this week",
                "Organic developer and community posts where competitors appear. "
                "These are the conversations shaping tool preferences — "
                "the gap table above shows how many more of these competitors have vs Nimble.")

        missing = comm_org[comm_org["Competitor"].isin(COMPETITORS)].copy()
        if all_weeks:
            missing = missing[missing["Week Of"] == all_weeks[0]]
        missing = missing.sort_values(["impact_order", "Competitor"])

        comp_f = st.selectbox("Filter by competitor", ["All"] + COMPETITORS)
        if comp_f != "All":
            missing = missing[missing["Competitor"] == comp_f]

        if missing.empty:
            st.caption("No community signals this week.")
        else:
            for _, row in missing.head(25).iterrows():
                render_finding(row)

        # Simple week-over-week gap comparison (table, not confusing chart)
        if n_weeks >= 2:
            st.markdown("---")
            section("Is the gap getting better or worse?",
                    "Comparing total community conversations Nimble is absent from, week by week.")
            gap_summary = (
                gap_df.groupby("Week Of")["Gap"].sum().reset_index()
                .sort_values("Week Of", ascending=False).head(8)
            )
            gap_summary["Week Of"] = gap_summary["Week Of"].dt.strftime("Week of %b %d")
            gap_summary.columns = ["Week", f"Conversations {YOUR_COMPANY} Missed"]
            st.dataframe(
                gap_summary,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Week": st.column_config.TextColumn(width="medium"),
                    f"Conversations {YOUR_COMPANY} Missed": st.column_config.NumberColumn(
                        width="medium",
                        help=f"Total organic community signals from competitors where {YOUR_COMPANY} had no equivalent signal",
                    ),
                },
            )


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 4 — CATEGORY HEATMAP
# ══════════════════════════════════════════════════════════════════════════════

elif page == "4. Category Heatmap":
    st.markdown("## Category Activity Heatmap")
    st.caption(
        "Darker = more signals in that category over the last 4 weeks. "
        "**How to read it:** Heavy Funding activity = raising or spending capital. "
        "Heavy Hiring = scaling sales or engineering. Heavy Product Launch = shipping new features. "
        "Heavy Community = investing in developer mindshare. Click a cell's category to see the actual findings."
    )

    heatmap_src = df[df["Competitor"].isin(COMPETITORS + [YOUR_COMPANY])]
    recent = heatmap_src[heatmap_src["Week Of"] >= today - timedelta(weeks=4)]
    older  = heatmap_src[
        (heatmap_src["Week Of"] >= today - timedelta(weeks=8)) &
        (heatmap_src["Week Of"] <  today - timedelta(weeks=2))
    ]

    heat_r = recent.groupby(["Competitor", "Category"]).size().unstack(fill_value=0)
    heat_o = older.groupby(["Competitor",  "Category"]).size().unstack(fill_value=0)
    all_cats = sorted(set(list(heat_r.columns) + list(heat_o.columns)))
    heat_r = heat_r.reindex(index=COMPETITORS + [YOUR_COMPANY], columns=all_cats, fill_value=0)
    heat_o = heat_o.reindex(index=COMPETITORS + [YOUR_COMPANY], columns=all_cats, fill_value=0)

    if heat_r.empty:
        st.info("Not enough category data yet.")
    else:
        fig = go.Figure(go.Heatmap(
            z=heat_r.values.tolist(),
            x=list(heat_r.columns),
            y=list(heat_r.index),
            colorscale="Blues",
            text=heat_r.values.tolist(),
            texttemplate="%{text}",
            hovertemplate=(
                "<b>%{y}</b> · %{x}<br>"
                "<b>%{z} signals</b> in the last 4 weeks<br>"
                "<i>Select the category below to read the findings</i><extra></extra>"
            ),
            showscale=True,
        ))
        fig.update_layout(
            **CHART_BASE, height=300,
            xaxis=dict(side="top", tickfont=dict(size=12)),
            yaxis=dict(autorange="reversed"),
        )
        st.plotly_chart(fig, use_container_width=True)

        # Drill-down: select competitor + category to see findings
        st.markdown("---")
        section("Explore findings by competitor and category")
        dc1, dc2 = st.columns(2)
        with dc1:
            hm_comp = st.selectbox("Competitor", ["All"] + COMPETITORS + [YOUR_COMPANY], key="hm_comp")
        with dc2:
            hm_cat  = st.selectbox("Category",   ["All"] + all_cats,    key="hm_cat")

        hm_findings = recent.copy()
        if hm_comp != "All":
            hm_findings = hm_findings[hm_findings["Competitor"] == hm_comp]
        if hm_cat != "All":
            hm_findings = hm_findings[hm_findings["Category"] == hm_cat]
        hm_findings = hm_findings.sort_values(["Week Of", "impact_order"], ascending=[False, True])

        if hm_findings.empty:
            st.caption("No findings for this selection.")
        else:
            st.caption(f"{len(hm_findings)} finding(s)")
            for _, row in hm_findings.iterrows():
                render_finding(row, show_comp=(hm_comp == "All"))

        # Positioning shifts — only shown with actual findings as evidence
        shifts = [
            (comp, cat, int(heat_r.loc[comp, cat]))
            for comp in COMPETITORS + [YOUR_COMPANY]
            for cat in heat_r.columns
            if heat_r.loc[comp, cat] > 0 and heat_o.loc[comp, cat] == 0
        ]
        if shifts:
            st.markdown("---")
            section("New category entries — positioning shifts",
                    "These competitors entered a category they had zero signals in over the prior 2 weeks. "
                    "A sudden entry usually signals a strategic pivot or new go-to-market push.")
            for comp, cat, count in sorted(shifts, key=lambda x: -x[2]):
                color = COMPETITOR_COLORS.get(comp, "#888")
                shift_finds = recent[
                    (recent["Competitor"] == comp) & (recent["Category"] == cat)
                ].sort_values("impact_order")
                with st.expander(
                    f"{comp} entered {cat} — {count} new signal(s) (was zero in prior 2 weeks)",
                    expanded=False,
                ):
                    st.caption(
                        f"This is a positioning shift. {comp} had no {cat} signals in weeks 3–6 "
                        f"but now has {count}. Here are the signals that triggered this detection:"
                    )
                    for _, row in shift_finds.iterrows():
                        render_finding(row, show_comp=False)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 5 — SALES BATTLECARDS
# ══════════════════════════════════════════════════════════════════════════════

elif page == "5. Sales Battlecards":
    st.markdown("## Live Competitive Weaknesses")
    st.caption(
        "Signals where a competitor has **Negative sentiment + High or Medium impact**. "
        "These are the strongest talking points for competitive deals — "
        "use the 'Use this when...' prompt to know exactly when to bring it up. "
        "All findings link to the original source so you can share it with a prospect."
    )

    scope = st.radio("Scope", ["This week only", "All time (full history)"], horizontal=True)
    sel_lbl = st.selectbox("Week", wk_labels, label_visibility="visible",
                            disabled=(scope == "All time (full history)")) if wk_labels else None
    sel_week = all_weeks[wk_labels.index(sel_lbl)] if sel_lbl else week_start

    if scope == "This week only":
        bcd_src = df[df["Week Of"] == sel_week]
    else:
        bcd_src = df

    bcd = bcd_src[
        (bcd_src["Sentiment"] == "negative") &
        (bcd_src["Impact"].isin(["High", "Medium"])) &
        (bcd_src["Competitor"].isin(COMPETITORS))
    ].sort_values(["Competitor", "impact_order", "Week Of"], ascending=[True, True, False])

    if bcd.empty:
        st.info("No negative High/Medium signals for this selection. Try 'All time' scope or select a prior week.")
    else:
        for comp in COMPETITORS:
            cbc = bcd[bcd["Competitor"] == comp]
            if cbc.empty: continue
            color = COMPETITOR_COLORS[comp]
            st.markdown(
                f"<p style='font-size:17px;font-weight:800;color:{color};"
                f"margin:20px 0 8px'>{h(comp)}</p>",
                unsafe_allow_html=True,
            )
            for _, row in cbc.iterrows():
                ibg = IMPACT_BG.get(row["Impact"], "#f5f5f5")
                ifg = IMPACT_FG.get(row["Impact"], "#888")
                uw  = h(USE_WHEN.get(row["Category"], "this competitor comes up in a sales conversation"))
                age = age_label(row.get("Event Date"))

                st.markdown(
                    f"<div style='border:1px solid #e8e8e8;border-left:3px solid #e74c3c;"
                    f"border-radius:6px;padding:14px 18px;margin-bottom:12px;background:white'>"
                    f"<div style='display:flex;justify-content:space-between;align-items:center;"
                    f"margin-bottom:8px'>"
                    f"<div>"
                    f"<span style='background:{ibg};color:{ifg};padding:2px 7px;border-radius:4px;"
                    f"font-size:11px;font-weight:700'>{h(row['Impact'])}</span>&nbsp;"
                    f"<span style='background:#eee;color:#555;padding:2px 7px;border-radius:4px;"
                    f"font-size:11px;font-weight:600'>{h(row['Category'])}</span>"
                    f"</div>"
                    f"<span style='color:#bbb;font-size:11px'>{h(age)}</span>"
                    f"</div>"
                    f"<div style='font-size:14px;font-weight:700;color:#1a1a2e;margin-bottom:5px'>"
                    f"{h(row['Title'])}</div>"
                    f"<p style='margin:0 0 10px;color:#444;font-size:13px;line-height:1.6'>"
                    f"{h(row['Summary'])}</p>"
                    f"<div style='display:flex;justify-content:space-between;align-items:flex-start;"
                    f"gap:12px'>"
                    f"<div style='background:#fff8f0;border-radius:4px;padding:8px 12px;flex:1'>"
                    f"<div style='font-size:11px;font-weight:700;color:#e67e22;"
                    f"text-transform:uppercase;letter-spacing:.5px;margin-bottom:3px'>"
                    f"Use this when...</div>"
                    f"<p style='margin:0;font-size:13px;color:#333'>{uw}</p>"
                    f"</div>"
                    f"<a href='{row['URL']}' target='_blank' style='display:inline-block;"
                    f"background:#1a3a5c;color:white;padding:8px 14px;border-radius:6px;"
                    f"font-size:12px;font-weight:700;text-decoration:none;white-space:nowrap'>"
                    f"View source &rarr;</a>"
                    f"</div></div>",
                    unsafe_allow_html=True,
                )


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 6 — SENTIMENT TRENDS
# ══════════════════════════════════════════════════════════════════════════════

elif page == "6. Sentiment Trends":
    st.markdown("## Sentiment Trend Per Competitor")
    st.caption(
        "**% of signals that are negative**, week over week. "
        "A rising negative rate means a competitor is either struggling, getting scrutinized by the community, "
        "or generating controversy. A rate above 30% is a significant sales opportunity — "
        "prospects who ask about this vendor will hear mixed things."
    )

    sent_wk  = comp_df.groupby(["Week Of", "Competitor", "Sentiment"]).size().reset_index(name="Count")
    sent_tot = sent_wk.groupby(["Week Of", "Competitor"])["Count"].transform("sum")
    sent_wk["Ratio"]  = (sent_wk["Count"] / sent_tot * 100).round(1)
    neg_ratio = sent_wk[sent_wk["Sentiment"] == "negative"].copy()

    if not insufficient(n_weeks, 2, "Sentiment trend"):
        fig = px.line(
            neg_ratio, x="Week Of", y="Ratio", color="Competitor",
            color_discrete_map=COMPETITOR_COLORS, markers=True,
        )
        fig.add_hline(
            y=30, line_dash="dash", line_color="#e74c3c", line_width=1,
            annotation_text="30% — significant sales opportunity",
            annotation_position="bottom right",
            annotation_font=dict(color="#e74c3c", size=11),
        )
        fig.update_traces(
            hovertemplate=(
                "<b>%{fullData.name}</b><br>Week of %{x|%b %d}<br>"
                "<b>%{y:.1f}%</b> of signals are negative<br>"
                "<i>Above 30% = strong sales opportunity</i><extra></extra>"
            ),
            line=dict(width=2), marker=dict(size=6),
        )
        fig.update_layout(
            **CHART_BASE, height=320,
            legend=dict(orientation="h", y=1.02, x=1, xanchor="right", yanchor="bottom"),
            xaxis_title="", yaxis_title="% negative",
            yaxis=dict(ticksuffix="%", showgrid=True, gridcolor="#f0f0f0"),
        )
        fig.update_xaxes(tickformat="%b %d", showgrid=False)
        st.plotly_chart(fig, use_container_width=True)

    # All-time sentiment mix
    st.markdown("---")
    section("All-time sentiment mix",
            "Stacked bar showing the overall tone of coverage per competitor. "
            "High negative share = market is scrutinizing them. Low positive share = low organic praise.")
    sent_all = comp_df.groupby(["Competitor", "Sentiment"]).size().reset_index(name="Count")
    fig2 = px.bar(
        sent_all, x="Competitor", y="Count", color="Sentiment",
        color_discrete_map={"positive": "#27ae60", "negative": "#e74c3c", "neutral": "#ccc"},
        barmode="stack",
    )
    fig2.update_traces(
        hovertemplate="<b>%{x}</b> · %{fullData.name}<br>%{y} signals<extra></extra>"
    )
    fig2.update_layout(
        **CHART_BASE, height=300,
        legend=dict(orientation="h", y=1.02, x=1, xanchor="right", yanchor="bottom"),
        xaxis_title="", yaxis_title="Total signals",
        yaxis=dict(showgrid=True, gridcolor="#f0f0f0"),
    )
    st.plotly_chart(fig2, use_container_width=True)

    # Drill-down: show what's driving negative sentiment
    st.markdown("---")
    section("What is driving negative sentiment?",
            "Select a competitor to see their negative findings — these are the specifics behind the chart.")
    sent_comp = st.selectbox("Competitor", COMPETITORS, key="sent_comp")
    neg_finds = comp_df[
        (comp_df["Competitor"] == sent_comp) &
        (comp_df["Sentiment"] == "negative")
    ].sort_values(["Week Of", "impact_order"], ascending=[False, True])
    st.caption(f"{len(neg_finds)} negative findings for {sent_comp} (all time, most recent first)")
    if neg_finds.empty:
        st.info(f"No negative signals found for {sent_comp}.")
    else:
        for _, row in neg_finds.head(15).iterrows():
            render_finding(row, show_comp=False)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 7 — PLATFORM BREAKDOWN
# ══════════════════════════════════════════════════════════════════════════════

elif page == "7. Platform Breakdown":
    st.markdown("## Platform Signal Breakdown")
    st.caption(
        "Where each competitor's signals originate, split by Organic vs. Self-Promoted. "
        "**Organic signals on Reddit, HackerNews, or developer blogs are the most valuable** — "
        "they reflect genuine community pull. A competitor generating mostly self-promoted signals "
        "is pushing hard but not being amplified. "
        "Select a competitor and platform below the chart to read the actual articles."
    )

    pb_comp = st.selectbox("Competitor", ["All"] + COMPETITORS)
    plat_df = comp_df.copy() if pb_comp == "All" else comp_df[comp_df["Competitor"] == pb_comp]
    plat_df = plat_df.copy()
    plat_df["Platform"] = plat_df["Platform"].fillna("Unknown").replace("", "Unknown")

    plat_counts = plat_df.groupby(["Platform", "Source Type"]).size().reset_index(name="Count")
    plat_order  = (plat_counts.groupby("Platform")["Count"].sum()
                   .sort_values(ascending=True).index.tolist())

    fig = px.bar(
        plat_counts, y="Platform", x="Count", color="Source Type",
        orientation="h", barmode="stack",
        color_discrete_map={"Organic": "#27ae60", "Self-Promoted": "#bbb"},
        category_orders={"Platform": plat_order},
    )
    fig.update_traces(
        hovertemplate=(
            "<b>%{y}</b> · %{fullData.name}<br>"
            "<b>%{x} signals</b><br>"
            "<i>Organic = third-party coverage, Self-Promoted = their own content</i><extra></extra>"
        )
    )
    fig.update_layout(
        **CHART_BASE,
        height=max(280, len(plat_counts["Platform"].unique()) * 34),
        legend=dict(orientation="h", y=1.02, x=1, xanchor="right", yanchor="bottom"),
        xaxis=dict(showgrid=True, gridcolor="#f0f0f0"),
        xaxis_title="Signals", yaxis_title="",
    )
    st.plotly_chart(fig, use_container_width=True)

    # Organic % summary (only for All view)
    if pb_comp == "All":
        org_pct = comp_df.groupby(["Competitor", "Source Type"]).size().unstack(fill_value=0)
        if "Organic" in org_pct.columns:
            tot = org_pct.sum(axis=1)
            org_pct["Pct"] = (org_pct["Organic"] / tot.replace(0, 1) * 100).round(1)
            org_pct = org_pct.reset_index().sort_values("Pct", ascending=True)
            fig2 = px.bar(
                org_pct, x="Pct", y="Competitor", orientation="h",
                color="Competitor", color_discrete_map=COMPETITOR_COLORS,
            )
            fig2.update_traces(
                hovertemplate=(
                    "<b>%{y}</b><br>%{x:.1f}% of all signals are organic<br>"
                    "<i>Higher = more genuine community pull</i><extra></extra>"
                ),
                showlegend=False,
            )
            fig2.add_vline(x=50, line_dash="dash", line_color="#ccc",
                           annotation_text="50% threshold",
                           annotation_position="top right")
            fig2.update_layout(
                **CHART_BASE, height=240,
                xaxis=dict(range=[0,100], ticksuffix="%",
                           showgrid=True, gridcolor="#f0f0f0"),
                yaxis_title="",
            )
            st.plotly_chart(fig2, use_container_width=True)

    # Drill-down: click to read findings from a specific platform
    st.markdown("---")
    section("Read the actual articles")
    pc1, pc2, pc3 = st.columns(3)
    with pc1:
        all_platforms = sorted(plat_df["Platform"].dropna().unique())
        plat_sel = st.selectbox("Platform", ["All"] + all_platforms)
    with pc2:
        src_sel = st.radio("Source type", ["All", "Organic", "Self-Promoted"], horizontal=True)
    with pc3:
        comp_sel2 = st.selectbox("Competitor", ["All"] + COMPETITORS, key="plat_comp2",
                                  disabled=(pb_comp != "All"))
        if pb_comp != "All":
            comp_sel2 = pb_comp

    drill = plat_df.copy()
    if plat_sel != "All":
        drill = drill[drill["Platform"] == plat_sel]
    if src_sel != "All":
        drill = drill[drill["Source Type"] == src_sel]
    if comp_sel2 != "All":
        drill = drill[drill["Competitor"] == comp_sel2]
    drill = drill.sort_values(["Week Of", "impact_order"], ascending=[False, True])

    st.caption(f"{len(drill)} finding(s) matching your filters")
    if drill.empty:
        st.info("No findings for this filter combination.")
    else:
        for _, row in drill.head(25).iterrows():
            render_finding(row, show_comp=(comp_sel2 == "All"))


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 8 — SALES TALKING POINTS
# ══════════════════════════════════════════════════════════════════════════════

elif page == "8. Sales Talking Points":
    st.markdown("## Sales Talking Points This Week")
    st.caption(
        f"For each competitor: their most significant move this week and exactly how to position {YOUR_COMPANY} against it. "
        "All findings are sourced — click 'View source' to read the full context or share with a prospect."
    )

    sel_lbl  = st.selectbox("Week", wk_labels, label_visibility="visible") if wk_labels else None
    sel_week = all_weeks[wk_labels.index(sel_lbl)] if sel_lbl else week_start
    sel_df   = df[df["Week Of"] == sel_week]

    for comp in COMPETITORS:
        color   = COMPETITOR_COLORS[comp]
        comp_wk = sel_df[sel_df["Competitor"] == comp].sort_values("impact_order")

        if comp_wk.empty:
            st.markdown(
                f"<div style='border:1px solid #eee;border-left:4px solid {color};"
                f"border-radius:6px;padding:12px 18px;margin-bottom:12px;"
                f"background:white;opacity:.5'>"
                f"<b style='color:{color}'>{h(comp)}</b> — no signals this week.</div>",
                unsafe_allow_html=True,
            )
            continue

        top     = comp_wk.iloc[0]
        cat     = str(top["Category"])
        sent    = str(top["Sentiment"])
        impact  = str(top["Impact"])
        ibg     = IMPACT_BG.get(impact, "#f5f5f5")
        ifg     = IMPACT_FG.get(impact, "#888")
        play    = h(
            HOW_TO_POSITION.get((cat, sent), DEFAULT_POSITION).replace("[competitor]", comp)
        )
        age     = age_label(top.get("Event Date"))

        st.markdown(
            f"<div style='border:1px solid #eee;border-left:4px solid {color};"
            f"border-radius:6px;padding:16px 20px;margin-bottom:16px;background:white'>"
            f"<div style='display:flex;justify-content:space-between;align-items:center;"
            f"margin-bottom:10px'>"
            f"<div>"
            f"<b style='font-size:17px;color:{color}'>{h(comp)}</b>&ensp;"
            f"<span style='background:{ibg};color:{ifg};padding:2px 7px;border-radius:4px;"
            f"font-size:11px;font-weight:700'>{h(impact)}</span>&nbsp;"
            f"<span style='background:#eee;color:#555;padding:2px 7px;border-radius:4px;"
            f"font-size:11px;font-weight:600'>{h(cat)}</span>"
            f"</div>"
            f"<span style='color:#bbb;font-size:11px'>{h(age)}</span>"
            f"</div>"
            f"<div style='font-size:11px;font-weight:700;color:#888;text-transform:uppercase;"
            f"letter-spacing:.5px;margin-bottom:4px'>Biggest move</div>"
            f"<div style='font-size:14px;font-weight:700;color:#1a1a2e;margin-bottom:5px'>"
            f"{h(top['Title'])}</div>"
            f"<p style='margin:0 0 12px;color:#444;font-size:13px;line-height:1.6'>"
            f"{h(top['Summary'])}</p>"
            f"<a href='{top['URL']}' target='_blank' style='font-size:12px;color:#3498db;"
            f"font-weight:600;text-decoration:none;display:block;margin-bottom:12px'>"
            f"View source &rarr;</a>"
            f"<div style='background:#f0f6ff;border-radius:4px;padding:10px 14px'>"
            f"<div style='font-size:11px;font-weight:700;color:#2471a3;"
            f"text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px'>"
            f"How to position {YOUR_COMPANY}</div>"
            f"<p style='margin:0;font-size:13px;color:#222;line-height:1.6'>{play}</p>"
            f"</div></div>",
            unsafe_allow_html=True,
        )

        # Show remaining findings this week as expandable
        remaining = comp_wk.iloc[1:]
        if not remaining.empty:
            with st.expander(f"+ {len(remaining)} more {comp} finding(s) this week"):
                for _, row in remaining.iterrows():
                    render_finding(row, show_comp=False)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 9 — SIGNAL VELOCITY
# ══════════════════════════════════════════════════════════════════════════════

elif page == "9. Signal Velocity":
    st.markdown("## Signal Velocity")
    st.caption(
        "How many signals each competitor generates per week. "
        "A spike (star marker) means a competitor's volume exceeded **1.5× their rolling 4-week average** — "
        "this almost always means a product launch, funding announcement, or coordinated PR push. "
        "Expand a spike below the chart to see exactly what caused it."
    )

    velocity = (
        comp_df.groupby(["Week Of", "Competitor"]).size().reset_index(name="Count")
        .sort_values("Week Of")
    )

    spike_frames = []
    for comp in COMPETITORS:
        cv = velocity[velocity["Competitor"] == comp].copy().sort_values("Week Of")
        cv["Rolling"] = cv["Count"].shift(1).rolling(4, min_periods=1).mean()
        cv["Spike"]   = (cv["Count"] >= cv["Rolling"] * 1.5) & (cv["Rolling"] > 0)
        spike_frames.append(cv)
    vel_full = pd.concat(spike_frames) if spike_frames else velocity.assign(Spike=False, Rolling=0.0)
    spikes   = vel_full[vel_full.get("Spike", pd.Series(False, index=vel_full.index)) == True]

    if not insufficient(n_weeks, 2, "Velocity chart"):
        fig = px.line(
            velocity, x="Week Of", y="Count", color="Competitor",
            color_discrete_map=COMPETITOR_COLORS, markers=True,
        )
        if not spikes.empty:
            for _, sp in spikes.iterrows():
                comp  = sp["Competitor"]
                color = COMPETITOR_COLORS.get(comp, "#888")
                fig.add_trace(go.Scatter(
                    x=[sp["Week Of"]], y=[sp["Count"]],
                    mode="markers",
                    marker=dict(size=16, color=color, symbol="star",
                                line=dict(color="white", width=1.5)),
                    hovertemplate=(
                        f"<b>{h(comp)} — SPIKE DETECTED</b><br>"
                        f"{int(sp['Count'])} signals vs {sp['Rolling']:.1f} avg (1.5x threshold)<br>"
                        f"<i>Expand the spike panel below to see what caused it</i><extra></extra>"
                    ),
                    showlegend=False,
                ))
        fig.update_traces(
            selector=dict(mode="lines+markers"),
            hovertemplate=(
                "<b>%{fullData.name}</b><br>Week of %{x|%b %d}<br>"
                "<b>%{y} signals</b><extra></extra>"
            ),
            line=dict(width=2), marker=dict(size=6),
        )
        fig.update_layout(
            **CHART_BASE, height=320,
            legend=dict(orientation="h", y=1.02, x=1, xanchor="right", yanchor="bottom"),
            xaxis_title="", yaxis_title="Signals per week",
        )
        fig.update_xaxes(tickformat="%b %d", showgrid=False)
        fig.update_yaxes(showgrid=True, gridcolor="#f0f0f0")
        st.plotly_chart(fig, use_container_width=True)

    # Spike detail — expandable with actual findings
    if not spikes.empty:
        st.markdown("---")
        section("Spike investigations",
                "What caused each volume spike? Expand to read the findings from that week.")
        for _, sp in spikes.sort_values("Week Of", ascending=False).iterrows():
            comp  = sp["Competitor"]
            color = COMPETITOR_COLORS.get(comp, "#888")
            avg   = float(sp.get("Rolling", 0))
            spike_week = sp["Week Of"]
            spike_finds = comp_df[
                (comp_df["Competitor"] == comp) &
                (comp_df["Week Of"] == spike_week)
            ].sort_values("impact_order")

            with st.expander(
                f"{comp} — {int(sp['Count'])} signals week of "
                f"{spike_week.strftime('%b %d')} (avg was {avg:.1f})",
                expanded=False,
            ):
                st.caption(
                    f"Volume was {int(sp['Count']/avg*100-100) if avg > 0 else '∞'}% above average. "
                    f"Here are the {len(spike_finds)} findings from that week:"
                )
                for _, row in spike_finds.iterrows():
                    render_finding(row, show_comp=False)

    elif n_weeks >= 2:
        st.caption("No spikes detected — no competitor has exceeded 1.5× their rolling average yet.")
