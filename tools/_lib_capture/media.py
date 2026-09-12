"""Inspect local bytes without network access or rewriting source media."""
from dataclasses import dataclass
import hashlib
import io

from .slug import source_extension

@dataclass(frozen=True)
class ImageInfo:
    width: int
    height: int
    format: str
    sha256: str


def inspect_image(data: bytes, *, expected_format: str | None = None) -> ImageInfo:
    from PIL import Image, UnidentifiedImageError

    if not data or data.lstrip().startswith(b"<"):
        raise ValueError("image is empty or is markup, not image bytes")
    if expected_format not in (None, "PNG", "JPEG"):
        raise ValueError("only PNG/JPEG image decoding is supported")
    formats = [expected_format] if expected_format else ["PNG", "JPEG"]
    try:
        with Image.open(io.BytesIO(data), formats=formats) as image:
            if image.format not in formats:
                raise ValueError("unexpected image format before verification")
            image.verify()
        with Image.open(io.BytesIO(data), formats=formats) as image:
            if image.format not in formats:
                raise ValueError("unexpected image format before decoding")
            image.load()
            width, height = image.size
            orientation = image.getexif().get(274, 1)
            if orientation in (5, 6, 7, 8):
                width, height = height, width
            if min(width, height) < 1 or not image.format:
                raise ValueError("invalid image dimensions or format")
            return ImageInfo(width, height, image.format, hashlib.sha256(data).hexdigest())
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError) as exc:
        raise ValueError("image bytes do not decode completely") from exc


def inspect_original(data: bytes, suffix: str) -> str:
    suffix = source_extension(suffix)
    if not data:
        raise ValueError("source file is empty")
    if suffix in (".png", ".jpg", ".jpeg"):
        info = inspect_image(data, expected_format="PNG" if suffix == ".png" else "JPEG")
        if info.format != ("PNG" if suffix == ".png" else "JPEG"):
            raise ValueError("decoded image format differs from filename extension")
        return f"fully decoded {info.format}; {info.width} x {info.height} pixels"
    if suffix == ".pdf":
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError

        try:
            reader = PdfReader(io.BytesIO(data), strict=True)
            if reader.is_encrypted or not reader.pages:
                raise ValueError("PDF is encrypted or contains no pages")
            for page in reader.pages:
                contents = page.get_contents()
                if contents is not None:
                    contents.get_data()
            return f"PDF structure and page streams checked; {len(reader.pages)} pages; not visual/OCR verification"
        except PdfReadError as exc:
            raise ValueError("PDF cannot be parsed completely") from exc
    return "bytes preserved and hashed; format/content not decoded"
