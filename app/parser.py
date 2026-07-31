from __future__ import annotations

import re
from dataclasses import dataclass


URL_PATTERN = re.compile(r"https?://[^\s<>\])}\"'`]+")
POSSIBLE_NAME_PATTERN = re.compile(
    r"^[А-ЯЁ][а-яё-]+(?:\s+[А-ЯЁ][а-яё-]+){1,3}$"
)
ZERO_PATTERN = re.compile(r"^[\s:;,\-.()]*0[\s:;,\-.()]*$")


@dataclass(frozen=True)
class RealtorLeads:
    realtor_name: str
    links: list[str]


def extract_realtor_leads(document_text: str, realtor_name: str) -> RealtorLeads:
    lines = document_text.splitlines()
    normalized_target = normalize_text(realtor_name)

    start_index = None
    header_tail = ""
    for index, line in enumerate(lines):
        normalized_line = normalize_text(line)
        position = normalized_line.find(normalized_target)
        if position == -1:
            continue

        start_index = index
        header_tail = line[position + len(realtor_name) :]
        break

    if start_index is None:
        return RealtorLeads(realtor_name=realtor_name, links=[])

    block_lines = []
    if header_tail.strip():
        block_lines.append(header_tail.strip(" :-\t"))

    for raw_line in lines[start_index + 1 :]:
        stripped = raw_line.strip()
        if not stripped:
            if block_lines:
                break
            continue

        if is_new_realtor_header(stripped):
            break

        block_lines.append(stripped)

    if block_means_no_leads(block_lines):
        return RealtorLeads(realtor_name=realtor_name, links=[])

    links = []
    seen = set()
    for line in block_lines:
        for link in URL_PATTERN.findall(line):
            clean_link = link.rstrip(".,);")
            if clean_link not in seen:
                seen.add(clean_link)
                links.append(clean_link)

    return RealtorLeads(realtor_name=realtor_name, links=links)


def normalize_text(value: str) -> str:
    return " ".join(value.split()).casefold()


def is_new_realtor_header(line: str) -> bool:
    if "http://" in line or "https://" in line:
        return False
    return bool(POSSIBLE_NAME_PATTERN.match(line))


def block_means_no_leads(block_lines: list[str]) -> bool:
    if not block_lines:
        return True
    if len(block_lines) == 1 and ZERO_PATTERN.match(block_lines[0]):
        return True
    return False
