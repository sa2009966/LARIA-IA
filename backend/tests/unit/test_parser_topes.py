"""Topes del parser contra archivos hostiles (bombas zip, PDFs gigantes)."""
import io
import zipfile

import pytest

from src.application import file_parser as fp


def _zip(entradas: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for nombre, datos in entradas.items():
            zf.writestr(nombre, datos)
    return buf.getvalue()


def test_una_bomba_zip_se_rechaza_sin_descomprimir(monkeypatch):
    monkeypatch.setattr(fp, "MAX_UNCOMPRESSED_BYTES", 1024 * 1024)
    bomba = _zip({"word/document.xml": b"0" * (2 * 1024 * 1024)})  # comprime a ~2 KB

    assert len(bomba) < 20_000
    with pytest.raises(fp.UnsupportedFormatError, match="descomprimido"):
        fp.parse_file("bomba.docx", bomba)


def test_demasiadas_entradas_se_rechazan(monkeypatch):
    monkeypatch.setattr(fp, "MAX_ZIP_ENTRIES", 10)

    with pytest.raises(fp.UnsupportedFormatError, match="demasiadas partes"):
        fp.parse_file("x.xlsx", _zip({f"f{i}.xml": b"x" for i in range(11)}))


def test_un_zip_roto_da_un_mensaje_claro():
    with pytest.raises(fp.UnsupportedFormatError, match="dañado"):
        fp.parse_file("roto.pptx", b"no soy un zip")


def test_pdf_con_demasiadas_paginas(monkeypatch):
    # PyPDF2 ya es dependencia del parser. reportlab no está en el CI.
    from PyPDF2 import PdfWriter

    writer = PdfWriter()
    for _ in range(4):
        writer.add_blank_page(width=72, height=72)
    buf = io.BytesIO()
    writer.write(buf)
    monkeypatch.setattr(fp, "MAX_PDF_PAGES", 3)

    with pytest.raises(fp.UnsupportedFormatError, match="4 páginas"):
        fp.parse_file("libro.pdf", buf.getvalue())


def test_el_texto_extraido_tiene_tope(monkeypatch):
    monkeypatch.setattr(fp, "MAX_TEXT_CHARS", 100)

    assert len(fp.parse_file("a.txt", b"x" * 1000)) == 100


def test_un_docx_normal_sigue_funcionando():
    import docx

    d = docx.Document()
    d.add_paragraph("La célula es la unidad de la vida.")
    buf = io.BytesIO()
    d.save(buf)

    assert "célula" in fp.parse_file("a.docx", buf.getvalue())
