"""Command line interface: legoize PICTURE -o OUTDIR"""

from __future__ import annotations

import argparse
import sys

from .build import build_mosaic
from .palette import COLORS
from .tiling import bill_of_materials


def _int_list(text):
    return tuple(int(t) for t in text.split(",") if t.strip())


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="legoize",
        description="Turn a picture into a buildable LEGO plate mosaic with "
                    "step-by-step building instructions.")
    ap.add_argument("image", nargs="?", help="the picture to convert")
    ap.add_argument("-o", "--out", default="mosaic_out",
                    help="output folder (default: mosaic_out)")
    ap.add_argument("--list-colors", action="store_true",
                    help="print the LEGO colours this program can use and exit")

    g = ap.add_argument_group("size")
    g.add_argument("--width", type=int, default=48,
                   help="width in studs (default 48, one LEGO baseplate)")
    g.add_argument("--height", type=int, default=None,
                   help="height in studs (default: keep the aspect ratio)")
    g.add_argument("--panel", type=int, default=48,
                   help="split into panels of this many studs, 0 for one "
                        "piece (default 48 = a 48x48 baseplate)")
    g.add_argument("--crop", choices=("fit", "crop", "pad"), default="fit",
                   help="fit the whole picture, centre-crop, or letterbox")

    g = ap.add_argument_group("colour")
    g.add_argument("--palette", default="common",
                   help="'common' (default), 'extended', 'grayscale', 'bw', "
                        "or a comma separated list of colour names/ids")
    g.add_argument("--exclude-colors", type=_int_list, default=(),
                   help="colour ids to leave out, e.g. 0,15")
    g.add_argument("--dither", choices=("auto", "floyd", "none"), default="auto",
                   help="auto (default): dither only large photo mosaics")
    g.add_argument("--dither-strength", type=float, default=0.4)
    g.add_argument("--lightness-weight", type=float, default=1.5,
                   help="how hard to work at matching brightness; higher "
                        "keeps shapes crisper (default 1.5)")
    g.add_argument("--chroma-weight", type=float, default=1.0,
                   help="raise above 1 if a limited palette comes out "
                        "over-saturated")
    g.add_argument("--despeckle", type=float, default=6.0,
                   help="clean up lone anti-aliasing studs, in dE2000 units; "
                        "0 turns it off, higher is more aggressive "
                        "(default 6)")
    g.add_argument("--brightness", type=float, default=1.0)
    g.add_argument("--contrast", type=float, default=1.0)
    g.add_argument("--saturation", type=float, default=1.0)
    g.add_argument("--sharpen", type=float, default=0.0)

    g = ap.add_argument_group("parts")
    g.add_argument("--max-part", type=int, default=8,
                   help="longest plate edge the tiler may use (default 8)")
    g.add_argument("--max-plate-width", type=int, default=2,
                   help="shortest plate edge; 2 keeps to cheap 1xN/2xN plates")
    g.add_argument("--only-1x1", action="store_true",
                   help="classic mosaic: every stud is its own 1x1 plate")

    g = ap.add_argument_group("instructions")
    g.add_argument("--step-rows", type=int, default=2,
                   help="stud rows finished per step (default 2)")
    g.add_argument("--max-parts-per-step", type=int, default=14)
    g.add_argument("--stud-px", type=int, default=22,
                   help="pixels per stud in the preview render")
    g.add_argument("--step-stud-px", type=int, default=11,
                   help="pixels per stud in the step pictures")
    g.add_argument("--embed", choices=("auto", "yes", "no"), default="auto",
                   help="inline the step pictures so instructions.html is one "
                        "self-contained file (auto: only for small builds)")
    g.add_argument("--title", default=None)
    g.add_argument("--no-compare", action="store_true",
                   help="skip the original-vs-mosaic comparison picture")
    g.add_argument("-q", "--quiet", action="store_true")

    args = ap.parse_args(argv)

    if args.list_colors:
        print("%-26s %5s  %-8s %s" % ("COLOUR", "ID", "HEX", "TIER"))
        for c in COLORS:
            print("%-26s %5d  %-8s %s" % (c.name, c.id, c.hex, c.tier))
        return 0

    if not args.image:
        ap.error("give me a picture to convert (or use --list-colors)")

    res = build_mosaic(
        args.image, args.out,
        width=args.width, height=args.height, panel=args.panel,
        palette=args.palette, dither=args.dither,
        dither_strength=args.dither_strength,
        lightness_weight=args.lightness_weight,
        chroma_weight=args.chroma_weight, despeckle=args.despeckle,
        max_part=args.max_part,
        max_plate_width=args.max_plate_width, only_1x1=args.only_1x1,
        crop=args.crop, brightness=args.brightness, contrast=args.contrast,
        saturation=args.saturation, sharpen=args.sharpen,
        step_rows=args.step_rows, max_parts_per_step=args.max_parts_per_step,
        embed=args.embed, stud_px=args.stud_px,
        step_stud_px=args.step_stud_px,
        title=args.title, exclude_colors=args.exclude_colors,
        compare=not args.no_compare, verbose=not args.quiet)

    if not args.quiet:
        print("\nTop parts:")
        for row in bill_of_materials(res.placements, res.palette)[:8]:
            print("  %4d x %-12s %s" % (row["quantity"], row["part"],
                                        row["color_name"]))
        print("\nOpen %s/instructions.html to start building." % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
