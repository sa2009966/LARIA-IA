"""Parser de múltiples formatos de archivo a texto plano.

Extrae el texto de PDF, DOCX, XLSX, PPTX, TXT/MD y archivos de código/planos.
Cada parser devuelve una cadena de texto UTF-8 que LARIA puede analizar.
"""
from __future__ import annotations

import io
import re
from enum import Enum

# Librerías de parsing (imports lazy para no bloquear el arranque si faltan).
try:
    from PyPDF2 import PdfReader
except ImportError:  # pragma: no cover
    PdfReader = None

try:
    import docx
except ImportError:  # pragma: no cover
    docx = None

try:
    import openpyxl
except ImportError:  # pragma: no cover
    openpyxl = None

try:
    import pptx
except ImportError:  # pragma: no cover
    pptx = None

try:
    import chardet
except ImportError:  # pragma: no cover
    chardet = None


class UnsupportedFormatError(ValueError):
    """El formato del archivo no se puede parsear."""


class FileFormat(str, Enum):
    TXT = "txt"
    MD = "md"
    MARKDOWN = "markdown"
    PDF = "pdf"
    DOCX = "docx"
    XLSX = "xlsx"
    PPTX = "pptx"
    CODE = "code"


# Extensiones que siempre se tratan como texto puro (independiente del encoding).
_TEXT_SUFFIXES = {".txt", ".md", ".markdown"}
# Extensiones de código / planos / otros textos planos.
_PLAIN_CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".htm", ".css", ".scss",
    ".json", ".csv", ".xml", ".yaml", ".yml", ".toml", ".ini", ".cfg",
    ".sh", ".bash", ".sql", ".java", ".c", ".cpp", ".h", ".cs", ".php",
    ".rb", ".go", ".rs", ".swift", ".kt", ".r", ".jl", ".lua", ".pl",
    ".tex", ".rst", ".log",
}
_BINARY_SUFFIXES = {".pdf", ".docx", ".xlsx", ".pptx"}


def _input_key_factory() -> re.Pattern:
    return re.compile(r".+\.\w+$")


def extension_of(filename: str) -> str:
    name = (filename or "").strip().lower()
    match = _input_key_factory().match(name)
    if not match:
        return ""
    return name.rsplit(".", 1)[-1]


def _format_for(filename: str) -> FileFormat:
    ext = extension_of(filename)
    if not ext:
        return FileFormat.TXT
    if ext in {"txt"}:
        return FileFormat.TXT
    if ext in {"md", "markdown"}:
        return FileFormat.MARKDOWN
    if ext == "pdf":
        return FileFormat.PDF
    if ext == "docx":
        return FileFormat.DOCX
    if ext == "xlsx":
        return FileFormat.XLSX
    if ext == "pptx":
        return FileFormat.PPTX
    return FileFormat.CODE


def is_supported(filename: str) -> bool:
    """True si podemos extraer texto del archivo."""
    ext = "." + extension_of(filename)
    if ext in _TEXT_SUFFIXES or ext in _PLAIN_CODE_EXTENSIONS or ext in _BINARY_SUFFIXES:
        return True
    # fallback: nombres sin extensión se tratan como texto.
    return extension_of(filename) == ""


def parse_file(filename: str, data: bytes) -> str:
    """Extrae texto plano de `data` según la extensión de `filename`.

    Returns:
        Texto UTF-8 extraído. Nunca vacío (lanza UnsupportedFormatError si no
        se pudo parsear).
    """
    fmt = _format_for(filename)
    if fmt in (FileFormat.TXT, FileFormat.MARKDOWN, FileFormat.CODE):
        if fmt == FileFormat.CODE and "." + extension_of(filename) not in (
            _TEXT_SUFFIXES | _PLAIN_CODE_EXTENSIONS
        ):
            # extensión rara pero no binaria → intentar texto
            return _decode_text(data)
        return _decode_text(data)
    if fmt == FileFormat.PDF:
        return _parse_pdf(data)
    if fmt == FileFormat.DOCX:
        return _parse_docx(data)
    if fmt == FileFormat.XLSX:
        return _parse_xlsx(data)
    if fmt == FileFormat.PPTX:
        return _parse_pptx(data)
    raise UnsupportedFormatError(f"No se puede procesar el formato del archivo: {filename}")


def _decode_text(data: bytes) -> str:
    """Decodifica bytes a texto usando UTF-8 o detección de encoding."""
    if not data:
        return ""
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        if chardet is not None:
            detected = chardet.detect(data[:100_000] if len(data) > 100_000 else data)
            enc = detected.get("encoding")
            if enc:
                try:
                    return data.decode(enc, errors="replace")
                except (LookupError, UnicodeDecodeError):
                    pass
        return data.decode("latin-1", errors="replace")


def _parse_pdf(data: bytes) -> str:
    if PdfReader is None:
        raise UnsupportedFormatError("PyPDF2 no está instalado para leer PDF.")
    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception as exc:  # noqa: BLE001
        raise UnsupportedFormatError(f"No se pudo leer el PDF: {exc}") from exc
    parts = []
    for page in reader.pages:
        try:
            txt = page.extract_text() or ""
            if txt.strip():
                parts.append(txt)
        except Exception:  # noqa: BLE001
            continue
    text = "\n\n".join(parts).strip()
    if not text:
        raise UnsupportedFormatError("El PDF no contiene texto extraíble (¿escaneado?).")
    return text


def _parse_docx(data: bytes) -> str:
    if docx is None:
        raise UnsupportedFormatError("python-docx no está instalado para leer DOCX.")
    try:
        document = docx.Document(io.BytesIO(data))
    except Exception as exc:  # noqa: BLE001
        raise UnsupportedFormatError(f"No se pudo leer el DOCX: {exc}") from exc
    paragraphs = [p.text for p in document.paragraphs if p.text and p.text.strip()]
    # Tablas del documento.
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            if any(cells):
                paragraphs.append(" | ".join(cells))
    text = "\n".join(paragraphs).strip()
    if not text:
        raise UnsupportedFormatError("El documento DOCX no contiene texto.")
    return text


def _parse_xlsx(data: bytes) -> str:
    if openpyxl is None:
        raise UnsupportedFormatError("openpyxl no está instalado para leer XLSX.")
    try:
        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as exc:  # noqa: BLE001
        raise UnsupportedFormatError(f"No se pudo leer el XLSX: {exc}") from exc
    rows_out = []
    for sheet in wb.worksheets:
        rows_out.append(f"[Hoja: {sheet.title}]")
        for row in sheet.iter_rows(values_only=True):
            cells = [str(c).strip() if c is not None else "" for c in row]
            if any(cells):
                rows_out.append(" | ".join(cells))
    text = "\n".join(rows_out).strip()
    wb.close()
    if not text:
        raise UnsupportedFormatError("El libro XLSX no contiene datos.")
    return text


def _parse_pptx(data: bytes) -> str:
    if pptx is None:
        raise UnsupportedFormatError("python-pptx no está instalado para leer PPTX.")
    try:
        prs = pptx.Presentation(io.BytesIO(data))
    except Exception as exc:  # noqa: BLE001
        raise UnsupportedFormatError(f"No se pudo leer el PPTX: {exc}") from exc
    parts = []
    for slide in prs.slides:
        slide_text = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    line = "".join(run.text for run in para.runs)
                    if line.strip():
                        slide_text.append(line)
            if shape.has_table:
                for row in shape.table.rows:
                    cells = [cell.text.strip() for cell in row.cells]
                    if any(cells):
                        slide_text.append(" | ".join(cells))
        if slide_text:
            parts.append("\n".join(slide_text))
    text = "\n\n---\n\n".join(parts).strip()
    if not text:
        raise UnsupportedFormatError("La presentación PPTX no contiene texto.")
    return text
