# naipng ✒️🖼️
<a id="naipng"></a>

`naipng` is a Python library and command-line tool to read [NovelAI](https://novelai.net)
data encoded in PNG files (like in Lorebook cards and generated images), with no dependencies.

Also check out my website [pngmeta](https://pngmeta.glitch.me) for a browser-based tool for
[viewing](https://pngmeta.glitch.me) and [copying](https://pngmeta.glitch.me/transfer) PNG `tEXt` metadata.

# Table of Contents
<a id="table-of-contents"></a>

- [What Is This?](#what-is-this)
- [Installation](#installation)
- [Usage](#usage)
  - [Library](#library)
    - [Example](#naipngread-example)
    - [Error Handling](#error-handling)
  - [CLI](#cli)
    - [Help Text](#help-text)
    - [Examples](#examples)
- [Technical Background](#technical-background)
- [License](#license)

# What Is This?
<a id="what-is-this"></a>

User-made content for the web service [NovelAI](https://novelai.net) is often shared off-platform in the form of files.
These files take on multiple formats. Though most are simple JSON, some content can be shared embedded within PNGs,
which is more complicated to extract.

**Text Generation**: NovelAI allows exporting certain settings and objects related to text generation AI as PNG images
in place of regular JSON files, as a way of associating art with the descriptions of characters and places being shared.
These are commonly known as Lorebook cards.

**Image Generation**: NovelAI encodes image generation settings within generated PNGs, including parameters
such as `prompt`, `steps`, and so on, to make it easier to replicate and modify generated images.

Both domains use PNG metadata to encode this information, thus this tool allows the extraction of that metadata.

See more technical details in the [Technical Background](#technical-background) section.

# Installation
<a id="installation"></a>

`naipng` is available on PyPI, so it can be installed through `pip`:

```bash
python -m pip install naipng
```

Since `naipng` has no dependencies, you can also import or run it by simply adding the `naipng` directory
to your source tree.

# Usage
<a id="usage"></a>

`naipng` may be used either as a [library](#library) or a [command-line tool](#cli).

## Library
<a id="library"></a>

The primary function entrypoint provided by `naipng` is `naipng.read(file: bytes | BinaryIO)`.
This can be used to parse a PNG image for NovelAI metadata from either an open file or a `bytes` object in memory.

Two more specific variations of `naipng.read()` also exist:

- `naipng.read_text_gen(file: bytes | BinaryIO)` only returns text generation data
  - *E.g. Lorebooks*
- `naipng.read_image_gen(file: bytes | BinaryIO)` only returns image generation data
  - *E.g. image prompts*

### `naipng.read()` Example
<a id="naipngread-example"></a>

```python
import naipng

# Using a file-like object
with open("image.png", "rb") as file:
    decoded = naipng.read(file)

if decoded is None:
    # No NovelAI data found encoded in the image
    print("N/A")
else:
    # naipng.read() returns a dict object representing the first data found
    for k, v in decoded.items():
        print(k, "->", v)
```

Another example, using `bytes` as input to `naipng.read`:

```python
import naipng
import pathlib

data: bytes = pathlib.Path("image.png").read_bytes()
decoded = naipng.read(data)

# ...
```

### Error Handling
<a id="error-handling"></a>

`naipng` defines two error types for `naipng.read()` and its variants:

- `naipng.InvalidPNGError` is raised when a PNG is invalid and cannot be parsed, such as when:
  - The PNG datastream ends prematurely (before `IEND`)
  - A `tEXt` chunk is corrupted *(i.e. has an invalid CRC)*
  - The PNG signature is missing
  - The PNG `IHDR` chunk is missing or misplaced
- `naipng.NAIDataError` is raised when a PNG has a `tEXt` chunk designated as `naidata`,
  but it was unable to be decoded properly
  - This is never raised for `naipng.read_image_gen()`

Both error classes derive from `ValueError`.

This example shows the behaviour of `naipng.read` with an invalid PNG datastream
(correct signature, but ends early).

```python
import naipng

# Using a bytes object as input (a file-like object could be used too)
with open("image.png", "rb") as file:
    # The datastream is truncated, rendering it invalid
    data = file.read(10)

try:
    naipng.read(data)
except naipng.InvalidPNGError as e:
    raise SystemExit(f"Error: {e}") from e
```

This outputs:

```
Error: not a valid PNG file: ends prematurely
```

## CLI
<a id="cli"></a>

`naipng` may be invoked on the command line as either `python -m naipng <file>` or simply `naipng <file>`.

### Help Text
<a id="help-text"></a>

```
usage: naipng [-h] [-q] [-c] [-t] [-i] file [outfile]

read NovelAI data encoded in a PNG file

positional arguments:
  file           PNG file to read, or - for stdin
  outfile        output file path, or - for stdout (default: -)

options:
  -h, --help     show this help message and exit
  -q, --quiet    don't print errors
  -c, --compact  don't pretty-print decoded JSON
  -t, --text     only check for text generation data
  -i, --image    only check for image generation data
```

### Examples
<a id="examples"></a>

- Printing to stdout:

```bash
naipng image.png
```

- Saving to a file:

```bash
naipng image.png naidata.json
```

- Saving to a file by redirecting `stdin` and `stdout`:

```bash
naipng - < image.png > naidata.json
```

- Downloading via `curl` and piping PNG data through `stdin`:

```bash
curl -fs https://files.catbox.moe/3b6dux.png | naipng -
```

----------

`naipng` may be used in shell pipelines alongside JSON-parsing tools like [`jq`](https://jqlang.github.io/jq/)
in order to construct more complex scripts.

```bash
$ curl -fs https://files.catbox.moe/3b6dux.png | naipng -c - | jq -r ".[\"entries\"][][\"text\"]"

Everyone said that no man now living or ever after would be born who would be equal to him in strength, courage, and in all sorts of courtesy, as well as in boldness and generosity that he had above all men, and that his name would never perish in the German tongue, and the same was true with the Norsemen
```

#### Trivia
<a id="trivia"></a>

The linked file is the first Lorebook card shared as an example when PNG embedding was announced.
Its art is by Tarmillustrates.
The quote in it is from *[Þiðreks saga](https://en.wikipedia.org/wiki/%C3%9Ei%C3%B0reks_saga)*.

# Technical Background
<a id="technical-background"></a>

PNGs are made up of a sequence of data chunks.
Beyond those used to store visual information (e.g. pixels, palettes),
there are also several varieties of metadata chunks.
See [the official PNG specification](http://www.libpng.org/pub/png/spec/1.2/PNG-Structure.html) for full details.

NovelAI uses [`tEXt` metadata chunks](http://www.libpng.org/pub/png/spec/1.2/PNG-Chunks.html#C.Anc-text)
to encode most metadata.
- For text generation settings, NovelAI uses a `tEXt` chunk with a `naidata` keyword.
  - The contents are base64-encoded JSON.
  - `naidata` is a nonstandard `tEXt` keyword, so recognizing these chunks is unambiguous.
- For image generation settings, NovelAI uses multiple `tEXt` chunks, each with different keywords.
  - Some of these include `Title`, `Description`, `Software`, `Source`, and `Comment`.
  - `naipng` only reads the `Comment` field among these, which is JSON-encoded and contains the most information.
  - `Comment` is a standard `tEXt` keyword, so recognizing these chunks is slightly ambiguous.
    - Other software may use the `Comment` `tEXt` chunk type for other purposes, and may or may not store JSON in it.
    - `naipng` assumes that the first JSON-encoded `Comment` `tEXt` chunk found is valid image generation metadata.

# License
<a id="license"></a>

`naipng` is free and open-source software provided under the [zlib license](https://opensource.org/licenses/Zlib).
