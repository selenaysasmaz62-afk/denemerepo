import asyncio
from motor.ogrenme_motoru import KelimeOgrenmeMotoru

async def main():
    await KelimeOgrenmeMotoru().run()

if __name__ == "__main__":
    asyncio.run(main())
