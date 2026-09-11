import asyncio
import json

from motor.cumle_motoru_v2 import CumleMotoruV2
from motor.arastirma_motoru import KelimeArastirmaMotoru


async def main():
    word = "ince"
    cm = CumleMotoruV2()
    am = KelimeArastirmaMotoru()

    print("=== 1 TATOEBA ===")
    tatoeba = await cm._tatoeba_sentences(word)
    print("adet:", len(tatoeba))
    for x in tatoeba[:10]:
        print("-", x)

    print("\n=== 2 WEB CUMLE ARAMASI ===")
    for query in (
        f'"{word}" "örnek cümle"',
        f'"{word}" "örnek kullanım"',
        f'"{word}" "cümle içinde"',
        f'"{word}" "kullanım örneği"',
        f'"{word}" günlük kullanım',
    ):
        data = await cm.web.search(query)
        results = data.get("results", [])
        print("\nSORGULAMA:", query)
        print("adet:", len(results))
        for r in results[:5]:
            print(json.dumps(r, ensure_ascii=False))

    print("\n=== 3 ARAMA MOTORU RESEARCH ===")
    research = await am.research(word)
    print("sources:", len(research.get("sources", [])))
    print(json.dumps(research, ensure_ascii=False, indent=2)[:12000])

    print("\n=== 4 CUMLE MOTORU FINAL ===")
    usage = await am.research_usage(word, research)
    sentences = await cm.research(word, research, usage)
    print("adet:", len(sentences))
    print(json.dumps(sentences, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
