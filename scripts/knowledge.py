import json
import re
from html import unescape
from pathlib import Path

SECTIONS = ('schedule', 'problems', 'resources', 'practice')

def passages(root=Path('docs')):
    for section in SECTIONS:
        for file in sorted((root / section).rglob('*.md')):
            content = unescape(file.read_text(encoding='utf-8'))
            title = re.search(r'^# (.+)$', content, re.M)
            if not title:
                continue
            route = file.relative_to(root).with_suffix('.html').as_posix()
            for part in re.split(r'(?=^## )', content, flags=re.M):
                lines = part.strip().splitlines()
                if not lines:
                    continue
                heading = lines[0].lstrip('# ').strip()
                anchor = re.search(r' \{#([\w-]+)\}$', heading)
                path = route + ('#' + anchor[1] if anchor else '')
                heading = heading.split(' {#', 1)[0]
                for start in range(0, len(part), 2100):
                    yield dict(path=path, title=title[1], heading=heading,
                               body=part[start:start + 2350])

if __name__ == '__main__':
    dest = Path('docs/public/knowledge.json')
    dest.parent.mkdir(exist_ok=True)
    dest.write_text(json.dumps(list(passages()), ensure_ascii=False), encoding='utf-8')
