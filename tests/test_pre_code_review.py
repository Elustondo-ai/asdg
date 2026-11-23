"""Pre-code review skill: outline parsing, validation, rendering when python-pptx is present, and packaging."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

CORE = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(CORE / 'scripts/lib'))
sys.path.insert(0, str(CORE / 'skills/asdg-pre-code-review'))
import build_deck
from cli_clients import skill_names
from distribution_files import package_files

OUTLINE = """---
project: Demo
sprint: SPRINT-001: first
presenter: A Person
---

# Purpose

## Why it exists
- One point
![A picture](docs/pic.png)
> Spoken notes.
> Second line.
Source: docs/purpose.md, docs/other.md

# Context

## GAP: Nothing written
- Looked in the folder
> Missing.
Source: docs/purpose.md
"""


class PreCodeReviewTests(unittest.TestCase):
    def test_parse_reads_front_matter_subjects_slides_and_gaps(self):
        meta, slides = build_deck.parse(OUTLINE)
        self.assertEqual(meta, {'project': 'Demo', 'sprint': 'SPRINT-001: first', 'presenter': 'A Person'})
        self.assertEqual([(s['section'], s['headline'], s['gap']) for s in slides],
                         [('Purpose', 'Why it exists', False), ('Context', 'Nothing written', True)])
        self.assertEqual(slides[0]['notes'], ['Spoken notes.', 'Second line.'])
        self.assertEqual(slides[0]['sources'], ['docs/purpose.md', 'docs/other.md'])
        self.assertEqual((slides[0]['caption'], slides[0]['image']), ('A picture', 'docs/pic.png'))

    def test_parse_rejects_a_line_outside_the_format(self):
        with self.assertRaisesRegex(ValueError, 'Line 3'):
            build_deck.parse('# Purpose\n## Slide\nloose prose\n')
        with self.assertRaisesRegex(ValueError, 'outside a slide'):
            build_deck.parse('# Purpose\n- point before any slide\n')

    def test_validate_names_missing_notes_sources_files_and_front_matter(self):
        with tempfile.TemporaryDirectory() as folder:
            meta, slides = build_deck.parse('# S\n## Bare\n- p\n## Many\n- 1\n- 2\n- 3\n- 4\n- 5\n> n\nSource: gone.md\n')
            problems = '\n'.join(build_deck.validate(meta, slides, Path(folder)))
        for expected in ('lacks "project"', 'lacks "presenter"', '"Bare": no speaker notes', '"Bare": no Source',
                         '5 points', 'file not found: gone.md'):
            self.assertIn(expected, problems)

    def test_a_complete_outline_validates_clean_and_check_writes_nothing(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'docs').mkdir()
            for name in ('purpose.md', 'other.md', 'pic.png'):
                (root / 'docs' / name).write_bytes(b'x')
            (root / 'outline.md').write_text(OUTLINE)
            self.assertEqual(build_deck.validate(*build_deck.parse(OUTLINE), root), [])
            self.assertEqual(build_deck.main(['--root', folder, '--outline', 'outline.md', '--check']), 0)
            self.assertFalse((root / 'build').exists())

    @unittest.skipUnless(importlib.util.find_spec('pptx'), 'python-pptx is not installed in this interpreter')
    def test_render_embeds_notes_on_every_slide(self):
        from pptx import Presentation
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'docs').mkdir()
            (root / 'docs/purpose.md').write_text('x')
            text = OUTLINE.replace('![A picture](docs/pic.png)\n', '').replace(', docs/other.md', '')
            build_deck.render(*build_deck.parse(text), root, root / 'out/deck.pptx')
            slides = list(Presentation(str(root / 'out/deck.pptx')).slides)
            self.assertEqual(len(slides), 3)
            self.assertTrue(all(slide.notes_slide.notes_text_frame.text.strip() for slide in slides))
            self.assertEqual((root / 'out/.gitignore').read_text(), '*\n')

    def test_the_skill_is_packaged_indexed_and_has_an_adapter_template(self):
        packaged = {path.relative_to(CORE).as_posix() for path in package_files(CORE)}
        for name in ('skills/asdg-pre-code-review/SKILL.md', 'skills/asdg-pre-code-review/build_deck.py',
                     'skills/asdg-pre-code-review/build_deck.md', 'templates/.agents/skills/asdg-pre-code-review/SKILL.md',
                     'templates/.agents/skills/asdg-pre-code-review/agents/openai.yaml',
                     'tests/test_pre_code_review.py', 'tests/test_pre_code_review.md'):
            self.assertIn(name, packaged)
        self.assertIn('asdg-pre-code-review', skill_names(CORE.parent))
        self.assertIn('asdg-pre-code-review/SKILL.md', (CORE / 'skills/README.md').read_text())
        self.assertIn('asdg-pre-code-review/SKILL.md', (CORE / 'skills/asdg-help/SKILL.md').read_text())


if __name__ == '__main__':
    unittest.main()
