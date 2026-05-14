"""Configuración compartida para pruebas unitarias del backend.

No se carga .env ni configuración de infraestructura: solo se ajusta el path
de importación para que `pytest` encuentre el paquete `src` al ejecutar
desde la raíz del repositorio.
"""

import sys
from pathlib import Path

# Simulamos un entorno de ejecución donde el proyecto está en el path de Python.
# No es un mock de negocio: es utilidad de descubrimiento de módulos para pytest.
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
