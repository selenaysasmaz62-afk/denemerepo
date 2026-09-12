import asyncio

from motor.cumle_motoru_v2 import CumleMotoruV2


async def main():
    word = "ince"
    motor = CumleMotoruV2()
    sentences = await motor._tatoeba_sentences(word)

    if not sentences:
        raise AssertionError("Tatoeba 'ince' için geçerli cümle döndürmedi.")

    for sentence, url in sentences:
        if not motor._contains_target_word(word, sentence):
            raise AssertionError(f"Tatoeba yanlış eşleşme döndürdü: {sentence}")
        if len(sentence.split()) < 3:
            raise AssertionError(f"Tatoeba çok kısa cümle döndürdü: {sentence}")
        if not url:
            raise AssertionError(f"Tatoeba kaynak URL'si eksik: {sentence}")

    print(f"Tatoeba OK: {len(sentences)} geçerli 'ince' cümlesi bulundu.")
    for sentence, url in sentences[:5]:
        print(f"- {sentence} | {url}")


if __name__ == "__main__":
    asyncio.run(main())
