from typing import List


def split_code_by_lines(code: str, max_lines: int) -> List[str]:
    lines = code.splitlines()
    if len(lines) <= max_lines:
        return [code]
    return ["\n".join(lines[i : i + max_lines]) for i in range(0, len(lines), max_lines)]
