class UrlKontrol:
    def normalize(self, url):
        return url.strip().rstrip("/")
