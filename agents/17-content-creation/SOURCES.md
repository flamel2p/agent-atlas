# Sources and implementation evidence

## Book-derived pattern

The source is Imran Ahmad, *30 Agents Every AI Engineer Must Build*, Packt, March 2026, Chapter 10. This case uses the retained [content-creation brief](../../agent-library-analysis/agents/17-content-creation.md), [inventory](../../agent-library-analysis/agent-inventory.md), and [foundations](../../agent-library-analysis/foundations.md). The purchased ebook was not reopened during this implementation.

The retained analysis locates researcher, writer, editor, and brand constraints at printed pages 293-296, physical PDF pages 324-327. Campaign orchestration and asset dispatch appear at printed pages 297-302, PDF pages 328-333. The end-to-end campaign and mock analytics appear at printed pages 303-306, PDF pages 334-337.

The analysis identifies a material gap. The sample returns best-effort content after two retries even if validation still fails. Its substring checks do not establish factual support or tone. Mock analytics and a printed recommendation do not demonstrate measured engagement or persistent learning.

This implementation selects a constrained synthetic content grammar and explicit unapproved terminal outcomes. It does not reproduce the book's code, prompts, media dispatcher, or analytics. Source locators are retained-analysis evidence, not fresh verification of the ebook body.

## Current implementation references

Checked on 2026-10-22.

- [Python 3.14 package resources](https://docs.python.org/3.14/library/importlib.resources.html) documents access to packaged non-code data. The case uses fixed resource names, never user-supplied resource paths.
- [Python 3.14 unittest](https://docs.python.org/3.14/library/unittest.html) documents standard-library test discovery. Tests need no separate runtime service.
- [uv distribution builds](https://docs.astral.sh/uv/concepts/projects/build/) distinguishes the build frontend from the backend that selects package contents.
- [Hatch build configuration](https://hatch.pypa.io/latest/config/build/) documents explicit package selection.
- [Hatchling 1.32.4](https://pypi.org/project/hatchling/1.32.4/) documents the selected build backend. This version was also present in the local dependency cache.

The local environment provides CPython 3.14.8 and uv 0.12.23. Build and runtime results belong in the README verification record. Documentation checks alone do not establish compatibility.
