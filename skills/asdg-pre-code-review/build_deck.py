#!/usr/bin/env python3
"""Render a pre-code review outline (Markdown) to a PowerPoint deck with speaker notes."""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT_OUTLINE = 'docs/asdg/00-governance/presentation/outline.md'
CACHE = Path('.asdg/cache/asdg-pre-code-review')
CHROME = ('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', 'google-chrome', 'chromium', 'chromium-browser')
MAX_POINTS = 4
INK, MUTED, ACCENT, GAP = '1F2933', '6B7280', '2563EB', 'B45309'


def parse(text: str) -> tuple[dict, list[dict]]:
    """Return the front matter and the slides of an outline; raise ValueError on a line outside the grammar."""
    meta, slides, section, slide = {}, [], '', None
    lines = text.splitlines()
    if lines and lines[0].strip() == '---':
        end = next((i for i, line in enumerate(lines[1:], 1) if line.strip() == '---'), None)
        if end is None:
            raise ValueError('Front matter is not closed with ---')
        for line in lines[1:end]:
            if line.strip():
                key, _, value = line.partition(':')
                meta[key.strip()] = value.strip()
        lines = lines[end + 1:]
    for number, line in enumerate(lines, 1):
        line = line.rstrip()
        image = re.fullmatch(r'!\[(.*)\]\((.+)\)', line)
        if not line:
            continue
        if line.startswith('## '):
            headline = line[3:].strip()
            slide = {'section': section, 'headline': re.sub(r'^GAP:\s*', '', headline), 'gap': headline.startswith('GAP:'),
                     'points': [], 'image': None, 'caption': '', 'notes': [], 'sources': []}
            slides.append(slide)
        elif line.startswith('# '):
            section, slide = line[2:].strip(), None
        elif slide is None:
            raise ValueError(f'Line {number} is outside a slide: {line}')
        elif line.startswith('- '):
            slide['points'].append(line[2:].strip())
        elif image:
            slide['caption'], slide['image'] = image.group(1).strip(), image.group(2).strip()
        elif line.startswith('>'):
            slide['notes'].append(line[1:].strip())
        elif line.startswith('Source:'):
            slide['sources'] += [item.strip() for item in line[7:].split(',') if item.strip()]
        else:
            raise ValueError(f'Line {number} is not a point, image, note or source: {line}')
    return meta, slides


def validate(meta: dict, slides: list[dict], root: Path) -> list[str]:
    """Return every problem that would make the deck incomplete or misleading."""
    problems = [f'Front matter lacks "{key}"' for key in ('project', 'sprint', 'presenter') if not meta.get(key)]
    if not slides:
        problems.append('The outline has no slides')
    for number, slide in enumerate(slides, 2):
        where = f'Slide {number} "{slide["headline"]}"'
        if not slide['section']:
            problems.append(f'{where}: no "# Subject" line above it')
        if not ' '.join(slide['notes']).strip():
            problems.append(f'{where}: no speaker notes (lines starting with >)')
        if not slide['sources']:
            problems.append(f'{where}: no Source: line')
        if len(slide['points']) > MAX_POINTS:
            problems.append(f'{where}: {len(slide["points"])} points; at most {MAX_POINTS}')
        if not slide['points'] and not slide['image']:
            problems.append(f'{where}: neither points nor an image')
        for path in slide['sources'] + ([slide['image']] if slide['image'] else []):
            if not (root / path).is_file():
                problems.append(f'{where}: file not found: {path}')
    return problems


def svg_size(svg: Path) -> tuple[int, int]:
    head = svg.read_text(errors='replace')[:2000]
    box = re.search(r'viewBox="[\d.\-]+[ ,]+[\d.\-]+[ ,]+([\d.]+)[ ,]+([\d.]+)"', head)
    width, height = re.search(r'<svg[^>]*\swidth="([\d.]+)', head), re.search(r'<svg[^>]*\sheight="([\d.]+)', head)
    if width and height:
        return round(float(width.group(1))), round(float(height.group(1)))
    return (round(float(box.group(1))), round(float(box.group(2)))) if box else (1200, 675)


def to_png(image: Path, cache: Path) -> Path | None:
    """Return a PNG for the image; convert SVG with rsvg-convert or headless Chrome, or return None."""
    if image.suffix.lower() != '.svg':
        return image
    target = cache / (hashlib.sha256(image.read_bytes()).hexdigest()[:16] + '.png')
    if target.is_file():
        return target
    cache.mkdir(parents=True, exist_ok=True)
    width, height = svg_size(image)
    if shutil.which('rsvg-convert'):
        command = ['rsvg-convert', '-z', '2', '-b', 'white', '-o', str(target), str(image)]
    else:
        chrome = next((c for c in CHROME if Path(c).is_file() or shutil.which(c)), None)
        if chrome is None:
            return None
        page = cache / (target.stem + '.html')
        page.write_text(f'<body style="margin:0;background:#fff"><img src="{image.resolve().as_uri()}" '
                        f'style="display:block;width:{width}px;height:{height}px"></body>')
        command = [chrome, '--headless=new', '--disable-gpu', '--hide-scrollbars', '--force-device-scale-factor=2',
                   f'--window-size={width},{height}', f'--screenshot={target}', page.as_uri()]
    done = subprocess.run(command, capture_output=True, timeout=120)
    return target if done.returncode == 0 and target.is_file() else None


def render(meta: dict, slides: list[dict], root: Path, output: Path) -> list[str]:
    """Write the deck and return the images that could not be converted."""
    from PIL import Image
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.util import Inches, Pt

    deck = Presentation()
    deck.slide_width, deck.slide_height = Inches(13.333), Inches(7.5)
    blank, unconverted = deck.slide_layouts[6], []

    def text(slide, left, top, width, height, lines, size, color=INK, bold=False):
        frame = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height)).text_frame
        frame.word_wrap = True
        for index, line in enumerate(lines):
            paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
            run = paragraph.add_run()
            run.text, run.font.size, run.font.bold, run.font.name = line, Pt(size), bold, 'Arial'
            run.font.color.rgb = RGBColor.from_string(color)
            paragraph.space_after = Pt(size * 0.6)

    def bar(slide, color):
        shape = slide.shapes.add_shape(1, 0, 0, Inches(0.25), deck.slide_height)
        shape.fill.solid()
        shape.fill.fore_color.rgb = RGBColor.from_string(color)
        shape.line.fill.background()

    def picture(slide, path, left, top, width, height):
        with Image.open(path) as opened:
            ratio = opened.width / opened.height
        fitted = min(width, height * ratio)
        slide.shapes.add_picture(str(path), Inches(left + (width - fitted) / 2), Inches(top + (height - fitted / ratio) / 2),
                                 width=Inches(fitted))

    title = deck.slides.add_slide(blank)
    bar(title, ACCENT)
    text(title, 0.9, 2.2, 11.5, 1.2, [meta['project']], 44, bold=True)
    text(title, 0.9, 3.4, 11.5, 0.8, ['Pre-code review: ' + meta['sprint']], 26, ACCENT)
    text(title, 0.9, 4.6, 11.5, 1.0, [meta['presenter'], meta.get('date', '')], 18, MUTED)
    title.notes_slide.notes_text_frame.text = meta.get('notes') or (
        f'This is the pre-code review for {meta["project"]}, {meta["sprint"]}. It assembles what the specialists '
        'documented before coding starts. Slides marked GAP show what is missing.')

    for number, item in enumerate(slides, 2):
        slide = deck.slides.add_slide(blank)
        bar(slide, GAP if item['gap'] else ACCENT)
        text(slide, 0.7, 0.35, 11.9, 0.4, [item['section'].upper() + ('  ·  GAP' if item['gap'] else '')], 12,
             GAP if item['gap'] else ACCENT, bold=True)
        text(slide, 0.7, 0.75, 11.9, 1.1, [item['headline']], 30, bold=True)
        png = to_png(root / item['image'], root / CACHE) if item['image'] else None
        if item['image'] and png is None:
            unconverted.append(item['image'])
        wide = png is None or not item['points']
        if item['points']:
            text(slide, 0.7, 2.0, 11.9 if wide else 5.3, 4.3, ['•  ' + point for point in item['points']], 20)
        if png is not None:
            picture(slide, png, 0.7 if wide else 6.3, 2.0, 11.9 if wide else 6.4, 4.0)
            text(slide, 0.7 if wide else 6.3, 6.05, 11.9 if wide else 6.4, 0.4, [item['caption']], 11, MUTED)
        elif item['image']:
            text(slide, 0.7, 6.05, 11.9, 0.4, ['Visual not converted: ' + item['image']], 11, GAP)
        text(slide, 0.7, 6.85, 11.0, 0.4, ['Source: ' + ', '.join(item['sources'])], 9, MUTED)
        text(slide, 12.3, 6.85, 0.7, 0.4, [str(number)], 9, MUTED)
        slide.notes_slide.notes_text_frame.text = '\n'.join(item['notes'])
    output.parent.mkdir(parents=True, exist_ok=True)
    (output.parent / '.gitignore').write_text('*\n')
    deck.save(str(output))
    return unconverted


def report(output: Path) -> bool:
    """Read the saved deck back and print each slide's headline, visual and notes; False if a slide lacks notes."""
    from pptx import Presentation
    complete = True
    for number, slide in enumerate(Presentation(str(output)).slides, 1):
        texts = [shape.text_frame.text for shape in slide.shapes if shape.has_text_frame and shape.text_frame.text]
        notes = slide.notes_slide.notes_text_frame.text if slide.has_notes_slide else ''
        visual = 'visual' if any(shape.shape_type == 13 for shape in slide.shapes) else 'no visual'
        complete = complete and bool(notes.strip())
        print(f'{number:>2}  {(texts[1] if number > 1 else texts[0])[:60]:<60}  {visual:<9}  notes {len(notes)} chars')
    return complete


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='.', help='project root; outline paths are relative to it')
    parser.add_argument('--outline', default=DEFAULT_OUTLINE)
    parser.add_argument('--output', help='default: <outline folder>/build/pre-code-review.pptx')
    parser.add_argument('--check', action='store_true', help='validate the outline and write nothing')
    parser.add_argument('--setup', action='store_true', help='install python-pptx into a private environment, then exit')
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    venv = root / CACHE / 'venv'
    if args.setup:
        subprocess.run([sys.executable, '-m', 'venv', str(venv)], check=True)
        return subprocess.run([str(venv / 'bin/python'), '-m', 'pip', 'install', '--quiet', 'python-pptx']).returncode
    outline = root / args.outline
    if not outline.is_file():
        print(f'Outline not found: {outline}', file=sys.stderr)
        return 2
    try:
        meta, slides = parse(outline.read_text())
    except ValueError as error:
        print(f'{outline}: {error}', file=sys.stderr)
        return 2
    problems = validate(meta, slides, root)
    for problem in problems:
        print('PROBLEM: ' + problem, file=sys.stderr)
    gaps = [slide['headline'] for slide in slides if slide['gap']]
    if problems or args.check:
        print(f'{len(slides)} slides, {len(gaps)} marked GAP, {len(problems)} problems')
        return 1 if problems else 0
    try:
        import pptx  # noqa: F401
    except ImportError:
        private = venv / 'bin/python'
        if private.is_file() and not os.environ.get('ASDG_DECK_CHILD'):
            return subprocess.run([str(private), __file__] + (argv if argv is not None else sys.argv[1:]),
                                  env={**os.environ, 'ASDG_DECK_CHILD': '1'}).returncode
        print('python-pptx is not installed. Run this script once with --setup.', file=sys.stderr)
        return 2
    output = Path(args.output).resolve() if args.output else outline.parent / 'build' / 'pre-code-review.pptx'
    unconverted = render(meta, slides, root, output)
    complete = report(output)
    for name in gaps:
        print('GAP: ' + name)
    for name in unconverted:
        print('VISUAL NOT CONVERTED: ' + name)
    print(f'Wrote {output}')
    return 0 if complete and not unconverted else 1


if __name__ == '__main__':
    sys.exit(main())
