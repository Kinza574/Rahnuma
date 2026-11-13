"""Shared result page (used by the wizard and Quick Diagnosis)."""

from datetime import date

import pandas as pd
import streamlit as st

from engine.consult import run_consultation, steps
from ui import components as c

FEE_WORD = {"low": "Low", "medium": "Medium", "high": "High", "unknown": "Not confirmed"}
STATUS_WORD = {"eligible": "Eligible", "conditional": "Conditional", "not_eligible": "Not eligible"}


def render(result, answers, kb, prefix, on_use=None, use_ask_if=True, name=None):
    report_head(name)
    if result.status == "insufficient":
        c.section("Insufficient data")
        st.write("The system needs a few more answers before it can give advice:")
        for m in result.missing:
            st.markdown(f"- {m}")
        c.muted("The engine stopped (HALT) because these inputs are essential. A blank field counts as missing; 0 counts as an answer.")
        with st.expander("How the system reached this"):
            for i, s in enumerate(steps(result, kb, True), 1):
                st.markdown(f"{i}. {s}")
        return

    technical = st.toggle("Show technical details", key=f"{prefix}_tech",
                          help="Shows rule IDs, certainty factors (CF) and the CF calculations.")
    st.markdown(f'<p class="rn-summary">{c.esc(result.summary)}</p>', unsafe_allow_html=True)
    profile_section(result, kb, technical)
    top_section(result, kb, technical)
    not_eligible_section(result, kb)
    universities_section(result, kb, prefix)
    outlook_section(result, kb)
    what_if(result, answers, kb, prefix, on_use, use_ask_if)
    c.section("How the system reached this")
    with st.expander(f"Show all {len(result.trace)} steps"):
        c.muted("Each line is one rule firing, in the order the engine fired them.")
        for i, s in enumerate(steps(result, kb, technical), 1):
            st.markdown(f"{i}. {s}")
    st.download_button("Download my result (TXT)", result_text(result, answers, kb), file_name="rahnuma_result.txt",
                       mime="text/plain", key=f"{prefix}_dl")


def report_head(name):
    who = name.strip() if name and name.strip() else "Student"
    today = date.today().strftime("%d %B %Y")
    st.markdown(f'<div class="rn-report-head"><div class="who">Counselling report — {c.esc(who)}</div>'
                f'<div class="meta">{today} · Rahnuma University Field Advisor</div></div>', unsafe_allow_html=True)


def profile_section(result, kb, technical):
    """The Diagnosis section: band, aptitudes, conditions met or missed, checks."""
    p = result.profile
    c.section("Diagnosis")
    rows = []
    band = p["band"] or "—"
    note = "" if p["marks_reliable"] in (None, 1.0) else " (estimate: Part-I marks)"
    rows.append(("Marks band", c.esc(f"{band}{note}")))
    if p["aptitudes"]:
        strong = [f"{n} — {w}" + (f" (CF {cf:.2f})" if technical else "") for n, cf, w in p["aptitudes"][:5]]
        rows.append(("Strongest aptitudes", "<br>".join(c.esc(x) for x in strong)))
    else:
        rows.append(("Strongest aptitudes", "None found from your answers"))
    if p["eligible"]:
        rows.append(("Requirements met", c.esc(", ".join(p["eligible"]))))
    if p["conditional"]:
        rows.append(("Conditions to meet", "<br>".join(c.esc(x) for x in p["conditional"])))
    if p["not_eligible"]:
        rows.append(("Not eligible", c.esc(", ".join(p["not_eligible"]))))
    if result.warnings:
        rows.append(("Checks", "<br>".join(c.esc(w) for w in result.warnings)))
    body = "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in rows)
    st.markdown(f'<dl class="rn-dl">{body}</dl>', unsafe_allow_html=True)


def top_section(result, kb, technical):
    """Recommended fields as a numbered list with confidence bars."""
    c.section("Recommended fields")
    for text in result.advice:
        c.warning_box(text)
    for i, t in enumerate(result.top, 1):
        f = kb.fields[t["id"]]
        cond = '<span class="rn-cond">Conditional</span>' if t["status"] == "conditional" else ""
        body = f'<div class="name">{c.esc(t["name"])}{cond}</div>'
        body += c.confidence_bar(t["cf"], t["label"] + (f" · CF {t['cf']:.3f}" if technical else ""))
        body += f'<div class="rn-muted">{c.esc(f["description"])} {f["years"]} years. Entry: {c.esc(f["required_test"])}.</div>'
        body += "<ul style='margin:0.4rem 0 0 0'>" + "".join(f"<li>{c.esc(r)}</li>" for r in t["reasons"][:3]) + "</ul>"
        for x in t["conditions"]:
            body += f"<div><b>Condition:</b> {c.esc(x)}</div>"
        if t["notes"]:
            body += f'<div class="rn-muted">Note: {c.esc("; ".join(t["notes"]))}</div>'
        if technical:
            body += f'<div class="rn-muted">Evidence from {c.esc(", ".join(t["rules"]))}</div>'
        st.markdown(f'<div class="rn-rec"><div class="num">{i}</div><div>{body}</div></div>', unsafe_allow_html=True)
    if result.action_plan:
        st.markdown("**Your action plan**")
        for step in result.action_plan:
            st.markdown(f"- {step}")


def not_eligible_section(result, kb):
    """Collapsed list of fields the student is not eligible for, with RC07 messages."""
    rows = [(fid, e) for fid, e in result.eligibility.items() if e["status"] == "not_eligible"]
    if not rows and not result.like_but_not:
        return
    with st.expander(f"Not eligible ({len(rows)} fields)"):
        for _, text in result.like_but_not:
            c.warning_box(text)
        for fid, e in rows:
            st.markdown(f"**{kb.fields[fid]['name']}** — not eligible because: {e['reasons'][0]}")


def universities_section(result, kb, prefix):
    """One filterable table of matching universities per recommended field."""
    if not result.top:
        return
    c.section("Matching universities")
    c.muted(f"University data as of {kb.universities['as_of']}. Rows marked 'Not yet verified' could not be checked on an official page.")
    for t in result.top:
        data = result.universities.get(t["id"])
        st.markdown(f"**{t['name']}**")
        if data is None:
            c.muted("No list for this field.")
            continue
        for n in data["notes"]:
            c.warning_box(n)
        if data["relaxed"]:
            words = " and ".join({"city": "city", "budget": "budget"}[x] for x in data["relaxed"])
            c.warning_box(f"Nothing matched every choice, so your {words} filter was relaxed.")
        items = data["items"]
        if not items:
            c.muted("No university in our list matches.")
            continue
        df = pd.DataFrame([{
            "University": it["name"], "City": it["city"], "Sector": it["sector"].title(),
            "Fee band": FEE_WORD.get(it["fee_band"], it["fee_band"]),
            "Hostel": "Not confirmed" if it["hostel"] == "unknown" else it["hostel"].title(), "Women only": "Yes" if it["women_only"] else "No",
            "Required test": f"{it['tests']} ({it['test_status']})",
            "Notes": "; ".join(it["tags"]), "Source": it["source_url"], "Verified": it["verified"],
        } for it in items])
        with st.popover("Filter this table"):
            cities = st.multiselect("City", sorted(df["City"].unique()), key=f"{prefix}_fc_{t['id']}")
            sectors = st.multiselect("Sector", sorted(df["Sector"].unique()), key=f"{prefix}_fs_{t['id']}")
            fees = st.multiselect("Fee band", sorted(df["Fee band"].unique()), key=f"{prefix}_ff_{t['id']}")
            verified = st.checkbox("Show only verified", key=f"{prefix}_fv_{t['id']}")
            women = st.checkbox("Women only", key=f"{prefix}_fw_{t['id']}")
            hostel = st.checkbox("Hostel available", key=f"{prefix}_fh_{t['id']}")
        view = df
        if cities:
            view = view[view["City"].isin(cities)]
        if sectors:
            view = view[view["Sector"].isin(sectors)]
        if fees:
            view = view[view["Fee band"].isin(fees)]
        if verified:
            view = view[view["Verified"]]
        if women:
            view = view[view["Women only"] == "Yes"]
        if hostel:
            view = view[view["Hostel"].isin(["Yes", "Limited"])]
        st.dataframe(view, hide_index=True, width="stretch",
                     column_config={"Source": st.column_config.LinkColumn("Source", display_text="Open"), "Verified": None})
        c.muted(f"{len(view)} of {len(df)} shown · {int(df['Verified'].sum())} verified")
        if data["removed"]:
            with st.expander(f"Removed by your filters ({len(data['removed'])})"):
                for name, why in data["removed"]:
                    st.markdown(f"- {name}: {why}")


def outlook_section(result, kb):
    """Job demand in Pakistan and abroad, with notes and sources."""
    if not result.job_outlook:
        return
    c.section("Job outlook")
    c.muted(f"Market data as of {kb.market['as_of']}. {kb.market.get('context', '')}")
    for fid, m in result.job_outlook.items():
        conf = m["confidence"]
        pk = m["pk"].title() + (" (estimate)" if conf["pk"] == "estimate" else "")
        ab = m["abroad"].title() + (" (estimate)" if conf["abroad"] == "estimate" else "")
        body = f"<p>Pakistan: <b>{c.esc(pk)}</b> · Abroad: <b>{c.esc(ab)}</b></p><p>{c.esc(m['note'])}</p>"
        for n in m["notes"]:
            body += f'<p class="rn-muted">{c.esc(n)}</p>'
        if m["sources"]:
            body += f'<p class="rn-muted">Sources: {c.esc("; ".join(m["sources"]))}</p>'
        st.markdown(f'<div style="margin-bottom:0.8rem"><b>{c.esc(kb.fields[fid]["name"])}</b>{body}</div>', unsafe_allow_html=True)


def result_text(result, answers, kb):
    """The report as plain text for the download button."""
    lines = ["Rahnuma — University Field Advisor", "", result.summary, ""]
    lines.append("Recommended fields:")
    for i, t in enumerate(result.top, 1):
        lines.append(f"{i}. {t['name']} — {t['label']}" + (" (conditional)" if t["status"] == "conditional" else ""))
        lines += [f"   - {r}" for r in t["reasons"]]
        lines += [f"   Condition: {x}" for x in t["conditions"]]
    if result.action_plan:
        lines += ["", "Action plan:"] + [f"- {x}" for x in result.action_plan]
    for t in result.top:
        u = result.universities.get(t["id"])
        if u:
            lines += ["", f"Universities for {t['name']}:"]
            lines += [f"- {it['name']} ({it['city']}, {it['sector']}, fee {FEE_WORD[it['fee_band']]})" for it in u["items"]]
    if result.warnings:
        lines += ["", "Warnings:"] + [f"- {w}" for w in result.warnings]
    lines += ["", "For guidance only — always confirm admission criteria with the university."]
    return "\n".join(lines)


# ---- What if? (decision support) ----

def _f(v):
    return None if v is None else float(v)


def what_if(result, answers, kb, prefix, on_use, use_ask_if):
    """Decision support: change a few answers and compare the result."""
    c.section("What if?")
    c.muted("Change a few answers and see what would change. Your saved answers stay the same unless you press 'Use these answers'.")
    k = f"{prefix}_wi"
    new = dict(answers)
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        new["inter_pct"] = c1.number_input("Inter %", 0.0, 100.0, float(answers.get("inter_pct") or 0), 0.5, key=f"{k}_inter")
        if answers.get("stream") == "pre_med" or not use_ask_if:
            v = c2.number_input("MDCAT %", 0.0, 100.0, value=_f(answers.get("mdcat_pct")), step=1.0, key=f"{k}_mdcat", placeholder="Not taken")
            new["mdcat_pct"], new["mdcat_pct_not_taken"] = v, v is None
        else:
            c2.caption("MDCAT applies to Pre-Medical students only.")
        if answers.get("I12") in ("yes", "notsure") or not use_ask_if:
            v = c3.number_input("LAT (out of 100)", 0.0, 100.0, value=_f(answers.get("lat_pct")), step=1.0, key=f"{k}_lat", placeholder="Not taken")
            new["lat_pct"], new["lat_pct_not_taken"] = v, v is None
        else:
            c3.caption("LAT is used only if you showed an interest in law.")
        d1, d2, d3 = st.columns(3)
        opts = {o["value"]: o["label"] for o in kb.options("budget")}
        new["budget"] = d1.selectbox("Budget", list(opts), index=list(opts).index(answers.get("budget") or "low"), format_func=opts.get, key=f"{k}_budget")
        sec = {o["value"]: o["label"] for o in kb.options("sector")}
        new["sector"] = d2.selectbox("Sector", list(sec), index=list(sec).index(answers.get("sector") or "either"), format_func=sec.get, key=f"{k}_sector")
        tri = ["yes", "no", "notsure"]
        new["relocate"] = d3.selectbox("Willing to move city?", tri, index=tri.index(answers.get("relocate") or "no"), format_func=c.TRI_LABEL.get, key=f"{k}_reloc")
        new["pref_cities"] = st.multiselect("Other cities", kb.cities, default=answers.get("pref_cities") or [], key=f"{k}_cities")
    after = run_consultation(new, kb, use_ask_if=use_ask_if)
    compare(result, after, kb)
    if on_use and st.button("Use these answers", key=f"{k}_use"):
        on_use(new)
        st.rerun()


def compare(before, after, kb):
    """Fields gained or lost, CF changes and university counts before and after."""
    if after.status != "ok":
        c.warning_box("With these answers the result would be 'Insufficient data'.")
        return
    b_top = [t["id"] for t in before.top]
    a_top = [t["id"] for t in after.top]
    gained = [kb.fields[f]["name"] for f in a_top if f not in b_top]
    lost = [kb.fields[f]["name"] for f in b_top if f not in a_top]
    if not gained and not lost and b_top == a_top:
        c.muted("Your recommended fields would stay the same.")
    if gained:
        st.markdown(f"**Fields gained:** {', '.join(gained)}")
    if lost:
        st.markdown(f"**Fields lost:** {', '.join(lost)}")
    rows = []
    for fid in dict.fromkeys(b_top + a_top):
        bs, as_ = before.wm.get(f"suit.{fid}"), after.wm.get(f"suit.{fid}")
        be, ae = before.eligibility.get(fid, {}), after.eligibility.get(fid, {})
        bu, au = before.universities.get(fid), after.universities.get(fid)
        rows.append({
            "Field": kb.fields[fid]["name"],
            "Status before → after": f"{STATUS_WORD.get(be.get('status'), '—')} → {STATUS_WORD.get(ae.get('status'), '—')}",
            "CF before → after": f"{bs.cf:.2f} → {as_.cf:.2f}" if bs and as_ else f"{bs.cf:.2f} → —" if bs else f"— → {as_.cf:.2f}" if as_ else "—",
            "Universities before → after": f"{len(bu['items']) if bu else 0} → {len(au['items']) if au else 0}",
        })
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
