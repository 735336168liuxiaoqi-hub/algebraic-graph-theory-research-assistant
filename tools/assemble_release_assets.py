"""Assemble the seven release attachments locally from a verified wheel and source candidate."""
import argparse
from email.parser import BytesParser
import hashlib
from io import BytesIO
import json
from pathlib import Path
import posixpath
import re
import tomllib
from urllib.parse import quote, unquote, urlsplit, urlunsplit
from zipfile import ZipFile

from prepare_public_release import PROJECT_NAME


ROOT = Path(__file__).resolve().parents[1]
GUIDES = {
    'INSTALL_CN.md': '使用指南.md',
    'INSTALL_EN.md': 'docs/QUICKSTART.md',
    'LOCAL_TEST_PLAN_zh.md': 'docs/reference/LOCAL_ACCEPTANCE.md',
}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def version_of(data):
    match = re.search(r'''^__version__\s*=\s*["']([0-9A-Za-z.]+)["']\s*$''', data.decode(), re.MULTILINE)
    if not match:
        raise ValueError('No release version in _version.py')
    return match[1]


def standalone_guide(data, path, repository, version):
    def pin(match):
        label, target = match.groups()
        url = urlsplit(target)
        if url.scheme or url.netloc or not url.path:
            return match[0]
        dest = posixpath.normpath(posixpath.join(posixpath.dirname(path), unquote(url.path)))
        if dest.startswith(('/', '../')):
            raise ValueError('Link outside source: ' + target)
        absolute = f'{repository}/blob/v{version}/' + quote(dest)
        return label + '(' + urlunsplit((*urlsplit(absolute)[:3], url.query, url.fragment)) + ')'

    lines = data.decode('utf-8-sig').splitlines(keepends=True)
    fence = None
    for index, line in enumerate(lines):
        marker = re.match(r'^\s*(`{3,}|~{3,})', line)
        if marker:
            if fence is None:
                fence = marker[1]
            elif marker[1].startswith(fence):
                fence = None
        elif fence is None:
            lines[index] = re.sub(r'(!?\[[^\]\n]*\])\(([^\s()]+)\)', pin, line)
    if lines and lines[0].startswith('# '):
        lines.insert(1, f'\n[v{version}]({repository}/tree/v{version})\n')
    return ''.join(lines).encode()


def assemble(source, wheel, evidence, output):
    if output.exists():
        raise FileExistsError('Choose a new release asset directory: ' + str(output))
    version = version_of((ROOT/'graph_research/_version.py').read_bytes())
    basename = f'{PROJECT_NAME}-{version}'
    prefix = basename+'/'
    source_filename = basename+'-source.zip'
    expected_wheel = f'graph_research_assistant-{version}-py3-none-any.whl'
    if source.name != basename+'-source-candidate.zip' or wheel.name != expected_wheel:
        raise ValueError('Expected a source candidate ZIP and wheel for ' + version)
    report = json.loads(evidence.read_text(encoding='utf-8-sig'))
    if report.get('version') != version or any(not isinstance(report.get(key), list) or not report[key]
                                              for key in ('checks', 'limitations')):
        raise ValueError('Evidence must match version and include nonempty checks and limitations lists')
    assets = {source_filename: source.read_bytes(), wheel.name: wheel.read_bytes()}
    with ZipFile(BytesIO(assets[wheel.name])) as package, ZipFile(BytesIO(assets[source_filename])) as candidate:
        manifest = json.loads(candidate.read(prefix+'SOURCE_MANIFEST.json'))
        if manifest['version'] != version or manifest['project'] != PROJECT_NAME:
            raise ValueError('Source manifest does not match the release')
        members = [prefix + name for name in manifest['files']] + [prefix+'SOURCE_MANIFEST.json']
        if sorted(candidate.namelist()) != sorted(members):
            raise ValueError('Unexpected, duplicate or missing source files')
        for name, digest in manifest['files'].items():
            if sha256(candidate.read(prefix+name)) != digest:
                raise ValueError('Source manifest hash mismatch: ' + name)
        metadata = BytesParser().parsebytes(package.read(f'graph_research_assistant-{version}.dist-info/METADATA'))
        if metadata['Version'] != version or metadata['Name'] != 'graph-research-assistant':
            raise ValueError('Wheel metadata does not match the release')
        for name in ('graph_research/_version.py', 'graph_research/_integrity.json'):
            if package.read(name) != candidate.read(prefix+name):
                raise ValueError('Wheel and source disagree: ' + name)
        if version_of(candidate.read(prefix+'graph_research/_version.py')) != version:
            raise ValueError('Candidate _version.py disagrees with the release')
        project = tomllib.loads(candidate.read(prefix+'pyproject.toml').decode())['project']
        repository = project['urls']['Repository'].rstrip('/')
        for filename, path in GUIDES.items():
            assets[filename] = standalone_guide(candidate.read(prefix+path), path, repository, version)
    report['release_tag'] = 'v'+version
    report['assets'] = [{'name': name, 'bytes': len(data), 'sha256': sha256(data)} for name, data in assets.items()]
    assets['RELEASE_VALIDATION.json'] = (json.dumps(report, ensure_ascii=False, indent=2)+'\n').encode()
    assets['SHA256SUMS.txt'] = ''.join(f'{sha256(data)}  {name}\n' for name, data in assets.items()).encode()
    output.mkdir(parents=True, exist_ok=False)
    for name, data in assets.items():
        with (output/name).open('xb') as stream:
            stream.write(data)
    print(f'Assembled {len(assets)} release assets for v{version}: {output}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ('source', 'wheel', 'evidence', 'output'):
        parser.add_argument('--'+option, type=Path, required=True)
    assemble(**vars(parser.parse_args()))


if __name__ == '__main__':
    main()
