"""The whole pipeline: picture in, buildable mosaic + instructions out."""

from __future__ import annotations

import os
from dataclasses import dataclass

from . import instructions as instr
from . import palette as pal_mod
from . import parts as parts_mod
from . import quantize as quant
from . import render as rnd
from . import tiling


@dataclass
class MosaicResult:
    indices: object
    palette: tuple
    placements: list
    panels: list
    steps: list
    size: dict
    stats: dict
    outdir: str
    files: dict


def build_mosaic(image_path, outdir, *, width=48, height=None, panel=48,
                 palette="common", dither="auto", dither_strength=0.4,
                 lightness_weight=1.5, chroma_weight=1.0,
                 despeckle=6.0,
                 max_part=8, max_plate_width=2, only_1x1=False, crop="fit",
                 brightness=1.0, contrast=1.0, saturation=1.0, sharpen=0.0,
                 embed="auto", step_rows=2, max_parts_per_step=14, stud_px=22,
                 step_stud_px=11, title=None, exclude_colors=(),
                 compare=True, verbose=True):
    def log(msg):
        if verbose:
            print(msg, flush=True)

    os.makedirs(outdir, exist_ok=True)
    pal = pal_mod.get_palette(palette, exclude_ids=exclude_colors)
    log("Palette: %d LEGO colours (%s)" % (len(pal), palette))

    src = quant.load_and_fit(image_path, width, height, crop=crop,
                             brightness=brightness, contrast=contrast,
                             saturation=saturation, sharpen=sharpen)
    H, W = src.shape[:2]
    log("Grid: %d x %d studs (%d studs)" % (W, H, W * H))

    result = quant.quantize(src, pal, dither=dither,
                            dither_strength=dither_strength,
                            lightness_weight=lightness_weight,
                            chroma_weight=chroma_weight,
                            despeckle_threshold=despeckle)
    stats = quant.fidelity(result)
    log("Colour match: mean dE2000 %.2f per stud, %.2f seen from a distance "
        "(dither=%s)" % (stats["mean_delta_e"],
                         stats["mean_delta_e_at_distance"], result.dither))

    catalog = parts_mod.build_catalog(max_studs=max_part, only_1x1=only_1x1,
                                      max_width=max_plate_width)
    panels = tiling.split_panels(W, H, panel)
    placements = tiling.tile(result.indices, catalog, panels)
    steps = tiling.make_steps(placements, panels, band_rows=step_rows,
                              max_parts=max_parts_per_step)
    log("Tiled into %d plates across %d panel(s); %d build steps" % (
        len(placements), len(panels), len(steps)))

    size = instr.physical_size(W, H)
    files = {}

    preview = rnd.render_mosaic(result.indices, pal, stud_px=stud_px,
                                seams=False)
    preview.save(os.path.join(outdir, "preview.png"))
    files["preview"] = os.path.join(outdir, "preview.png")

    plan = rnd.render_mosaic(result.indices, pal, placements,
                             stud_px=max(12, stud_px - 4), seams=True,
                             labels=True)
    plan.save(os.path.join(outdir, "plan.png"))
    files["plan"] = os.path.join(outdir, "plan.png")

    compare_img = None
    if compare:
        # render at roughly the comparison size so the studs do not alias
        small = rnd.render_mosaic(result.indices, pal,
                                  stud_px=max(5, round(560 / max(W, H))),
                                  seams=False)
        compare_img = rnd.side_by_side(image_path, small)
        compare_img.save(os.path.join(outdir, "compare.png"))
        files["compare"] = os.path.join(outdir, "compare.png")

    usage = tiling.color_usage(result.indices, pal)
    rnd.color_swatches(usage).save(os.path.join(outdir, "colors.png"))
    files["colors"] = os.path.join(outdir, "colors.png")

    log("Rendering %d step pictures..." % len(steps))
    step_images = instr.render_steps(result.indices, pal, placements, steps,
                                     outdir, stud_px=step_stud_px)

    title = title or ("LEGO mosaic - %s" % os.path.basename(image_path))
    settings = {"studs": "%dx%d" % (W, H), "palette": palette,
                "dither": result.dither, "max_plate": max_part,
                "panel": panel or "none",
                "lightness_weight": lightness_weight,
                "chroma_weight": chroma_weight, "despeckle": despeckle}

    do_embed = (embed is True or embed == "yes"
                or (embed == "auto" and len(steps) <= 160))
    if not do_embed:
        log("%d steps: the booklet will link to the steps/ folder instead of "
            "inlining them" % len(steps))
    html_path = os.path.join(outdir, "instructions.html")
    instr.write_html(html_path, title=title, indices=result.indices,
                     palette=pal, placements=placements, steps=steps,
                     panels=panels, size=size, preview_img=preview,
                     compare_img=compare_img, step_images=step_images,
                     stats=stats, source_name=os.path.basename(image_path),
                     settings=settings, embed=do_embed)
    files["instructions_html"] = html_path

    txt_path = os.path.join(outdir, "instructions.txt")
    instr.write_text(txt_path, title=title, indices=result.indices,
                     palette=pal, placements=placements, steps=steps,
                     panels=panels, size=size, stats=stats)
    files["instructions_txt"] = txt_path

    csv_path = os.path.join(outdir, "parts.csv")
    instr.write_csv(csv_path, placements, pal)
    files["parts_csv"] = csv_path

    json_path = os.path.join(outdir, "mosaic.json")
    instr.write_json(json_path, title=title, indices=result.indices,
                     palette=pal, placements=placements, steps=steps,
                     panels=panels, size=size, stats=stats, settings=settings)
    files["mosaic_json"] = json_path

    log("Finished size: %s" % size["text"])
    log("Wrote %s" % outdir)

    return MosaicResult(indices=result.indices, palette=pal,
                        placements=placements, panels=panels, steps=steps,
                        size=size, stats=stats, outdir=outdir, files=files)
