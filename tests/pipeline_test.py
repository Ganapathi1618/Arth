import sys, asyncio, os
sys.path.insert(0,"backend")
os.environ["TRANSLATION_PROVIDER"]="mock"
from app.services.pdf_engine import inspect, extract, rebuild
from app.services.translator import get_provider

async def main():
    src="tests/sample_textbook.pdf"
    info=inspect(src)
    print(f"pages={info.pages} text_layer={info.has_text_layer} scanned={info.scanned_pages} multicol={info.multi_column_pages}")
    blocks=extract(src)
    print(f"blocks extracted: {len(blocks)}")
    for b in blocks[:6]:
        print(f"  p{b.page} size={b.size} bold={b.bold} align={b.align} :: {b.text[:58]}")
    prov=get_provider()
    outs=await prov.translate_batch([b.text for b in blocks],"en","te")
    for b,o in zip(blocks,outs): b.translated=o
    stats=rebuild(src,"tests/out_te.pdf",blocks,"te")
    print("rebuild stats:",stats)
    import pymupdf
    pymupdf.open("tests/out_te.pdf")[0].get_pixmap(dpi=140).save("tests/out_te.png")
    pymupdf.open(src)[0].get_pixmap(dpi=140).save("tests/orig.png")

asyncio.run(main())
