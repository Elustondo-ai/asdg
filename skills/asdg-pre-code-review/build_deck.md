# build_deck.py: render an outline to PowerPoint

The script turns one Markdown outline into a `.pptx` with speaker notes. It selects and writes nothing itself: the [Pre-code review skill](SKILL.md) has an agent write the outline, and a person may edit it before rendering.

| Responsibility | Collaborators |
| --- | --- |
| Parse the outline and reject lines outside the format | the outline file |
| Check that each slide has notes, a source and existing files | the project's `docs/asdg/` files |
| Convert SVG visuals to PNG, once per file content | `rsvg-convert`, or Google Chrome in headless mode |
| Lay out the slides and embed the notes | `python-pptx`, Pillow |
| Read the saved deck back and print what each slide holds | the written `.pptx` |

## Run it

```sh
python3 asdg/skills/asdg-pre-code-review/build_deck.py --setup    # once: private environment with python-pptx
python3 asdg/skills/asdg-pre-code-review/build_deck.py --check    # validate only, write nothing
python3 asdg/skills/asdg-pre-code-review/build_deck.py            # render
```

Run from the project root, or pass `--root`. `--outline` defaults to `docs/asdg/00-governance/presentation/outline.md`; `--output` defaults to `build/pre-code-review.pptx` beside the outline.
Exit 0: rendered, or checked clean. Exit 1: outline problems, a slide without notes, or a visual not converted. Exit 2: no outline, a line outside the format, or `python-pptx` missing.
`--setup` creates `.asdg/cache/asdg-pre-code-review/venv` and installs `python-pptx` from the Python package index. A later run that cannot import it restarts itself inside that environment.

## Outline format

```markdown
---
project: Alice.Good.Meetings
sprint: SPRINT-003: new page layout
presenter: Pablo Elustondo
date: 18 November 2026
---

# Purpose

## Brief visual cues that protect his attention
- Regulate delivery: know when to slow down, pause or conclude
> Speaker notes, one or more lines, each starting with >.
Source: docs/asdg/02-purpose/01-purpose.md

## GAP: No context study exists
- Looked in the Context folder: only a README
> What is missing and who owns filling it.
Source: docs/asdg/01-context-and-domain-analysis/README.md
```

`project`, `sprint` and `presenter` are required; `date` and `notes` (title-slide notes) are optional. `# ` names the subject shown above each following slide. `## ` starts a slide; the prefix `GAP: ` marks it in amber.
A slide takes up to four `- ` points, one image line written as in ordinary Markdown (exclamation mark, caption in square brackets, path in round brackets), `> ` notes and a `Source:` line of comma-separated paths. Paths are relative to the project root. Any other line stops the run with its line number.

## Functions

`parse(text)` returns the front matter and the slide list. `validate(meta, slides, root)` returns the problems as sentences. `to_png(image, cache)` returns a PNG path or `None`. `render(meta, slides, root, output)` writes the deck and returns the visuals it could not convert. `report(output)` prints one line per slide and returns whether all have notes. `main(argv)` returns the exit code.
[Tests](../../tests/test_pre_code_review.md) cover parsing and validation without `python-pptx`; rendering is checked only when it is installed.
