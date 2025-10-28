from pdf_pipeline import extract_page_text_with_fallback
from llm_extract import chain

def parse_pdf(pdf_path: str):
    pages = extract_page_text_with_fallback(pdf_path)

    results = []
    for idx, src, text in pages:
        if not text.strip():
            continue
        try:
            parsed = chain.invoke({"page_text": text})
            results.extend(parsed.items)
        except Exception as e:
            print(f"Page {idx+1} LLM 실패: {e}")
    return results

if __name__ == "__main__":
    pdf_path = "data/sample.pdf"
    items = parse_pdf(pdf_path)

    for q in items:
        print("="*40)
        print("문제:", q.stem)
        print("보기:", q.options)
        print("정답:", q.answer)
        print("해설:", q.explanation)
