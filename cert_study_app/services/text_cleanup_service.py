import re


NOISE_ONLY_RE = re.compile(r"^[ㅇ○●◯θ∅µㆁ①②③④⑤⑥⑦⑧⑨⓵⓶⓷⓸⓹⓺⓻⓼⓽OΔXx]+$")
PAGE_FOOTER_RE = re.compile(r"^\d{1,3}\s*(?:[I|l]|\||/)\s*\d{1,3}$")


def is_noise_line(line: str) -> bool:
    text = re.sub(r"\s+", "", str(line or "").strip())
    if not text:
        return True
    if NOISE_ONLY_RE.fullmatch(text):
        return True
    if PAGE_FOOTER_RE.fullmatch(str(line or "").strip()):
        return True
    return False


def clean_question_text(value: str) -> str:
    if not value:
        return ""

    cleaned = []
    for raw_line in str(value).splitlines():
        line = re.sub(r"[ \u00A0\t]+", " ", raw_line).strip()
        if is_noise_line(line):
            continue
        cleaned.append(line)

    text = "\n".join(cleaned).strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def clean_inline_text(value: str) -> str:
    text = clean_question_text(value)
    text = re.sub(r"\s+", " ", text).strip()
    return text
