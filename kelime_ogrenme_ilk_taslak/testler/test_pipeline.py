from config import SETTINGS

def test_safe_input_exists():
    assert SETTINGS.input_file.exists()
