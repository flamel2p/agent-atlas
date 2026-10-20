"""Thin POSIX CLI: one bounded read, one pure map, and stdout/stderr only.

The host selects the local corpus path; source metadata and abstracts never
become tool instructions. All user-facing failures have fixed wording so file
paths and malformed input are not echoed to stderr.
"""

from __future__ import annotations

import argparse
from importlib import resources
import json
import os
import stat
import sys

from .corpus import InputError, MAX_CORPUS_BYTES, parse_corpus
from .mapping import LiteratureMap, ResearchRequest, map_literature


class _Parser(argparse.ArgumentParser):
    def error(self, _message: str) -> None:
        raise InputError("invalid command arguments")


def _read_path(path: str) -> bytes:
    """Open the named POSIX regular file without following a final symlink."""

    flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW
    fd = os.open(path, flags)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_CORPUS_BYTES:
            raise InputError("invalid corpus file")
        chunks: list[bytes] = []
        size = 0
        while size <= MAX_CORPUS_BYTES:
            chunk = os.read(fd, min(64 * 1024, MAX_CORPUS_BYTES + 1 - size))
            if not chunk:
                return b"".join(chunks)
            chunks.append(chunk)
            size += len(chunk)
        raise InputError("corpus byte limit exceeded")
    finally:
        os.close(fd)


def _default_bytes() -> bytes:
    # The packaged resource is controlled by this case, including in a wheel.
    with resources.files("scientific_research").joinpath("data/corpus.json").open("rb") as stream:
        return stream.read(MAX_CORPUS_BYTES + 1)


def _render_text(report: LiteratureMap) -> str:
    data = report.to_dict()
    lines = [
        "Synthetic literature map",
        f"Objective: {data['objective']}",
        f"Corpus: {data['corpus_id']} (SHA256 {data['corpus_sha256']})",
        f"Outcome: {data['outcome']}; stop: {data['stop_reason']}",
        f"Original: {data['original_record_count']}; considered: {data['considered_count']}; removed duplicates: {data['removed_duplicate_count']}; selected: {data['selected_count']}; truncated: {data['truncated']}",
        f"Query terms: {', '.join(data['query_terms'])}",
    ]
    for paper in data["selected_papers"]:
        score = paper["relevance"]
        lines.extend((
            "",
            f"Paper {paper['paper_id']}: {paper['title']} ({paper['year']})",
            f"Source: {paper['source']} / {paper['source_id']}; authors: {', '.join(paper['authors'])}",
            f"Relevance: {score['numerator']}/{score['denominator']}; matched: {', '.join(paper['matched_terms'])}",
            f"Abstract: {paper['abstract']}",
        ))
    for theme in data["themes"]:
        lines.extend(("", f"{theme['theme_id']} members: {', '.join(theme['member_ids'])}", f"Descriptors: {', '.join(theme['descriptors'])}"))
        for span in theme["evidence"]:
            lines.append(f"Excerpt {span['paper_id']} [{span['start']}:{span['end']}] SHA256 {span['abstract_sha256']}: {span['text']}")
    lines.append("")
    for decision in data["duplicate_decisions"]:
        lines.append(f"Duplicate {decision['retained_id']} retains aliases: {', '.join(decision['alias_ids'])}")
    lines.extend(("", *data["interpretation_limits"]))
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    """Return 0 for complete reports, 2 for rejected input, 130 on interrupt."""

    parser = _Parser(prog="scientific-research", description="Map a synthetic literature corpus into lexical themes and exact excerpts")
    parser.add_argument("--objective", required=True)
    parser.add_argument("--corpus")
    parser.add_argument("--max-papers", type=int, default=20)
    parser.add_argument("--target-themes", type=int, default=4)
    parser.add_argument("--format", choices=("json", "text"), default="json")
    try:
        args = parser.parse_args(argv)
        request = ResearchRequest(args.objective, args.max_papers, args.target_themes)
        raw = _read_path(args.corpus) if args.corpus is not None else _default_bytes()
        corpus = parse_corpus(raw)
        report = map_literature(corpus, request)
        output = json.dumps(report.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" if args.format == "json" else _render_text(report)
        sys.stdout.write(output)
        return 0
    except KeyboardInterrupt:
        sys.stderr.write("scientific-research: cancelled\n")
        return 130
    except (InputError, OSError, ValueError):
        sys.stderr.write("scientific-research: invalid input\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
