"""La voz no lee markdown, LaTeX, código ni esquemas dibujados (ADR-026)."""
import pytest

from src.domain.services.speakable import (
    AVISO_CODIGO,
    AVISO_ESQUEMA,
    AVISO_FORMULA,
    speakable_text,
)


@pytest.mark.parametrize(
    "escrito, hablado",
    [
        ("La **fotosíntesis** es _clave_.", "La fotosíntesis es clave."),
        ("## Resumen\n- uno\n- dos", "Resumen. uno. dos."),
        ("1. Primero\n2. Segundo", "Primero. Segundo."),
        ("Mira [la guía](https://x.y) 😀", "Mira la guía."),
        ("Usa `ls -la` para listar", "Usa ls -la para listar."),
    ],
)
def test_el_formato_desaparece(escrito, hablado):
    assert speakable_text(escrito) == hablado


def test_una_formula_simple_se_lee_y_una_compleja_se_avisa():
    assert "2x + 3 = 7" in speakable_text("Resuelve \\(2x + 3 = 7\\).")
    # Una fracción simple ya se lee ("a sobre b"); una anidada, no.
    assert AVISO_FORMULA in speakable_text("Es \\(\\frac{\\frac{a}{b}}{c}\\).")
    assert AVISO_FORMULA in speakable_text("$$\\sum_{i=1}^n i$$")


def test_el_codigo_se_avisa_una_vez():
    t = speakable_text("Así:\n```python\nprint('hola')\nx = 1\n```\nListo.")

    assert AVISO_CODIGO in t and "print" not in t and t.endswith("Listo.")


def test_un_esquema_dibujado_se_avisa_una_vez():
    esquema = "Mira:\n+---------+\n|  Base   |\n+----|----+\n     |\nFin."

    t = speakable_text(esquema)

    assert t.count(AVISO_ESQUEMA) == 1 and "+---" not in t


def test_texto_normal_no_cambia():
    assert speakable_text("Hola, ¿cómo estás?") == "Hola, ¿cómo estás?"


def test_vacio():
    assert speakable_text("") == "" and speakable_text("```\ncodigo\n```") == AVISO_CODIGO


@pytest.mark.parametrize(
    "formula, voz",
    [
        ("\\(\\frac{1}{2}\\)", "1 sobre 2"),
        ("\\(x^2 + 3\\)", "x al cuadrado + 3"),
        ("\\(a^{3}\\)", "a al cubo"),
        ("\\(2^n\\)", "2 elevado a n"),
        ("\\(\\sqrt{16} = 4\\)", "raíz de 16 = 4"),
        ("\\(3 \\cdot 4\\)", "3 por 4"),
        ("\\(x \\leq 5\\)", "x menor o igual que 5"),
    ],
)
def test_las_formulas_simples_se_dicen(formula, voz):
    assert voz in speakable_text(formula)


def test_una_formula_que_no_se_sabe_decir_se_avisa():
    assert AVISO_FORMULA in speakable_text("\\(\\int_0^1 f(x)\\,dx\\)")
