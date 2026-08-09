"""Line-decoding iterator for csv.reader that exposes the underlying byte
offset, so a caller can record where each CSV row starts even when a row
spans multiple physical lines because of an embedded newline inside a
quoted field.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import BinaryIO

DEFAULT_ENCODING = "utf-8"


class _OffsetTrackingLines:
    """Decodes physical lines from a binary file one at a time, suitable as
    the input iterable for csv.reader. csv.reader pulls as many lines as it
    needs to complete a row (more than one if a quoted field contains a raw
    newline), so offset tracking has to live at the file-handle level via
    tell() rather than by counting lines yielded.
    """

    def __init__(self, fileobj: BinaryIO, encoding: str = DEFAULT_ENCODING) -> None:
        self._file = fileobj
        self._encoding = encoding

    def __iter__(self) -> Iterator[str]:
        return self

    def __next__(self) -> str:
        raw = self._file.readline()
        if not raw:
            raise StopIteration
        return raw.decode(self._encoding)

    def tell(self) -> int:
        return self._file.tell()
