#!/usr/bin/env python3
import json, sys
args = sys.argv[1:]
if args and args[0] in {"check", "whoami"}:
    print("ok")
    raise SystemExit(0)
following = "--following" in args
if following:
    data = [
        {"id": "2", "text": "Open source agent runtime v2 released with replayable traces and deterministic tool mocks.", "createdAt": "2026-08-25T17:00:00Z", "author": {"username": "dev", "name": "Dev"}, "likeCount": 12},
        {"id": "3", "text": "A low information reaction", "createdAt": "2026-08-25T16:00:00Z", "author": {"username": "someone", "name": "Someone"}}
    ]
else:
    data = [
        {"id": "1", "text": "New model released with a 1M context window; pricing and eval methodology are linked.", "createdAt": "2026-08-25T18:00:00Z", "author": {"username": "lab", "name": "AI Lab"}, "likeCount": 900, "urls": [{"expandedUrl": "https://example.com/model"}]},
        {"id": "2", "text": "Open source agent runtime v2 released with replayable traces and deterministic tool mocks.", "createdAt": "2026-08-25T17:00:00Z", "author": {"username": "dev", "name": "Dev"}, "likeCount": 12}
    ]
print(json.dumps(data))
