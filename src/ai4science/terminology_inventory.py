"""Literal, case-sensitive term inventory for authorized Markdown inputs.

Matches are substrings, with no word-boundary or Unicode normalization rule.
Occurrences of the same term are non-overlapping, per line; different terms
are counted independently. Markdown syntax, headings, code and references are
included. Heading recognition supports ATX and single-line Setext headings,
excluding fenced code blocks; it is not a full Markdown parser. Output contains
source excerpts and needs the same confidentiality treatment as the source.
The workspace contract is not an OS sandbox against concurrent path changes.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re

from .contracts import create_artifact, validate_workspace_path


_ATX = re.compile(r'^ {0,3}#{1,6}(?:[ \t]+|$)(.*)$')
_SETEXT = re.compile(r'^ {0,3}(?:=+|-+)[ \t]*$')
_FENCE = re.compile(r'^ {0,3}(`{3,}|~{3,})')


def _headings(lines: list[str]) -> list[str | None]:
    result: list[str | None] = []
    heading = None
    fence_char = None
    fence_length = 0
    for i, line in enumerate(lines):
        fence = _FENCE.match(line)
        if fence:
            marker = fence.group(1)
            if fence_char is None:
                fence_char, fence_length = marker[0], len(marker)
            elif marker[0] == fence_char and len(marker) >= fence_length and not line[fence.end():].strip():
                fence_char = None
            result.append(heading)
            continue
        if fence_char is None:
            atx = _ATX.match(line)
            if atx:
                heading = re.sub(r'[ \t]+#+[ \t]*$', '', atx.group(1)).strip()
            elif (line.strip() and i + 1 < len(lines) and _SETEXT.fullmatch(lines[i + 1])
                  and not _SETEXT.fullmatch(line)):
                heading = line.strip()
        result.append(heading)
    return result


def count_terms(workspace_root: Path, input_path: str, terms: list[str]) -> dict:
    """Count literal terms and return 1-based line/column and local context.

    The caller must have authorization for the chosen workspace and input.
    SHA-256 is checked against the bytes actually analyzed. No output is written.
    """
    if not isinstance(terms, list) or any(
        not isinstance(term, str) or not term.strip() or '\n' in term or '\r' in term
        for term in terms
    ):
        raise ValueError('terms must be a list of non-empty single-line strings')
    terms = list(dict.fromkeys(terms))
    if not terms:
        raise ValueError('at least one term is required')
    source = validate_workspace_path(workspace_root, input_path, must_exist=True)
    artifact = create_artifact(workspace_root, input_path)
    data = source.read_bytes()
    if hashlib.sha256(data).hexdigest() != artifact.sha256:
        raise ValueError('input changed while being read')
    lines = data.decode('utf-8').splitlines()
    headings = _headings(lines)
    counts = []
    for term in terms:
        occurrences = []
        for index, line in enumerate(lines):
            start = 0
            while (position := line.find(term, start)) != -1:
                occurrences.append({
                    'line': index + 1, 'column': position + 1,
                    'heading': headings[index],
                    'context': line[max(0, position - 40):position + len(term) + 40],
                })
                start = position + len(term)
        counts.append({'term': term, 'count': len(occurrences), 'occurrences': occurrences})
    return {'input': {'path': input_path, 'sha256': artifact.sha256}, 'terms': counts}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Count literal terms in an authorized workspace Markdown file.')
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--input', required=True, help='Workspace-relative input path')
    parser.add_argument('--term', action='append', required=True, help='Case-sensitive literal term; repeat for more')
    args = parser.parse_args(argv)
    try:
        result = count_terms(args.workspace, args.input, args.term)
    except (OSError, ValueError, UnicodeError) as exc:
        parser.exit(2, f'Inventory failed: {type(exc).__name__}; verify authorized paths, UTF-8 input and terms.\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
