from motor.tekrar_kontrol import TekrarKontrol

def test_duplicate():
    assert TekrarKontrol().is_duplicate(["Merhaba", " merhaba "])
