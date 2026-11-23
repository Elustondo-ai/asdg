# Pre-code review skill tests

These tests check [build_deck.py](../skills/asdg-pre-code-review/build_deck.md), the script behind the [Pre-code review skill](../skills/asdg-pre-code-review/SKILL.md), and that the skill is packaged.

| Test | What it shows |
| --- | --- |
| `test_parse_reads_front_matter_subjects_slides_and_gaps` | An outline becomes front matter and slides, with subject, notes, sources, image and the GAP mark |
| `test_parse_rejects_a_line_outside_the_format` | Loose prose, or a point before any slide, stops with its line number |
| `test_validate_names_missing_notes_sources_files_and_front_matter` | Each kind of incomplete slide is named in a sentence |
| `test_a_complete_outline_validates_clean_and_check_writes_nothing` | `--check` exits 0 and creates no build folder |
| `test_render_embeds_notes_on_every_slide` | The saved deck has a title slide plus one slide per outline entry, all with notes |
| `test_the_skill_is_packaged_indexed_and_has_an_adapter_template` | The files are in the package list, the skill index, Help and the adapter templates |

## Fixtures

`OUTLINE` is a two-slide outline: one ordinary slide with an image and one GAP slide. Tests that need files create them in a temporary folder; no project document is read.

## Run

```sh
cd asdg && python3 -B -m unittest tests.test_pre_code_review -v
```

The render test is skipped when the interpreter has no `python-pptx`. To include it, use the private environment that `build_deck.py --setup` creates:

```sh
cd asdg && ../.asdg/cache/asdg-pre-code-review/venv/bin/python -B -m unittest tests.test_pre_code_review -v
```

## Limits

The tests check structure, not appearance: no test opens the deck in PowerPoint, and none converts an SVG. They cannot tell whether a slide is faithful to its source.
