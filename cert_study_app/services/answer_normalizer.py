from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from cert_study_app.services.text_cleanup_service import clean_inline_text


YES_WORDS = {"yes", "y", "예", "true", "selected"}
NO_WORDS = {"no", "n", "아니오", "아니요", "false", "not selected"}


@dataclass(frozen=True)
class AnswerEvaluation:
    chosen: str
    answer: str
    normalized_chosen: str
    normalized_answer: str
    correct: bool
    ordered: bool = False


def normalize_options(raw: Any) -> list[str]:
    if not raw:
        return []
    try:
        if isinstance(raw, str):
            parsed = json.loads(raw)
            if isinstance(parsed, (list, dict)):
                raw = parsed
        if isinstance(raw, dict):
            keyed = []
            for key, value in sorted(raw.items(), key=lambda kv: str(kv[0])):
                text = clean_inline_text(value)
                if re.match(r"^[A-Za-z1-9][\.\)]\s+", text):
                    keyed.append(text)
                else:
                    keyed.append(f"{key}. {text}")
            return split_embedded_options(keyed)
        if isinstance(raw, list):
            return split_embedded_options(raw)
    except Exception:
        return []
    return []


def split_embedded_options(options: list[str]) -> list[str]:
    split = []
    expected = "A"
    for option in options:
        text = clean_inline_text(option)
        if not text:
            continue
        parts = list(re.finditer(r"(?<![A-Za-z0-9])([A-Z])[\.\)]\s+", text))
        if len(parts) <= 1:
            split.append(text)
            continue
        for index, match in enumerate(parts):
            end = parts[index + 1].start() if index + 1 < len(parts) else len(text)
            part = text[match.start() : end].strip()
            label = match.group(1).upper()
            if label >= expected:
                split.append(part)
                expected = chr(ord(label) + 1)
    return split


def extract_options_from_stem(stem: str) -> list[str]:
    lines = [line.strip() for line in (stem or "").splitlines() if line.strip()]
    options = []
    current_key = None
    current_parts = []
    expected = "A"

    def flush():
        if current_key and current_parts:
            text = " ".join(current_parts).strip()
            if text:
                options.append(f"{current_key}. {text}")

    for line in lines:
        if re.match(r"^(answer|정답|explanation|reference)\b", line, re.I):
            flush()
            current_key = None
            current_parts = []
            break

        marker = None
        body = ""
        exact = re.match(r"^([A-Z])[\.\)]?$", line, re.I)
        inline = re.match(r"^([A-Z])[\.\)]?\s+(.+)$", line, re.I)
        if exact:
            marker = exact.group(1).upper()
        elif inline:
            marker = inline.group(1).upper()
            body = inline.group(2).strip()

        if marker and marker >= expected:
            flush()
            current_key = marker
            current_parts = [body] if body else []
            expected = chr(ord(marker) + 1)
        elif current_key:
            current_parts.append(line)

    flush()
    return options if len(options) >= 2 else []


def extract_answer_from_stem(stem: str) -> str:
    match = re.search(r"(?:Answer|정답)\s*:?\s*([A-Z1-9])", stem or "", re.I)
    if not match:
        return ""
    value = match.group(1).upper()
    if value.isdigit():
        return chr(ord("A") + int(value) - 1)
    return value


def option_label(value: Any) -> str:
    text = str(value or "").strip().upper()
    if text.isdigit():
        return chr(ord("A") + int(text) - 1)
    match = re.match(r"^([A-Z])(?:[\s\.,\)]|$)", text)
    return match.group(1) if match else text


def choice_labels(value: Any) -> list[str]:
    text = str(value or "").strip().upper()
    if not text:
        return []
    if re.fullmatch(r"[A-Z]{2,26}", text):
        return list(text)
    tokens = re.findall(r"\b[A-Z]\b|\b[1-9]\b", text)
    return [option_label(token) for token in tokens]


def yes_no_labels(value: Any) -> list[str]:
    raw_value = _parse_jsonish(value)

    if isinstance(raw_value, list):
        values = [
            item.get("value") or item.get("answer") or item.get("selected_answer")
            for item in raw_value
            if isinstance(item, dict)
        ]
        labels = yes_no_labels(",".join(str(item) for item in values if item))
        if labels:
            return labels
    elif isinstance(raw_value, dict):
        labels = yes_no_labels(",".join(str(item) for item in raw_value.values()))
        if labels:
            return labels

    text = str(value or "").strip().lower()
    if not text:
        return []
    if re.fullmatch(r"[yn](?:\s*,\s*[yn])+", text, re.I):
        return [token.upper() for token in re.findall(r"[yn]", text, re.I)]

    tokens = re.findall(
        r"(?<![가-힣])예(?![가-힣])|아니오|아니요|\byes\b|\bno\b|\bselected\b|\bnot selected\b|\btrue\b|\bfalse\b",
        text,
        re.I,
    )
    labels = []
    for token in tokens:
        lowered = token.lower()
        labels.append("Y" if token == "예" or lowered in YES_WORDS else "N")
    return labels if len(labels) >= 2 else []


def structured_answer_values(value: Any) -> list[str]:
    raw_value = _parse_jsonish(value)
    if isinstance(raw_value, list):
        values = [
            item.get("value") or item.get("answer") or item.get("selected_answer")
            for item in raw_value
            if isinstance(item, dict)
        ]
    elif isinstance(raw_value, dict):
        values = list(raw_value.values())
    else:
        return []
    return [str(item).strip() for item in values if str(item).strip()]


def option_text(options: list[str], label: str) -> str:
    label = option_label(label)
    for index, option in enumerate(options, 1):
        text = str(option).strip()
        keys = {str(index), chr(ord("A") + index - 1)}
        match = re.match(r"^([A-Z1-9])[\.\)]\s+(.+)$", text, re.I)
        if match:
            keys.add(option_label(match.group(1)))
            if match.group(1).isdigit():
                keys.add(match.group(1))
        if label in keys:
            return text
    return ""


def option_labels_from_texts(options: list[str], values: Any, allow_duplicates: bool = False) -> list[str]:
    if not values:
        return []
    if isinstance(values, str):
        values = [values]
    labels = []
    for value in values:
        target = re.sub(r"\s+", " ", str(value or "").strip()).lower()
        if not target:
            continue
        for index, option in enumerate(options, 1):
            body = re.sub(r"\s+", " ", _option_body(option)).lower()
            if body and (target == body or target in body or body in target):
                label = chr(ord("A") + index - 1)
                if allow_duplicates or label not in labels:
                    labels.append(label)
                break
    return labels


def normalize_answer(value: Any, *, ordered: bool = False) -> str:
    yn = yes_no_labels(value)
    if yn:
        return ",".join(yn)
    labels = choice_labels(value)
    if not labels:
        return option_label(value)
    if ordered:
        return ",".join(labels)
    return ",".join(sorted(set(labels)))


def evaluate_answer(chosen: Any, answer: Any, *, ordered: bool = False) -> AnswerEvaluation:
    normalized_chosen = normalize_answer(chosen, ordered=ordered)
    normalized_answer = normalize_answer(answer, ordered=ordered)
    return AnswerEvaluation(
        chosen=str(chosen or ""),
        answer=str(answer or ""),
        normalized_chosen=normalized_chosen,
        normalized_answer=normalized_answer,
        correct=normalized_chosen == normalized_answer,
        ordered=ordered,
    )


def _option_body(option: str) -> str:
    text = str(option or "").strip()
    match = re.match(r"^([A-Z1-9])[\.\)]\s+(.+)$", text, re.I)
    return (match.group(2) if match and match.group(2) else text).strip()


def _parse_jsonish(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value) if isinstance(value, str) else None
    except Exception:
        return None
