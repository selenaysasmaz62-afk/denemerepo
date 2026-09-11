from motor.kalite_kontrol import KaliteKontrol

def test_empty_result_is_rejected():
    assert not KaliteKontrol(90).validate("x", {}, {}, [], [])["accepted"]
