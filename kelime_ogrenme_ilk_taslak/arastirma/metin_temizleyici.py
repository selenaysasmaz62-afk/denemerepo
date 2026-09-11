class MetinTemizleyici:
    def clean(self, text):
        return " ".join((text or "").split())
