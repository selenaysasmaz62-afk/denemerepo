class KelimeArastirmaMotoru:
    async def research(self, word):
        return {"word": word, "meanings": [], "sources": []}

    async def research_usage(self, word, research):
        return {"word": word, "contexts": [], "patterns": []}
