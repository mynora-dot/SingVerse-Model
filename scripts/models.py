#!/usr/bin/env python3
"""Fetch, verify and package the models pinned by this repository (Python 3.11+)."""
import argparse
import copy
import hashlib
import json
import re
import shutil
import stat
import sys
import tempfile
import time
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SHA256 = re.compile(r'[0-9a-f]{64}')
FILENAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9._=+-]*')
TAG = re.compile(r'v[0-9]+\.[0-9]+\.[0-9]+(?:-(?:alpha|beta|rc)\.[0-9]+)?')
SOURCE_HOSTS = {'dl.fbaipublicfiles.com', 'huggingface.co', 'zenodo.org', 'github.com'}
SUPPORT_FILES = {'DOWNLOADS.md', 'MODEL-NOTICES.zip', 'model-catalog.json', 'RELEASE-NOTES.md'}


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def safe_path(root, relative):
    value = PurePosixPath(relative)
    if (not relative or '\\' in relative or value.is_absolute() or
            '..' in value.parts or str(value) != relative):
        raise ValueError(f'Unsafe repository path: {relative}')
    root = Path(root).resolve()
    current = root
    for part in value.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f'Symlinks are not model inputs: {relative}')
    return current


def catalog(root=ROOT):
    data = json.loads((root / 'catalog/models.lock.json').read_text())
    if data['schemaVersion'] != 1 or not re.fullmatch(r'[\w.-]+/[\w.-]+', data['repository']):
        raise ValueError('Unsupported catalog or repository')
    identifiers, assets, paths = set(), set(), set()
    for model in data['models']:
        if model['id'] in identifiers:
            raise ValueError('Duplicate model id')
        identifiers.add(model['id'])
        safe_path(root, model['directory'])
        artifact = model['artifact']
        name = artifact['name']
        if not FILENAME.fullmatch(name):
            raise ValueError('Artifact must have a flat filename')
        if name in assets or name in SUPPORT_FILES | {'SHA256SUMS'}:
            raise ValueError('Duplicate or reserved release filename')
        assets.add(name)
        if model['channel'] not in {'stable', 'experimental'}:
            raise ValueError('Unknown model channel')
        if model['channel'] == 'experimental' and not name.startswith('EXPERIMENTAL-'):
            raise ValueError('Experimental assets must be visibly labeled')
        names = set()
        if not model['files']:
            raise ValueError('A distributable model must have pinned files')
        for file in model['files']:
            filename = file['name']
            if not FILENAME.fullmatch(filename):
                raise ValueError('Model files must have flat names')
            path = f"{model['directory']}/{filename}"
            safe_path(root, path)
            if filename in names or path in paths:
                raise ValueError('Duplicate model file')
            names.add(filename)
            paths.add(path)
            if not 0 < file['size'] <= 512 * 1024**2 or not SHA256.fullmatch(file['sha256']):
                raise ValueError('Every model file needs a bounded size and SHA-256')
            if file.get('url'):
                url = urlparse(file['url'])
                if url.scheme != 'https' or url.hostname not in SOURCE_HOSTS:
                    raise ValueError('Model sources must use an approved HTTPS upstream')
        if (not artifact['members'] or len(set(artifact['members'])) != len(artifact['members']) or
                not set(artifact['members']) <= names or artifact['kind'] not in {'raw', 'zip'}):
            raise ValueError('Invalid artifact members')
        if artifact['kind'] == 'raw' and artifact['members'] != [name]:
            raise ValueError('Raw downloads must retain the upstream filename')
    for device in data['devices']:
        for key in ('recommendedModel', 'experimentalModel', 'optionalModel'):
            if device.get(key) and device[key] not in identifiers:
                raise ValueError('Device points to an unknown model')
        recommended = device.get('recommendedModel')
        if recommended and next(m for m in data['models'] if m['id'] == recommended)['channel'] != 'stable':
            raise ValueError('Experimental models cannot be device defaults')
    return data


def check_file(path, expected):
    if not path.is_file() or path.stat().st_size != expected['size'] or digest(path) != expected['sha256']:
        raise ValueError(f"Size/SHA-256 mismatch: {path.name}")


def verify(root, data, bundled=False):
    count = 0
    for model in data['models']:
        for file in model['files']:
            if bundled and file.get('url'):
                continue
            check_file(safe_path(root, f"{model['directory']}/{file['name']}"), file)
            count += 1
        if model['format'] == 'rknn':
            metadata = json.loads(safe_path(root, f"{model['directory']}/manifest.json").read_text())
            weight = next(f for f in model['files'] if f['name'] == 'uvr.rknn')
            if any(metadata.get(key) != value for key, value in {
                    'profile': 'uvr-mdxnet-9482-v1', 'target': model['target'],
                    'toolkit': '2.3.2', 'sourceSha256': data['uvrSourceSha256'],
                    'size': weight['size'], 'sha256': weight['sha256']}.items()):
                raise ValueError(f"RKNN target/source/runtime mismatch: {model['id']}")
    return count


def copy_checked(stream, target, file):
    """Bounded streaming validation; never deserialize model weights."""
    size, checksum = 0, hashlib.sha256()
    with target.open('xb') as output:
        while block := stream.read(1024**2):
            size += len(block)
            if size > file['size']:
                raise ValueError('Downloaded file exceeds its pinned size')
            output.write(block)
            checksum.update(block)
    if size != file['size'] or checksum.hexdigest() != file['sha256']:
        raise ValueError('Downloaded model size/SHA-256 mismatch')


def fetch(root, data):
    for model in data['models']:
        for file in model['files']:
            target = safe_path(root, f"{model['directory']}/{file['name']}")
            if target.exists():
                check_file(target, file)  # Never replace a differing local file.
                continue
            if not file.get('url'):
                raise ValueError(f'Missing checked-in model input: {target}')
            target.parent.mkdir(parents=True, exist_ok=True)
            for attempt in range(3):
                try:
                    with tempfile.TemporaryDirectory(prefix='.fetch-', dir=target.parent) as folder:
                        stage = Path(folder) / file['name']
                        request = Request(file['url'], headers={'User-Agent': 'SingVerse-Model/1'})
                        with urlopen(request, timeout=60) as source:
                            if urlparse(source.geturl()).scheme != 'https':
                                raise ValueError('Refusing a non-HTTPS redirect')
                            copy_checked(source, stage, file)
                        stage.chmod(0o644)
                        # Exclusive link fails instead of overwriting a concurrent installation.
                        target.hardlink_to(stage)
                    print(f"Fetched {model['id']}/{file['name']}", flush=True)
                    break
                except (OSError, ValueError):
                    if attempt == 2:
                        raise
                    time.sleep(2 ** attempt)
    verify(root, data)


def write_zip(destination, members):
    """Stable stored ZIPs, flat model members, fixed timestamps and permissions."""
    with zipfile.ZipFile(destination, 'x', compression=zipfile.ZIP_STORED) as bundle:
        for name, source in sorted(members.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            with source.open('rb') as stream, bundle.open(info, 'w') as output:
                shutil.copyfileobj(stream, output, length=1024**2)


def valid_tag(root, tag):
    if not TAG.fullmatch(tag) or tag != 'v' + (root / 'VERSION').read_text().strip():
        raise ValueError('The tag must be v<VERSION>, e.g. v0.1.0')


def release_notes(data, tag):
    lines = [f'# SingVerse 模型 {tag}', '',
             '按设备下载下表文件；CPU、CUDA、ROCm、MPS 共用同一 HTDemucs 权重。', '',
             '| 文件 | 用途 | 状态 |', '| --- | --- | --- |']
    for model in data['models']:
        lines.append(f"| `{model['artifact']['name']}` | {model['description']} | {model['validation']['summary']} |")
    lines += ['', 'RK3566 FP16 仅通过隔离 CLI 实机验证；正式管理端接入仍待验证。',
              'INT8 伴奏相对 RMS 误差约 41.41%，未通过音质数值检查，仅供研究。',
              'RK3566 + Toolkit2 2.3.2 不支持本次 W4A16 配置，INT4 没有下载文件。',
              'RK3568 / RK3588 尚无本项目板端验证模型；不可复用 RK3566 文件。', '',
              '安装方法见 `DOWNLOADS.md`；下载后按 `SHA256SUMS` 校验。',
              '上游许可证、作者归属和转换记录见 `MODEL-NOTICES.zip`；模型未统一改许可。',
              'GitHub 自动生成的 Source code 压缩包不包含所有上游权重，请选附件。', '']
    return '\n'.join(lines)


def notice_members(root):
    members = {'THIRD_PARTY_NOTICES.md': root / 'THIRD_PARTY_NOTICES.md'}
    for path in sorted((root / 'licenses').rglob('*')):
        if path.is_file():
            relative = path.relative_to(root).as_posix()
            members[relative] = safe_path(root, relative)
    return members


def write_checksums(folder):
    entries = sorted(p for p in folder.iterdir() if p.name != 'SHA256SUMS')
    (folder / 'SHA256SUMS').write_text(''.join(f'{digest(p)}  {p.name}\n' for p in entries))


def build(root, data, tag, revision, output):
    valid_tag(root, tag)
    if not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ValueError('Use the full source commit SHA for release provenance')
    verify(root, data)
    if output.exists():
        raise FileExistsError('Output already exists; use a new directory')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.release-', dir=output.parent) as folder:
        stage = Path(folder)
        for model in data['models']:
            artifact = model['artifact']
            members = {name: safe_path(root, f"{model['directory']}/{name}") for name in artifact['members']}
            if artifact['kind'] == 'raw':
                shutil.copyfile(next(iter(members.values())), stage / artifact['name'])
            else:
                write_zip(stage / artifact['name'], members)
        write_zip(stage / 'MODEL-NOTICES.zip', notice_members(root))
        shutil.copyfile(root / 'docs/downloads.md', stage / 'DOWNLOADS.md')
        (stage / 'RELEASE-NOTES.md').write_text(release_notes(data, tag))
        published = copy.deepcopy(data)
        published.update(tag=tag, sourceRevision=revision, assets=[])
        for path in sorted(stage.iterdir()):
            published['assets'].append({'name': path.name, 'size': path.stat().st_size,
                'sha256': digest(path),
                'url': f"https://github.com/{data['repository']}/releases/download/{tag}/{path.name}"})
        (stage / 'model-catalog.json').write_text(json.dumps(published, ensure_ascii=False, indent=2) + '\n')
        write_checksums(stage)
        verify_release(root, data, tag, stage, revision)
        stage.rename(output)
    return output


def verify_zip(path, expected):
    with zipfile.ZipFile(path) as bundle:
        entries = bundle.infolist()
        if len(entries) != len(expected) or {item.filename for item in entries} != set(expected):
            raise ValueError(f'Unexpected ZIP members: {path.name}')
        for item in entries:
            file = expected[item.filename]
            if item.file_size != file['size'] or item.flag_bits & 1 or stat.S_ISLNK(item.external_attr >> 16):
                raise ValueError('Unsafe or incorrectly sized ZIP member')
            with bundle.open(item) as stream:
                if hashlib.file_digest(stream, 'sha256').hexdigest() != file['sha256']:
                    raise ValueError('ZIP model digest mismatch')


def verify_release(root, data, tag, folder, revision=None):
    valid_tag(root, tag)
    expected = {m['artifact']['name'] for m in data['models']} | SUPPORT_FILES
    if {p.name for p in folder.iterdir()} != expected | {'SHA256SUMS'}:
        raise ValueError('The release has missing or extra assets')
    sums = {}
    for line in (folder / 'SHA256SUMS').read_text().splitlines():
        checksum, name = line.split('  ', 1)
        if not SHA256.fullmatch(checksum) or name in sums or name not in expected:
            raise ValueError('Invalid SHA256SUMS entry')
        sums[name] = checksum
    if set(sums) != expected:
        raise ValueError('Incomplete SHA256SUMS')
    for name, checksum in sums.items():
        path = safe_path(folder, name)
        if digest(path) != checksum:
            raise ValueError(f'Release checksum mismatch: {name}')
    published = json.loads((folder / 'model-catalog.json').read_text())
    if ({k: published[k] for k in data} != data or published['tag'] != tag or
            not re.fullmatch(r'[0-9a-f]{40}', published['sourceRevision']) or
            revision is not None and published['sourceRevision'] != revision):
        raise ValueError('Published catalog differs from the source tag')
    indexed = {a['name']: a for a in published['assets']}
    if len(indexed) != len(published['assets']) or set(indexed) != expected - {'model-catalog.json'}:
        raise ValueError('Incomplete published asset index')
    for name, asset in indexed.items():
        check_file(folder / name, asset)
        if asset['url'] != f"https://github.com/{data['repository']}/releases/download/{tag}/{name}":
            raise ValueError('Unexpected release download URL')
    for model in data['models']:
        artifact = model['artifact']
        members = {f['name']: f for f in model['files'] if f['name'] in artifact['members']}
        if artifact['kind'] == 'raw':
            check_file(folder / artifact['name'], next(iter(members.values())))
        else:
            verify_zip(folder / artifact['name'], members)
    notices = {name: {'size': p.stat().st_size, 'sha256': digest(p)} for name, p in notice_members(root).items()}
    verify_zip(folder / 'MODEL-NOTICES.zip', notices)
    if (folder / 'DOWNLOADS.md').read_bytes() != (root / 'docs/downloads.md').read_bytes():
        raise ValueError('Download instructions differ from this tag')
    if (folder / 'RELEASE-NOTES.md').read_text() != release_notes(data, tag):
        raise ValueError('Release notes differ from this tag')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    command = commands.add_parser('validate', help='Check the lock file and device mappings')
    command.add_argument('--tag', help='Also require an exact VERSION match')
    commands.add_parser('fetch', help='Download pinned upstream weights; keep local models')
    command = commands.add_parser('verify', help='Verify local sizes, hashes and RKNN targets')
    command.add_argument('--bundled', action='store_true', help='Only files checked into Git')
    command = commands.add_parser('build', help='Build all release assets atomically')
    command.add_argument('--tag', required=True)
    command.add_argument('--revision', required=True)
    command.add_argument('--output', type=Path, default=ROOT / 'dist')
    command = commands.add_parser('verify-release', help='Check a release without installed weights')
    command.add_argument('--tag', required=True)
    command.add_argument('--revision')
    command.add_argument('--directory', type=Path, default=ROOT / 'dist')
    args = parser.parse_args()
    data = catalog()
    if args.command == 'validate' and args.tag:
        valid_tag(ROOT, args.tag)
    elif args.command == 'fetch':
        fetch(ROOT, data)
    elif args.command == 'verify':
        print(f'Verified {verify(ROOT, data, args.bundled)} pinned files')
    elif args.command == 'build':
        print(build(ROOT, data, args.tag, args.revision, args.output.resolve()))
    elif args.command == 'verify-release':
        verify_release(ROOT, data, args.tag, args.directory.resolve(), args.revision)
    print('OK:', args.command)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, OSError, zipfile.BadZipFile) as error:
        sys.exit(f'ERROR: {error}')
