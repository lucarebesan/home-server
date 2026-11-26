"""Inspect Box's active objects behind rclone's duplicate-path warning."""

from configparser import ConfigParser
from hashlib import sha1
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json
import re
import subprocess

home = Path.home()
state = home / '.local/state'
raw = home / 'box-import'
log = (state / 'box-check.log').read_text(encoding='utf-8')
paths = re.findall(r'NOTICE: (.*): Duplicate object found in source - ignoring', log)

def token():
    config = ConfigParser(interpolation=None)
    config.read(home / '.config/rclone/rclone.conf')
    return json.loads(config['box']['token'])['access_token']

def get_json(url):
    for attempt in range(2):
        try:
            with urlopen(Request(url, headers={'Authorization': 'Bearer ' + token()}), timeout=30) as response:
                return json.load(response)
        except HTTPError as error:
            if error.code != 401 or attempt:
                raise
            subprocess.run([str(home / '.local/bin/rclone'), 'lsd', 'box:'], check=True, capture_output=True)

def children(folder_id):
    entries = []
    offset = 0
    while True:
        query = urlencode({'fields': 'id,name,type,size,sha1', 'limit': 1000, 'offset': offset})
        page = get_json(f'https://api.box.com/2.0/folders/{folder_id}/items?{query}')
        entries.extend(page['entries'])
        offset += len(page['entries'])
        if offset >= page['total_count'] or not page['entries']:
            return entries

results = []
for relative in paths:
    parts = Path(relative).parts
    folder_id = '0'
    for component in parts[:-1]:
        matches = [item for item in children(folder_id) if item['type'] == 'folder' and item['name'] == component]
        if len(matches) != 1:
            raise RuntimeError(f'Folder path ambiguous: {component!r}: {len(matches)} matches')
        folder_id = matches[0]['id']
    matches = [item for item in children(folder_id) if item['type'] == 'file' and item['name'] == parts[-1]]
    local = raw / relative
    local_sha1 = sha1(local.read_bytes()).hexdigest() if local.is_file() else None
    results.append({'path': relative, 'folder_id': folder_id, 'entries': matches,
                    'local_size': local.stat().st_size if local.is_file() else None,
                    'local_sha1': local_sha1})

output = state / 'box-duplicate-audit.json'
output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
output.chmod(0o600)
print(json.dumps({'warnings': len(paths), 'entry_counts': [len(item['entries']) for item in results],
                  'local_matches': [sum(entry.get('sha1', '').lower() == item['local_sha1'] for entry in item['entries']) for item in results],
                  'unique_hashes': [len({entry.get('sha1') for entry in item['entries']}) for item in results]}), flush=True)
