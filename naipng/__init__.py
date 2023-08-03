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
import abc
import base64
import binascii
import contextlib
import io
import struct
import typing
from typing import BinaryIO, Callable, NamedTuple, Optional, Union

try:
    import orjson as json
except ImportError:
    import json

__all__ = [
    "read",
    "read_text_gen",
    "read_image_gen",
    "InvalidPNGError",
    "NAIDataError",
]

# PNG Structure
# See http://www.libpng.org/pub/png/spec/1.2/PNG-Structure.html

# A PNG always starts with an 8-byte signature
_PNG_SIGNATURE = bytes((137, 80, 78, 71, 13, 10, 26, 10))
_PNG_SIGNATURE_LEN = len(_PNG_SIGNATURE)

# The rest of a PNG is a series of chunks
# A PNG chunk consists of:
# - 4 byte data length (unsigned, big-endian)
# - 4 byte type code
# - Variable length data according to the first header field, and then
# - 4 byte CRC (unsigned, big-endian)
_PNG_CHUNK_HEADER_FORMAT = struct.Struct(">I4s")
_PNG_CHUNK_HEADER_LEN = _PNG_CHUNK_HEADER_FORMAT.size
_PNG_CHUNK_FOOTER_FORMAT = struct.Struct(">I")
_PNG_CHUNK_FOOTER_LEN = _PNG_CHUNK_FOOTER_FORMAT.size
# Chunk CRC checksums include the chunk type field
_PNG_TEXT_CRC_SEED = binascii.crc32(b"tEXt")


class _PNGHeader(NamedTuple):
    chunk_data_length: int
    chunk_type: bytes


class InvalidPNGError(ValueError):
    """
    Error raised when a PNG cannot be parsed.

    This may be due to data corruption, incomplete data,
    or passing a file that is not a PNG.
    """

    pass


class NAIDataError(ValueError):
    """
    Error raised when a ``naidata`` chunk cannot be decoded.

    This is raised by `read_text_gen` or `read` if a ``naidata`` chunk
    is found, but doesn't contain base64-encoded JSON.
    """

    pass


def read(file: Union[bytes, BinaryIO]) -> Optional[dict]:
    """
    Scans a PNG file for NovelAI JSON metadata.

    This function will return the decoded contents of the first
    PNG metadata entry found that contains either text generation
    or image generation JSON data. If no such entries are found,
    this function returns None.

    Notes:
        This returns upon finding the first ``tEXt`` chunk in the PNG
        with a ``naidata`` (text generation) keyword
        that contains base64-encoded JSON,
        or ``Comment`` (image generation) keyword
        that contains regular JSON.

        If a ``naidata`` chunk is found but does not contain valid
        base64-encoded JSON, a `NAIDataError` is raised.

        If a ``Comment`` chunk is found but does not contain valid JSON,
        it is skipped, because ``Comment`` is a standard ``tEXt`` chunk
        keyword, and thus may be valid to appear in a file
        for unrelated purposes.

    See Also:
        `read_text_gen()`:
            A similar function only for text generation metadata
            that only reads ``naidata`` chunks, and skips ``Comment`` chunks

        `read_image_gen()`:
            A similar function only for image generation metadata
            that only reads ``Comment`` chunks, and skips ``naidata`` chunks

    Args:
        file: A ``bytes`` object or file-like object representing a PNG
            to read. File-like objects are streamed beginning-to-end
            and need not support random access

    Returns:
        A dict populated with decoded JSON metadata if found, otherwise None

    Raises:
        InvalidPNGError: If `file` is not a valid PNG
        NAIDataError: If `file` contains a ``tEXt`` chunk with the ``naidata``
            keyword, but it cannot be decoded

    Examples:
        Reading from a file-like object::

            import naipng

            with open("image.png", "rb") as file:
                decoded = naipng.read(file)

            if decoded is None:
                # No NovelAI data found encoded in the image
                print("N/A")
            else:
                # naipng.read() returns a dict object
                # representing the first data found
                for k, v in decoded.items():
                    print(k, "->", v)

        Reading from a ``bytes`` object::

            import naipng
            import pathlib

            data: bytes = pathlib.Path("image.png").read_bytes()
            decoded = naipng.read(data)

            # ...

        Handling errors::

            import naipng

            with open("image.png", "rb") as file:
                # The datastream is truncated, rendering it invalid
                data = file.read(10)

            try:
                naipng.read(data)
            except naipng.InvalidPNGError as e:
                # ValueError also works
                raise SystemExit(f"Error: {e}") from e
    """
    return _read(file, _parse_nai_data_or_comment_chunk)


def read_text_gen(file: Union[bytes, BinaryIO]) -> Optional[dict]:
    """
    Scans a PNG file for NovelAI JSON text generation metadata.

    This function will return the decoded contents of the first
    PNG metadata entry found that contains text generation JSON data.
    If no such entries are found, this function returns None.

    Notes:
        This returns upon finding the first ``tEXt`` chunk in the PNG
        with a ``naidata`` keyword that contains base64-encoded JSON.

        If a ``naidata`` chunk is found but does not contain valid
        base64-encoded JSON, a `NAIDataError` is raised.

    See Also:
        `read()`:
            A similar function for both text generation and image generation
            metadata that reads both ``naidata`` and ``Comment`` chunks

        `read_image_gen()`:
            A similar function only for image generation metadata
            that only reads ``Comment`` chunks, and skips ``naidata`` chunks

    Args:
        file: A ``bytes`` object or file-like object representing a PNG
            to read. File-like objects are streamed beginning-to-end
            and need not support random access

    Returns:
        A dict populated with decoded JSON metadata if found, otherwise None

    Raises:
        InvalidPNGError: If `file` is not a valid PNG
        NAIDataError: If `file` contains a ``tEXt`` chunk with the ``naidata``
            keyword, but it cannot be decoded

    Examples:
        Reading from a file-like object::

            import naipng

            with open("image.png", "rb") as file:
                decoded = naipng.read_text_gen(file)

            if decoded is None:
                # No NovelAI text generation data found encoded in the image
                print("N/A")
            else:
                # naipng.read_text_gen() returns a dict object
                # representing the first data found
                for k, v in decoded.items():
                    print(k, "->", v)

        Reading from a ``bytes`` object::

            import naipng
            import pathlib

            data: bytes = pathlib.Path("image.png").read_bytes()
            decoded = naipng.read_text_gen(data)

            # ...

        Handling errors::

            import naipng

            with open("image.png", "rb") as file:
                # The datastream is truncated, rendering it invalid
                data = file.read(10)

            try:
                naipng.read_text_gen(data)
            except naipng.InvalidPNGError as e:
                # ValueError also works
                raise SystemExit(f"Error: {e}") from e
    """
    return _read(file, _parse_nai_data_chunk)


def read_image_gen(file: Union[bytes, BinaryIO]) -> Optional[dict]:
    """
    Scans a PNG file for NovelAI JSON metadata.

    This function will return the decoded contents of the first
    PNG metadata entry found that contains image generation JSON data.
    If no such entries are found, this function returns None.

    Notes:
        This returns upon finding the first ``tEXt`` chunk in the PNG
        with a ``Comment`` keyword that contains JSON.

        If a ``Comment`` chunk is found but does not contain valid JSON,
        it is skipped, because ``Comment`` is a standard ``tEXt`` chunk
        keyword, and thus may be valid to appear in a file
        for unrelated purposes.

    See Also:
        `read()`:
            A similar function for both text generation and image generation
            metadata that reads both ``naidata`` and ``Comment`` chunks

        `read_text_gen()`:
            A similar function only for text generation metadata
            that only reads ``naidata`` chunks, and skips ``Comment`` chunks

    Args:
        file: A ``bytes`` object or file-like object representing a PNG
            to read. File-like objects are streamed beginning-to-end
            and need not support random access

    Returns:
        A dict populated with decoded JSON metadata if found, otherwise None

    Raises:
        InvalidPNGError: If `file` is not a valid PNG

    Examples:
        Reading from a file-like object::

            import naipng

            with open("image.png", "rb") as file:
                decoded = naipng.read_image_gen(file)

            if decoded is None:
                # No NovelAI data found encoded in the image
                print("N/A")
            else:
                # naipng.read_image_gen() returns a dict object
                # representing the first data found
                for k, v in decoded.items():
                    print(k, "->", v)

        Reading from a ``bytes`` object::

            import naipng
            import pathlib

            data: bytes = pathlib.Path("image.png").read_bytes()
            decoded = naipng.read_image_gen(data)

            # ...

        Handling errors::

            import naipng

            with open("image.png", "rb") as file:
                # The datastream is truncated, rendering it invalid
                data = file.read(10)

            try:
                naipng.read_image_gen(data)
            except naipng.InvalidPNGError as e:
                # ValueError also works
                raise SystemExit(f"Error: {e}") from e
    """
    return _read(file, _parse_comment_chunk)


def _read(
    file: Union[bytes, BinaryIO], parser: Callable[[bytes], Optional[dict]]
) -> Optional[dict]:
    if not (isinstance(file, (bytes, io.IOBase))):
        raise TypeError(
            "read() argument 'file' must be bytes or a"
            f" readable binary file-like object, not {type(file).__name__}"
        )
    with _StreamReader.of(file) as reader:
        try:
            if reader.read(_PNG_SIGNATURE_LEN) != _PNG_SIGNATURE:
                raise InvalidPNGError(
                    "not a valid PNG file: incorrect PNG signature"
                )
        except EOFError as e:
            raise InvalidPNGError(
                "not a valid PNG file: too short, missing PNG signature"
            ) from e

        try:
            is_first_chunk = True
            while True:
                header = _PNGHeader._make(
                    _PNG_CHUNK_HEADER_FORMAT.unpack_from(
                        reader.read(_PNG_CHUNK_HEADER_LEN)
                    )
                )

                if is_first_chunk != (header.chunk_type == b"IHDR"):
                    raise InvalidPNGError(
                        "not a valid PNG file: IHDR chunk missing or misplaced"
                    )
                is_first_chunk = False

                if header.chunk_type == b"tEXt":
                    chunk_data = reader.read(header.chunk_data_length)
                    chunk_crc = _PNG_CHUNK_FOOTER_FORMAT.unpack_from(
                        reader.read(_PNG_CHUNK_FOOTER_LEN)
                    )[0]

                    # Calculate the CRC and compare against the one
                    # encoded in the file, to check for data corruption
                    # Note: Only calculated for chunks already recognized
                    # as tEXt chunks.
                    crc = binascii.crc32(chunk_data, _PNG_TEXT_CRC_SEED)
                    if crc != chunk_crc:
                        raise InvalidPNGError(
                            "not a valid PNG file: invalid chunk CRC"
                        )

                    parsed = parser(chunk_data)
                    if parsed is not None:
                        return parsed
                    del chunk_data, chunk_crc

                elif header.chunk_type == b"IEND":
                    break

                else:
                    reader.skip(
                        header.chunk_data_length + _PNG_CHUNK_FOOTER_LEN
                    )
        except EOFError as e:
            raise InvalidPNGError(
                "not a valid PNG file: ends prematurely"
            ) from e

        return None


def _parse_nai_data_or_comment_chunk(data: bytes) -> Optional[dict]:
    if data.startswith(b"naidata\0"):
        return _parse_nai_data_chunk(data)
    elif data.startswith(b"Comment\0"):
        return _parse_comment_chunk(data)
    else:
        return None


def _parse_nai_data_chunk(data: bytes) -> Optional[dict]:
    keyword = b"naidata\0"
    if not data.startswith(keyword):
        return None
    with memoryview(data) as mv:
        content = mv[len(keyword) :]
        try:
            raw_json = base64.b64decode(content, validate=True)
        except binascii.Error as e:
            raise NAIDataError(
                "invalid naidata chunk, not base64 encoded"
            ) from e
        try:
            return json.loads(raw_json)
        except json.JSONDecodeError as e:
            raise NAIDataError(
                "invalid naidata chunk, could not parse as JSON"
            ) from e


def _parse_comment_chunk(data: bytes) -> Optional[dict]:
    keyword = b"Comment\0"
    if not data.startswith(keyword):
        return None
    with memoryview(data) as mv:
        content = mv[len(keyword) :]
        try:
            if (
                len(content) < 2
                or content[0] != ord(b"{")
                or content[-1] != ord(b"}")
            ):
                # Not a JSON object
                return None
            return json.loads(content)
        except json.JSONDecodeError:
            # This is not necessarily an error case, as "Comment" is a standard
            # PNG tEXt chunk keyword. It could be used for other things than JSON.
            return None


class _StreamReader(contextlib.AbstractContextManager):
    def __init__(self, data: Union[bytes, BinaryIO]) -> None:
        self.data = data

    @staticmethod
    def of(data: Union[bytes, BinaryIO]) -> "_StreamReader":
        if isinstance(data, bytes):
            return _BytesReader(data)
        elif isinstance(data, io.IOBase):
            return _IOReader(typing.cast(BinaryIO, data))
        else:
            raise TypeError(f"no reader defined for type {type(data).__name__}")

    def read(self, num_bytes: int) -> Union[bytes, memoryview]:
        bytes_read = self._read(num_bytes)
        if len(bytes_read) < num_bytes:
            raise EOFError(
                f"requested {num_bytes} byte(s),"
                f" but only {len(bytes_read)} byte(s) were available"
            )
        return bytes_read

    @abc.abstractmethod
    def _read(self, num_bytes: int) -> Union[bytes, memoryview]:
        ...

    @abc.abstractmethod
    def skip(self, num_bytes: int) -> None:
        ...

    def close(self) -> None:
        pass

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()


class _IOReader(_StreamReader):
    _MAX_SKIP_CHUNK_SIZE: int = 256 << 10

    def __init__(self, data: BinaryIO):
        super().__init__(data)
        self._skip_buffer = None
        if not self.data.seekable():
            if hasattr(self.data, "readinto"):
                self.skip = self._readinto_skip
            else:
                self.skip = self._read_skip

    def _read(self, num_bytes: int) -> bytes:
        return self.data.read(num_bytes)

    def skip(self, num_bytes: int):
        # Skip by seeking
        self.data.seek(num_bytes, io.SEEK_CUR)

    def _read_skip(self, num_bytes: int):
        # Skip by reading and discarding data,
        # but not in more than 256 KiB chunks at a time
        block_size = self._MAX_SKIP_CHUNK_SIZE
        while num_bytes > block_size:
            num_bytes_read = len(self.data.read(block_size))
            if num_bytes_read > 0:
                num_bytes -= num_bytes_read
            else:
                return
        if num_bytes > 0:
            self.data.read(num_bytes)

    def _readinto_skip(self, num_bytes: int):
        # Skip by reading and discarding data,
        # but not in more than 256 KiB chunks at a time,
        # and reusing the same buffer to minimize memory allocations
        data = typing.cast(io.RawIOBase, self.data)
        block_size = self._MAX_SKIP_CHUNK_SIZE
        if num_bytes > block_size:
            block = self._skip_buffer
            if block is None or len(block) != block_size:
                self._skip_buffer = block = bytearray(block_size)
            while num_bytes > block_size:
                num_bytes_read = data.readinto(block)
                if num_bytes_read > 0:
                    num_bytes -= num_bytes_read
                else:
                    return
        if num_bytes > 0:
            data.read(num_bytes)

    def close(self) -> None:
        self._skip_buffer = None


class _BytesReader(_StreamReader):
    def __init__(self, data: bytes) -> None:
        super().__init__(data)
        self.pos = 0
        self.mv = memoryview(data)

    def _read(self, num_bytes: int) -> memoryview:
        old_pos = self.pos
        self.pos += num_bytes
        return self.mv[old_pos : self.pos]

    def skip(self, num_bytes: int) -> None:
        self.pos += num_bytes

    def close(self) -> None:
        self.mv.release()
