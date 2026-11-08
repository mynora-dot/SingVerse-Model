#!/usr/bin/env python3
"""Publish a complete checked release using the GitHub Actions token."""
import argparse
import json
import os
from pathlib import Path
import subprocess

from models import ROOT, catalog, digest, verify_release


def gh(*args):
    return subprocess.check_output(['gh', *args], text=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--revision', required=True)
    parser.add_argument('--directory', type=Path, required=True)
    args = parser.parse_args()
    data = catalog()
    repository = os.environ['GITHUB_REPOSITORY']
    if repository != data['repository'] or os.environ.get('GITHUB_REF') != f'refs/tags/{args.tag}':
        raise ValueError('Release publication must run on this repository tag')
    verify_release(ROOT, data, args.tag, args.directory, args.revision)
    # An existing release (including a failed draft) is never overwritten.
    releases = json.loads(gh('api', '--paginate', '--slurp', f'repos/{repository}/releases?per_page=100'))
    if any(release['tag_name'] == args.tag for page in releases for release in page):
        raise ValueError('Release already exists; inspect it and use a new version')
    assets = sorted(args.directory.iterdir())
    gh('release', 'create', args.tag, *(str(path) for path in assets),
       '--repo', repository, '--draft', '--verify-tag', '--title', f'SingVerse 模型 {args.tag}',
       '--notes-file', str(args.directory / 'RELEASE-NOTES.md'))
    release = json.loads(gh('api', f'repos/{repository}/releases/tags/{args.tag}'))
    remote = {asset['name']: asset for asset in release['assets']}
    if not release['draft'] or set(remote) != {p.name for p in assets} or len(remote) != len(release['assets']):
        raise ValueError('Remote draft is incomplete; it will remain unpublished')
    for path in assets:
        asset = remote[path.name]
        if asset['size'] != path.stat().st_size or asset['state'] != 'uploaded':
            raise ValueError('Remote asset upload is incomplete; draft remains unpublished')
        if asset.get('digest') and asset['digest'] != 'sha256:' + digest(path):
            raise ValueError('Remote asset digest mismatch; draft remains unpublished')
    gh('release', 'edit', args.tag, '--repo', repository, '--draft=false', '--verify-tag',
       '--prerelease' if '-' in args.tag else '--latest')
    print(f"Published https://github.com/{repository}/releases/tag/{args.tag}")


if __name__ == '__main__':
    main()
