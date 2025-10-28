from pdf_parser import parse_pdf

if __name__ == "__main__":
    pdf_path = "data/uploads/sample.pdf"   # 테스트할 PDF 경로
    output_json = "data/questions.json"

    items = parse_pdf(pdf_path, output_json)

    for q in items:
        print("="*40)
        print("문제:", q.stem)
        print("보기:", q.options)
        print("정답:", q.answer)
        print("해설:", q.explanation)
