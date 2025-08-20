from datetime import date
from app.models import Documento  # importa il tuo modello Documento

def test_crea_ddt():
    """Crea un DDT fittizio e controlla i campi"""
    ddt = Documento(
        tipo="DDT_IN",
        numero=1,
        anno=2025,
        data=date.today(),
    )
    assert ddt.tipo == "DDT_IN"
    assert ddt.numero == 1
    assert ddt.anno == 2025
