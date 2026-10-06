#!/usr/bin/env python3
from pathlib import Path
import json, os

HERE = Path(__file__).resolve()
JOB_ROOT = HERE.parents[1]

# Search upward first, then sibling directories, to help Codex quickly understand the stack.
candidates = []
for root in [JOB_ROOT.parent, JOB_ROOT]:
    if root.exists():
        candidates.append(root)

markers = {
    "node": ["package.json", "pnpm-lock.yaml", "yarn.lock", "package-lock.json"],
    "nextjs": ["next.config.js", "next.config.mjs", "next.config.ts"],
    "python": ["pyproject.toml", "requirements.txt", "manage.py"],
    "php": ["composer.json", "artisan"],
    "prisma": ["prisma/schema.prisma"],
    "supabase": ["supabase/config.toml"],
    "docker": ["docker-compose.yml", "compose.yml", "Dockerfile"],
}

found = {}
for root in candidates:
    for stack, names in markers.items():
        hits = []
        for name in names:
            p = root / name
            if p.exists():
                hits.append(str(p))
        if hits:
            found.setdefault(stack, []).extend(hits)

print(json.dumps(found, indent=2, ensure_ascii=False))
