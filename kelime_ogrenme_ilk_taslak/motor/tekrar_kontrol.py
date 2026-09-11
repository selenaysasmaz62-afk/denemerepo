class TekrarKontrol:
    def is_duplicate(self, values):
        normalized = [" ".join(str(v).casefold().split()) for v in values]
        return len(normalized) != len(set(normalized))
