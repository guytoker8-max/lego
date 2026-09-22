"""Write the step-by-step building instructions."""

from __future__ import annotations

import base64
import html
import io
import json
import os
from collections import Counter

from PIL import Image

from .render import render_mosaic
from .tiling import bill_of_materials, color_usage

STUD_MM = 8.0          # LEGO stud pitch
PLATE_MM = 3.2         # one plate is 3.2 mm thick


def physical_size(width_studs, height_studs):
    w_mm = width_studs * STUD_MM
    h_mm = height_studs * STUD_MM
    return {
        "width_mm": w_mm, "height_mm": h_mm,
        "width_cm": w_mm / 10.0, "height_cm": h_mm / 10.0,
        "width_in": w_mm / 25.4, "height_in": h_mm / 25.4,
        "text": "%.1f x %.1f cm (%.1f x %.1f in)" % (
            w_mm / 10.0, h_mm / 10.0, w_mm / 25.4, h_mm / 25.4),
    }


def step_lines(step, palette):
    """One printable line per distinct part in a step."""
    lines = []
    for p in step["placements"]:
        colour = palette[p.color_index]
        turn = (" " + p.orientation) if p.orientation else ""
        lines.append({
            "text": "Plate %s %s  -  %s at %s%s" % (
                p.size_name, colour.name, "part " + p.part.design_id,
                p.coords(), turn),
            "size": p.size_name,
            "design_id": p.part.design_id,
            "color_name": colour.name,
            "color_hex": colour.hex,
            "coords": p.coords(),
            "orientation": p.orientation,
        })
    return lines


def render_steps(indices, palette, placements, steps, outdir, *, stud_px=10,
                 write_files=True):
    """Render one picture per step; returns a list of PIL images."""
    if write_files:
        os.makedirs(os.path.join(outdir, "steps"), exist_ok=True)
    done_by_panel = {}
    images = []
    for step in steps:
        panel = step["panel"]
        done = done_by_panel.setdefault(panel.index, set())
        new = set(step["placements"])
        done |= new
        img = render_mosaic(
            indices, palette, placements, stud_px=stud_px, seams=True,
            highlight=new, full=set(done),
            region=(panel.col, panel.row, panel.w, panel.h), labels=True)
        images.append(img)
        if write_files:
            _compress(img).save(
                os.path.join(outdir, "steps", "step_%03d.png" % step["number"]),
                optimize=True)
    return images


def _compress(img, colors=96):
    """Flatten a rendered mosaic to an indexed PNG -- ~6x smaller, no visible
    loss, because the picture only ever holds a few dozen brick colours."""
    return img.convert("P", palette=Image.ADAPTIVE, colors=colors)


def _data_uri(img, kind="png"):
    buf = io.BytesIO()
    if kind == "jpeg":
        img.convert("RGB").save(buf, format="JPEG", quality=84, optimize=True)
        mime = "image/jpeg"
    else:
        _compress(img).save(buf, format="PNG", optimize=True)
        mime = "image/png"
    return "data:%s;base64,%s" % (mime, base64.b64encode(buf.getvalue()).decode())


def write_text(path, *, title, indices, palette, placements, steps, panels,
               size, stats):
    W = indices.shape[1]
    H = indices.shape[0]
    out = []
    out.append(title)
    out.append("=" * len(title))
    out.append("")
    out.append("Mosaic:      %d x %d studs  (%d studs total)" % (W, H, W * H))
    out.append("Finished:    %s" % size["text"])
    out.append("Parts:       %d plates in %d colours" % (
        len(placements), len({p.color_index for p in placements})))
    out.append("Panels:      %d" % len(panels))
    out.append("Steps:       %d" % len(steps))
    out.append("")
    out.append("Coordinates are (column,row), 1-indexed, counted from the")
    out.append("TOP-LEFT stud of the panel's baseplate.")
    out.append("")
    out.append("PARTS LIST")
    out.append("-" * 60)
    for row in bill_of_materials(placements, palette):
        out.append("  %4d x  %-12s %-24s  (part %s)" % (
            row["quantity"], row["part"], row["color_name"], row["design_id"]))
    out.append("")
    out.append("BUILDING STEPS")
    out.append("-" * 60)
    cur_panel = None
    for step in steps:
        panel = step["panel"]
        if panel.index != cur_panel:
            cur_panel = panel.index
            out.append("")
            out.append("## %s  (%d x %d studs, top-left of the whole picture "
                       "is at column %d, row %d)" % (
                           panel.label, panel.w, panel.h,
                           panel.col + 1, panel.row + 1))
        out.append("")
        out.append("Step %d" % step["number"])
        for line in step_lines(step, palette):
            out.append("   - " + line["text"])
    out.append("")
    with open(path, "w") as fh:
        fh.write("\n".join(out))


_CSS = """
:root{--ink:#16181d;--muted:#6b7280;--line:#e3e5ea;--bg:#ffffff;--soft:#f6f7f9;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;}
.wrap{max-width:980px;margin:0 auto;padding:40px 24px 80px}
h1{font-size:30px;margin:0 0 4px;letter-spacing:-.02em}
h2{font-size:20px;margin:44px 0 14px;padding-bottom:8px;border-bottom:1px solid var(--line)}
h3{font-size:15px;margin:0 0 10px;text-transform:uppercase;letter-spacing:.07em;color:var(--muted)}
.sub{color:var(--muted);margin:0 0 28px}
.hero{display:grid;grid-template-columns:1fr 1fr;gap:18px;align-items:start}
.hero img{width:100%;border-radius:10px;display:block}
.facts{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:26px 0}
.fact{background:var(--soft);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
.fact b{display:block;font-size:21px;letter-spacing:-.01em}
.fact span{color:var(--muted);font-size:12.5px;text-transform:uppercase;letter-spacing:.06em}
table{width:100%;border-collapse:collapse;font-size:14.5px}
th{text-align:left;font-size:12px;text-transform:uppercase;letter-spacing:.06em;
  color:var(--muted);border-bottom:1px solid var(--line);padding:8px 6px}
td{padding:7px 6px;border-bottom:1px solid var(--line)}
td.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.sw{display:inline-block;width:15px;height:15px;border-radius:4px;
  border:1px solid rgba(0,0,0,.28);vertical-align:-2px;margin-right:8px}
.step{display:grid;grid-template-columns:minmax(0,300px) 1fr;gap:22px;
  padding:20px 0;border-bottom:1px solid var(--line);page-break-inside:avoid}
.step img{width:100%;border-radius:8px;display:block;background:#222}
.step ul{margin:8px 0 0;padding-left:18px}
.step li{margin:3px 0;font-size:14.5px}
.num{display:inline-block;background:var(--ink);color:#fff;border-radius:6px;
  padding:2px 9px;font-weight:600;font-size:13.5px}
.panelhead{margin:40px 0 0;padding:14px 16px;background:var(--soft);
  border:1px solid var(--line);border-radius:10px}
.note{background:var(--soft);border:1px solid var(--line);border-radius:10px;
  padding:14px 16px;font-size:14.5px;color:#374151}
@media print{.step{break-inside:avoid}a{color:inherit}}
@media (max-width:720px){.hero,.step{grid-template-columns:1fr}}
"""


def write_html(path, *, title, indices, palette, placements, steps, panels,
               size, preview_img, compare_img, step_images, stats,
               source_name, settings, embed=True):
    """Write the booklet.

    ``embed`` inlines every picture so the .html is a single self-contained
    file you can mail to someone.  For very large mosaics that gets unwieldy,
    and the booklet links to the ``steps/`` folder beside it instead.
    """
    W, H = indices.shape[1], indices.shape[0]
    bom = bill_of_materials(placements, palette)
    usage = color_usage(indices, palette)
    e = html.escape

    p = []
    p.append("<!doctype html><html lang='en'><head><meta charset='utf-8'>")
    p.append("<meta name='viewport' content='width=device-width,initial-scale=1'>")
    p.append("<title>%s</title><style>%s</style></head><body><div class='wrap'>" %
             (e(title), _CSS))
    p.append("<h1>%s</h1>" % e(title))
    p.append("<p class='sub'>A LEGO&reg; plate mosaic of %s, with the exact "
             "part for every stud.</p>" % e(source_name))

    p.append("<div class='hero'>")
    if compare_img is not None:
        p.append("<figure style='margin:0;grid-column:1/-1'><img src='%s' alt='original next to the brick version'>"
                 "<figcaption class='sub' style='margin:8px 0 0;font-size:13.5px'>"
                 "Original photo (left) and the finished mosaic (right).</figcaption></figure>"
                 % _data_uri(compare_img, "jpeg"))
    else:
        p.append("<img src='%s' alt='finished mosaic'>" % _data_uri(preview_img))
    p.append("</div>")

    p.append("<div class='facts'>")
    for label, value in (
            ("Size in studs", "%d &times; %d" % (W, H)),
            ("Finished size", size["text"].split(" (")[0]),
            ("Plates", "%d" % len(placements)),
            ("Colours", "%d" % len(usage)),
            ("Baseplates", "%d" % len(panels)),
            ("Steps", "%d" % len(steps))):
        p.append("<div class='fact'><b>%s</b><span>%s</span></div>" % (value, label))
    p.append("</div>")

    p.append("<div class='note'><b>How to read these instructions.</b> "
             "Every step shows one panel. Plates you have already placed are "
             "in full colour, the new plates for this step are outlined in red, "
             "and the rest of the picture is ghosted so you can see where it is "
             "going. Coordinates are <b>(column, row)</b> counted from the "
             "<b>top-left stud</b> of that panel's baseplate, so "
             "<code>(5,3)-(8,3)</code> means a plate lying across columns 5 to 8 "
             "on row 3. Build on a %s baseplate, press every plate fully down, "
             "and work one row at a time.</div>"
             % (("%d&times;%d" % (panels[0].w, panels[0].h)) if panels else "flat"))

    p.append("<h2>Parts you need</h2>")
    p.append("<table><thead><tr><th>Qty</th><th>Plate</th><th>Colour</th>"
             "<th>LEGO part</th><th class='n'>Studs</th></tr></thead><tbody>")
    for row in bom:
        p.append("<tr><td class='n'>%d</td><td>%s</td>"
                 "<td><span class='sw' style='background:%s'></span>%s</td>"
                 "<td>%s</td><td class='n'>%d</td></tr>" % (
                     row["quantity"], e(row["part"]), row["color_hex"],
                     e(row["color_name"]), e(row["design_id"]), row["studs"]))
    p.append("</tbody></table>")
    p.append("<p class='sub' style='margin-top:10px'>%d plates in total. "
             "Colour numbers are BrickLink / Rebrickable ids: %s.</p>" % (
                 len(placements),
                 e(", ".join("%s = %d" % (u["color_name"], u["color_id"])
                             for u in usage))))

    p.append("<h2>Colours in the picture</h2>")
    p.append("<table><thead><tr><th>Colour</th><th class='n'>Studs</th>"
             "<th class='n'>Share</th></tr></thead><tbody>")
    for u in usage:
        p.append("<tr><td><span class='sw' style='background:%s'></span>%s "
                 "<span style='color:#6b7280'>(#%d)</span></td>"
                 "<td class='n'>%d</td><td class='n'>%.1f%%</td></tr>" % (
                     u["color_hex"], e(u["color_name"]), u["color_id"],
                     u["studs"], 100 * u["share"]))
    p.append("</tbody></table>")

    p.append("<h2>Building steps</h2>")
    cur = None
    for step, img in zip(steps, step_images):
        panel = step["panel"]
        if panel.index != cur:
            cur = panel.index
            if len(panels) > 1:
                p.append("<div class='panelhead'><b>%s</b> &mdash; %d &times; %d "
                         "studs. Its top-left stud is column %d, row %d of the "
                         "whole picture.</div>" % (
                             e(panel.label), panel.w, panel.h,
                             panel.col + 1, panel.row + 1))
        rows = step["placements"]
        band = "rows %d&ndash;%d" % (
            min(r.row for r in rows) + 1, max(r.row + r.h for r in rows))
        src = (_data_uri(img) if embed
               else "steps/step_%03d.png" % step["number"])
        p.append("<div class='step'><img src='%s' alt='step %d' loading='lazy'>"
                 "<div>" % (src, step["number"]))
        p.append("<h3><span class='num'>Step %d</span> &nbsp;%s</h3>" %
                 (step["number"], band))
        counts = Counter((l["size"], l["color_name"]) for l in step_lines(step, palette))
        p.append("<p class='sub' style='margin:0 0 6px;font-size:13.5px'>%s</p>" %
                 e(", ".join("%d x %s %s" % (n, s, c)
                             for (s, c), n in counts.most_common())))
        p.append("<ul>")
        for line in step_lines(step, palette):
            turn = (" &middot; lying %s" % line["orientation"]) if line["orientation"] else ""
            p.append("<li><span class='sw' style='background:%s'></span>"
                     "<b>Plate %s %s</b> at <code>%s</code>%s "
                     "<span style='color:#6b7280'>(part %s)</span></li>" % (
                         line["color_hex"], e(line["size"]), e(line["color_name"]),
                         e(line["coords"]), turn, e(line["design_id"])))
        p.append("</ul></div></div>")

    p.append("<h2>How this was made</h2>")
    p.append("<p class='sub'>%s</p>" % e(
        "Colours were matched with CIEDE2000 (the CIE perceptual colour "
        "difference) against real LEGO plate colours; the picture was then "
        "covered with the largest plates that fit. Settings: " +
        ", ".join("%s=%s" % (k, v) for k, v in sorted(settings.items()))))
    p.append("<p class='sub'>Average colour error %.1f &Delta;E2000 per stud, "
             "and %.1f for 3&times;3 stud averages &mdash; that second number is "
             "what your eye sees once you step back from the finished mosaic. "
             "A &Delta;E2000 below about 5 reads as the same colour to most "
             "people; a limited brick palette cannot always get there.</p>"
             % (stats["mean_delta_e"], stats["mean_delta_e_at_distance"]))
    p.append("<p class='sub' style='font-size:12.5px'>LEGO&reg; is a trademark "
             "of the LEGO Group, which does not sponsor or endorse this.</p>")
    p.append("</div></body></html>")

    with open(path, "w") as fh:
        fh.write("\n".join(p))


def write_json(path, *, title, indices, palette, placements, steps, panels,
               size, stats, settings):
    doc = {
        "title": title,
        "grid": {"width": int(indices.shape[1]), "height": int(indices.shape[0])},
        "physical_size": size,
        "settings": settings,
        "fidelity": stats,
        "palette": [{"id": c.id, "name": c.name, "hex": c.hex} for c in palette],
        "panels": [{"index": p.index, "col": p.col, "row": p.row,
                    "w": p.w, "h": p.h} for p in panels],
        "color_grid": [[int(palette[i].id) for i in row] for row in indices],
        "parts": bill_of_materials(placements, palette),
        "placements": [{"step": s["number"], "panel": p.panel,
                        "col": p.col + 1, "row": p.row + 1,
                        "w": p.w, "h": p.h, "plate": p.size_name,
                        "design_id": p.part.design_id,
                        "color_id": palette[p.color_index].id,
                        "color_name": palette[p.color_index].name}
                       for s in steps for p in s["placements"]],
    }
    with open(path, "w") as fh:
        json.dump(doc, fh, indent=1)


def write_csv(path, placements, palette):
    rows = bill_of_materials(placements, palette)
    with open(path, "w") as fh:
        fh.write("quantity,part,design_id,color_name,color_id,color_hex,studs\n")
        for r in rows:
            fh.write("%d,%s,%s,%s,%d,%s,%d\n" % (
                r["quantity"], r["part"], r["design_id"],
                r["color_name"].replace(",", ""), r["color_id"],
                r["color_hex"], r["studs"]))
