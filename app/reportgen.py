"""Generate a standalone HTML report and archive it to disk when a report is closed."""
import os
import re
from datetime import datetime
from html import escape

FILES_DIR = os.path.join(os.path.dirname(__file__), "files_data")


def _safe(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", (s or "").strip()).strip("-") or "report"


def build_report_html(rec, eq) -> str:
    cell = "border:1px solid #cbd5e1;padding:5px 8px;vertical-align:top"
    head = "border:1px solid #cbd5e1;padding:5px 8px;font-weight:700;background:#f1f5f9"
    media_by_item: dict[str, list] = {}
    general = []
    for m in rec.media:
        if m.item_no:
            media_by_item.setdefault(m.item_no, []).append(m)
        else:
            general.append(m)

    rows = []
    cur_section = None
    for i in rec.results:
        if getattr(i, "section", None) and i.section != cur_section:
            cur_section = i.section
            rows.append(f'<tr><td style="{head}" colspan="5">{escape(i.section)}</td></tr>')
        rd = i.readings or []
        if rd:
            reading_cell = "<br>".join(f'{escape(x.get("code",""))}: {escape(x.get("value") or "—")}{(" " + escape(x.get("unit"))) if x.get("unit") else ""}' for x in rd)
        else:
            reading_cell = f'{escape(i.reading_value or "")}{" " + escape(i.reading_unit) if i.reading_value and i.reading_unit else ""}'
        rows.append(
            f'<tr><td style="{cell};text-align:center">{escape(i.item_no)}</td>'
            f'<td style="{cell}">{escape(i.description)}</td>'
            f'<td style="{cell};text-align:center;font-weight:700">{escape((i.status or "").upper())}</td>'
            f'<td style="{cell}">{reading_cell}</td>'
            f'<td style="{cell}">{escape(i.remarks or "")}</td></tr>'
        )
        photos = [m for m in media_by_item.get(i.item_no, []) if m.kind == "photo"]
        vids = [m for m in media_by_item.get(i.item_no, []) if m.kind == "video"]
        if photos or vids:
            imgs = "".join(f'<img src="{m.url}" style="width:120px;height:120px;object-fit:cover;border:1px solid #cbd5e1;border-radius:4px;margin:3px">' for m in photos)
            vtxt = f'<div style="font-size:11px;color:#64748b">{len(vids)} video(s) attached</div>' if vids else ""
            rows.append(f'<tr><td style="{cell}"></td><td style="{cell}" colspan="4"><div style="font-size:11px;color:#64748b;margin-bottom:4px">Attachments for item {escape(i.item_no)}:</div>{imgs}{vtxt}</td></tr>')

    def sign(label, name, sig, note, at):
        at_s = at.strftime("%d %b %Y") if at else ""
        return (f'<td style="{cell};width:50%"><div style="font-size:11px;color:#64748b">{label}</div>'
                f'<div style="font-weight:700;min-height:18px">{escape(name or "—")}{" · <i>" + escape(sig) + "</i>" if sig else ""}</div>'
                f'{("<div style=font-size:11px;color:#475569>Note: " + escape(note) + "</div>") if note else ""}'
                f'{("<div style=font-size:11px;color:#64748b>" + at_s + "</div>") if at_s else ""}</td>')

    gen_imgs = "".join(f'<img src="{m.url}" style="width:140px;height:140px;object-fit:cover;border:1px solid #cbd5e1;border-radius:4px;margin:3px">' for m in general if m.kind == "photo")
    gen_block = f'<div style="margin-top:14px"><div style="font-weight:700;margin-bottom:6px">General photos</div>{gen_imgs}</div>' if gen_imgs else ""

    perf = rec.performed_at.strftime("%d %b %Y") if rec.performed_at else ""
    sheet = f"""<div style="background:#fff;color:#0b1220;padding:22px;font-size:13px;font-family:Arial,Helvetica,sans-serif">
    <div style="text-align:center;font-weight:800;font-size:15px;margin-bottom:4px">{escape((eq.type or 'EQUIPMENT').upper())} PREVENTIVE MAINTENANCE CHECKLIST</div>
    <div style="text-align:center;color:#64748b;font-size:12px;margin-bottom:14px">{escape(rec.frequency)} · {escape(rec.site_name or '')}</div>
    <table style="width:100%;border-collapse:collapse;margin-bottom:12px">
      <tr><td style="{head};width:22%">Equipment Tag</td><td style="{cell}">{escape(eq.tag or '')}</td><td style="{head};width:18%">Site</td><td style="{cell}">{escape(rec.site_name or '')}</td></tr>
      <tr><td style="{head}">Equipment</td><td style="{cell}">{escape(eq.name or '')}</td><td style="{head}">Location</td><td style="{cell}">{escape(eq.location or '')}</td></tr>
      <tr><td style="{head}">Frequency</td><td style="{cell}">{escape(rec.frequency)}</td><td style="{head}">Date</td><td style="{cell}">{perf}</td></tr>
      <tr><td style="{head}">Serviced by</td><td style="{cell}">{escape(rec.serviced_by or '')}</td><td style="{head}">Overall</td><td style="{cell}">{escape(rec.overall_status)}</td></tr>
    </table>
    <table style="width:100%;border-collapse:collapse">
      <thead><tr><th style="{head};width:8%">Sr.No</th><th style="{head};text-align:left">Description</th><th style="{head};width:11%">Status</th><th style="{head};width:18%">Reading / Value</th><th style="{head};width:24%">Remarks</th></tr></thead>
      <tbody>{''.join(rows)}</tbody></table>
    {('<div style="margin-top:10px;font-size:12px"><b>Note:</b> ' + escape(rec.note) + '</div>') if rec.note else ''}
    {gen_block}
    <div style="font-weight:700;margin-top:16px;margin-bottom:6px">Completion &amp; Verification</div>
    <table style="width:100%;border-collapse:collapse">
      <tr>{sign('Checked by (Technician)', rec.checked_by, rec.signature, None, rec.performed_at)}{sign('Manager approval', rec.manager_name, rec.manager_signature, rec.manager_note, rec.manager_signed_at)}</tr>
      <tr>{sign('Customer sign-off', rec.customer_name, rec.customer_signature, rec.customer_note, rec.customer_signed_at)}<td style="{cell}"><div style="font-size:11px;color:#64748b">Status</div><div style="font-weight:700">{escape(rec.approval)}</div></td></tr>
    </table>
    <div style="text-align:right;color:#94a3b8;font-size:10px;margin-top:10px">Flowea CMMS · archived {datetime.now().strftime('%d %b %Y %H:%M')}</div>
    </div>"""
    return f'<!DOCTYPE html><html><head><meta charset="utf-8"><title>{escape(eq.tag or "report")} {escape(rec.frequency)}</title></head><body style="margin:18px">{sheet}</body></html>'


def archive_report(rec, eq) -> str:
    """Write the closed report to app/files_data and return the relative path."""
    os.makedirs(FILES_DIR, exist_ok=True)
    now = datetime.now()
    stamp = now.strftime("%d-%m-%Y_%H-%M-%S")
    name = f"{stamp}_{_safe(rec.site_name)}_{_safe(eq.tag)}_{_safe(rec.frequency)}.html"
    with open(os.path.join(FILES_DIR, name), "w", encoding="utf-8") as f:
        f.write(build_report_html(rec, eq))
    return f"files_data/{name}"
