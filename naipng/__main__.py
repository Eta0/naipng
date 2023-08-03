"""
naipng
======

Scan PNG files for NovelAI JSON metadata.

License:
    Copyright (c) 2023 Eta

    This software is provided 'as-is', without any express or implied
    warranty. In no event will the authors be held liable for any damages
    arising from the use of this software.

    Permission is granted to anyone to use this software for any purpose,
    including commercial applications, and to alter it and redistribute it
    freely, subject to the following restrictions:

    1. The origin of this software must not be misrepresented; you must not
       claim that you wrote the original software. If you use this software
       in a product, an acknowledgment in the product documentation would be
       appreciated but is not required.
    2. Altered source versions must be plainly marked as such, and must not be
       misrepresented as being the original software.
    3. This notice may not be removed or altered from any source distribution.
"""
import argparse
import json
import sys
import textwrap

import naipng

from . import *


def main():
    parser = argparse.ArgumentParser(
        prog="naipng" if __name__ == "__main__" else None,
        description="read NovelAI data encoded in a PNG file",
        epilog=textwrap.dedent(r"""
            examples:
              (printing to stdout)
              %(prog)s image.png

              (saving to a file)
              %(prog)s image.png naidata.json

              (redirecting stdin and stdout)
              %(prog)s - < image.png > naidata.json

              (with external tools curl & jq)
              curl -fs https://files.catbox.moe/3b6dux.png | %(prog)s -c - | jq
        """),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "file",
        type=argparse.FileType(mode="rb"),
        help="PNG file to read, or - for stdin",
    )
    parser.add_argument(
        "outfile",
        nargs="?",
        type=argparse.FileType(mode="w"),
        default=sys.stdout,
        help="output file path, or - for stdout (default: -)",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        dest="quiet",
        action="store_true",
        help="don't print errors",
    )
    parser.add_argument(
        "-c",
        "--compact",
        dest="pretty_print",
        action="store_false",
        help="don't pretty-print decoded JSON",
    )
    parser.set_defaults(reader=naipng.read)
    parser.add_argument(
        "-t",
        "--text",
        dest="reader",
        action="store_const",
        const=naipng.read_text_gen,
        help="only check for text generation data",
    )
    parser.add_argument(
        "-i",
        "--image",
        dest="reader",
        action="store_const",
        const=naipng.read_image_gen,
        help="only check for image generation data",
    )
    args = parser.parse_args()
    try:
        nai_data = args.reader(args.file)
    except (InvalidPNGError, NAIDataError) as e:
        if not args.quiet:
            print("Error:", e, file=sys.stderr)
        sys.exit(100)
    if nai_data is None:
        if not args.quiet:
            print("No NovelAI data was found in the file.", file=sys.stderr)
        sys.exit(101)
    else:
        output = json.dumps(nai_data, indent=2 if args.pretty_print else None)

        try:
            args.outfile.write(output)
            args.outfile.flush()
        except OSError:
            if not args.quiet:
                print(
                    "Error: failed to write to output stream", file=sys.stderr
                )
            sys.exit(102)

    if args.file != sys.stdin.buffer:
        args.file.close()
    if args.outfile != sys.stdout:
        args.outfile.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(-1073741510 if sys.platform == "win32" else 2)
