import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import models
import publish


class Response(io.BytesIO):
    def geturl(self):
        return 'https://github.com/upstream/model'


class ModelReleaseTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.revision = 'a' * 40
        (self.root / 'VERSION').write_text('0.1.0\n')
        (self.root / 'docs').mkdir()
        (self.root / 'docs/downloads.md').write_text('Install instructions\n')
        (self.root / 'licenses').mkdir()
        (self.root / 'licenses/upstream.txt').write_text('Upstream license fixture\n')
        (self.root / 'THIRD_PARTY_NOTICES.md').write_text('Attribution fixture\n')
        self.data = {'schemaVersion': 1, 'repository': 'test/models',
                     'uvrSourceSha256': 'b' * 64, 'models': [], 'devices': [], 'unsupported': []}
        self.raw = self.add_model('demucs', 'raw', {'weights.th': b'raw weights'})
        self.zip = self.add_model('intel', 'zip', {'model.xml': b'<xml/>', 'model.bin': b'IR weights'})
        weight = b'RKNN fixture'
        manifest = {'profile': 'uvr-mdxnet-9482-v1', 'target': 'rk3566', 'toolkit': '2.3.2',
                    'sourceSha256': self.data['uvrSourceSha256'], 'size': len(weight),
                    'sha256': hashlib.sha256(weight).hexdigest()}
        self.rknn = self.add_model('rknn', 'zip', {'uvr.rknn': weight,
                                  'manifest.json': json.dumps(manifest).encode()}, experimental=True)
        self.rknn.update(format='rknn', target='rk3566')
        self.data['devices'] = [{'id': 'cpu', 'recommendedModel': 'demucs'}]
        self.save_catalog()

    def add_model(self, identifier, kind, files, experimental=False):
        directory = 'models/' + identifier
        folder = self.root / directory
        folder.mkdir(parents=True)
        specifications = []
        for name, content in files.items():
            (folder / name).write_bytes(content)
            specifications.append({'name': name, 'size': len(content),
                                   'sha256': hashlib.sha256(content).hexdigest()})
        name = next(iter(files)) if kind == 'raw' else identifier + '.zip'
        if experimental:
            name = 'EXPERIMENTAL-' + name
        item = {'id': identifier, 'directory': directory, 'format': 'fixture',
                'description': identifier, 'channel': 'experimental' if experimental else 'stable',
                'files': specifications, 'validation': {'summary': 'fixture'},
                'artifact': {'name': name, 'kind': kind, 'members': list(files)}}
        self.data['models'].append(item)
        return item

    def save_catalog(self):
        (self.root / 'catalog').mkdir(exist_ok=True)
        (self.root / 'catalog/models.lock.json').write_text(json.dumps(self.data))

    def build(self, name='dist'):
        return models.build(self.root, self.data, 'v0.1.0', self.revision, self.root / name)

    def refresh_index(self, folder):
        """Simulate replacing outer hashes; locked inner weights must still be checked."""
        index_path = folder / 'model-catalog.json'
        data = json.loads(index_path.read_text())
        for asset in data['assets']:
            path = folder / asset['name']
            asset.update(size=path.stat().st_size, sha256=models.digest(path))
        index_path.write_text(json.dumps(data))
        models.write_checksums(folder)

    def test_catalog_checks_device_mapping(self):
        self.assertEqual(models.catalog(self.root), self.data)
        self.data['devices'][0]['recommendedModel'] = 'rknn'
        self.save_catalog()
        with self.assertRaisesRegex(ValueError, 'cannot be device defaults'):
            models.catalog(self.root)

    def test_repository_catalog_has_no_bad_quantization_default(self):
        data = models.catalog()
        self.assertEqual(len(data['models']), 6)
        rk3566 = next(d for d in data['devices'] if d['id'] == 'rockchip-rk3566')
        self.assertNotIn('recommendedModel', rk3566)
        self.assertTrue(rk3566['experimentalModel'].endswith('fp16'))
        self.assertIsNone(data['unsupported'][0]['artifact'])
        self.assertFalse(next(m for m in data['models'] if m['precision'] == 'int8')['numericalReferenceCheckPassed'])

    def test_unsafe_names_and_sources_are_rejected(self):
        for change in ('traversal', 'duplicate', 'http', 'source-host', 'unlabeled-experimental'):
            with self.subTest(change=change):
                original = copy.deepcopy(self.data)
                if change == 'traversal':
                    self.raw['directory'] = '../escape'
                elif change == 'duplicate':
                    self.zip['artifact']['name'] = self.raw['artifact']['name']
                elif change == 'http':
                    self.raw['files'][0]['url'] = 'http://github.com/a/b'
                elif change == 'source-host':
                    self.raw['files'][0]['url'] = 'https://unlisted.invalid/model'
                else:
                    self.rknn['artifact']['name'] = 'rknn.zip'
                self.save_catalog()
                with self.assertRaises(ValueError):
                    models.catalog(self.root)
                self.data = original
                self.raw, self.zip, self.rknn = self.data['models']

    def test_symlink_input_is_rejected(self):
        weight = self.root / self.raw['directory'] / 'weights.th'
        outside = self.root / 'other'
        weight.rename(outside)
        weight.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'Symlinks'):
            models.verify(self.root, self.data)

    def test_same_size_weight_corruption_fails(self):
        (self.root / self.raw['directory'] / 'weights.th').write_bytes(b'bad weights')
        with self.assertRaisesRegex(ValueError, 'SHA-256'):
            models.verify(self.root, self.data)

    def test_rknn_target_must_match_even_if_manifest_is_repinned(self):
        path = self.root / self.rknn['directory'] / 'manifest.json'
        data = json.loads(path.read_text())
        data['target'] = 'rk3588'
        path.write_text(json.dumps(data))
        spec = next(f for f in self.rknn['files'] if f['name'] == 'manifest.json')
        spec.update(size=path.stat().st_size, sha256=models.digest(path))
        with self.assertRaisesRegex(ValueError, 'target/source/runtime'):
            models.verify(self.root, self.data)

    def test_download_is_bounded_and_checks_sha(self):
        spec = {'size': 3, 'sha256': hashlib.sha256(b'abc').hexdigest()}
        for index, content in enumerate((b'abcd', b'ab', b'xyz')):
            with self.subTest(content=content), self.assertRaises(ValueError):
                models.copy_checked(io.BytesIO(content), self.root / f'bad-{index}', spec)

    def test_fetch_checks_before_install_and_cleans_failed_attempts(self):
        path = self.root / self.raw['directory'] / 'weights.th'
        original = path.read_bytes()
        path.unlink()
        self.raw['files'][0]['url'] = 'https://github.com/upstream/model'
        with patch.object(models, 'urlopen', side_effect=[Response(b'invalid'), Response(original)]) as request, \
                patch.object(models.time, 'sleep'):
            models.fetch(self.root, self.data)
        self.assertEqual(request.call_count, 2)
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(list(path.parent.glob('.fetch-*')), [])

    def test_fetch_never_overwrites_a_differing_file(self):
        path = self.root / self.raw['directory'] / 'weights.th'
        path.write_bytes(b'keep original local data')
        with patch.object(models, 'urlopen') as request, self.assertRaises(ValueError):
            models.fetch(self.root, self.data)
        request.assert_not_called()
        self.assertEqual(path.read_bytes(), b'keep original local data')

    def test_download_failure_leaves_no_final_or_partial_file(self):
        path = self.root / self.raw['directory'] / 'weights.th'
        path.unlink()
        self.raw['files'][0]['url'] = 'https://github.com/upstream/model'
        with patch.object(models, 'urlopen', side_effect=lambda *a, **k: Response(b'wrong')), \
                patch.object(models.time, 'sleep'), self.assertRaises(ValueError):
            models.fetch(self.root, self.data)
        self.assertFalse(path.exists())
        self.assertEqual(list(path.parent.glob('.fetch-*')), [])

    def test_build_has_flat_compatible_zips_and_notice_asset(self):
        output = self.build()
        models.verify_release(self.root, self.data, 'v0.1.0', output, self.revision)
        with zipfile.ZipFile(output / 'intel.zip') as package:
            self.assertEqual(set(package.namelist()), {'model.xml', 'model.bin'})
        with zipfile.ZipFile(output / 'EXPERIMENTAL-rknn.zip') as package:
            self.assertEqual(set(package.namelist()), {'uvr.rknn', 'manifest.json'})
        self.assertTrue((output / 'MODEL-NOTICES.zip').is_file())
        index = json.loads((output / 'model-catalog.json').read_text())
        self.assertEqual(index['sourceRevision'], self.revision)
        self.assertIn('/releases/download/v0.1.0/', index['assets'][0]['url'])

    def test_build_is_reproducible(self):
        first, second = self.build('first'), self.build('second')
        self.assertEqual({p.name: models.digest(p) for p in first.iterdir()},
                         {p.name: models.digest(p) for p in second.iterdir()})

    def test_build_requires_exact_tag_and_does_not_replace_output(self):
        with self.assertRaises(ValueError):
            models.build(self.root, self.data, 'v9.9.9', self.revision, self.root / 'bad')
        output = self.build()
        with self.assertRaises(FileExistsError):
            self.build()
        self.assertTrue((output / 'weights.th').is_file())

    def test_missing_weight_creates_no_partial_release(self):
        (self.root / self.zip['directory'] / 'model.bin').unlink()
        with self.assertRaises(ValueError):
            self.build()
        self.assertFalse((self.root / 'dist').exists())

    def test_verify_release_does_not_need_installed_upstream_weights(self):
        output = self.build()
        (self.root / self.raw['directory'] / 'weights.th').unlink()
        (self.root / self.zip['directory'] / 'model.bin').unlink()
        models.verify_release(self.root, self.data, 'v0.1.0', output, self.revision)

    def test_missing_asset_and_wrong_commit_are_rejected(self):
        output = self.build()
        with self.assertRaisesRegex(ValueError, 'source tag'):
            models.verify_release(self.root, self.data, 'v0.1.0', output, 'c' * 40)
        (output / 'intel.zip').unlink()
        with self.assertRaisesRegex(ValueError, 'missing or extra'):
            models.verify_release(self.root, self.data, 'v0.1.0', output)

    def test_rehashing_an_extra_zip_member_does_not_bypass_locked_contents(self):
        output = self.build()
        with zipfile.ZipFile(output / 'intel.zip', 'a') as package:
            package.writestr('../unexpected', b'not a model')
        self.refresh_index(output)
        with self.assertRaisesRegex(ValueError, 'Unexpected ZIP'):
            models.verify_release(self.root, self.data, 'v0.1.0', output)

    def test_release_catalog_cannot_change_device_defaults(self):
        output = self.build()
        path = output / 'model-catalog.json'
        data = json.loads(path.read_text())
        data['devices'][0]['recommendedModel'] = 'rknn'
        path.write_text(json.dumps(data))
        models.write_checksums(output)
        with self.assertRaisesRegex(ValueError, 'source tag'):
            models.verify_release(self.root, self.data, 'v0.1.0', output)

    def run_publish(self, remote_change=None, existing=False):
        output = self.build()
        remote = {'draft': True, 'assets': [
            {'name': p.name, 'size': p.stat().st_size, 'state': 'uploaded',
             'digest': 'sha256:' + models.digest(p)} for p in output.iterdir()]}
        if remote_change:
            remote_change(remote)
        replies = [json.dumps([[{'tag_name': 'v0.1.0'}]] if existing else [[]]), '', json.dumps(remote), '']
        env = {'GITHUB_REPOSITORY': 'test/models', 'GITHUB_REF': 'refs/tags/v0.1.0'}
        argv = ['publish.py', '--tag', 'v0.1.0', '--revision', self.revision, '--directory', str(output)]
        with patch.object(publish, 'ROOT', self.root), patch.object(publish, 'catalog', return_value=self.data), \
                patch.dict(publish.os.environ, env), patch.object(sys, 'argv', argv), \
                patch.object(publish, 'gh', side_effect=replies) as calls:
            if existing or remote_change:
                with self.assertRaises(ValueError):
                    publish.main()
            else:
                publish.main()
            return calls.call_args_list

    def test_only_complete_server_uploads_are_published(self):
        calls = self.run_publish()
        self.assertIn('--draft', calls[1].args)
        self.assertIn('--draft=false', calls[-1].args)

    def test_failed_server_digest_never_publishes(self):
        calls = self.run_publish(lambda remote: remote['assets'][0].update(digest='sha256:' + '0' * 64))
        self.assertFalse(any('--draft=false' in call.args for call in calls))

    def test_existing_release_is_never_overwritten(self):
        calls = self.run_publish(existing=True)
        self.assertEqual(len(calls), 1)


if __name__ == '__main__':
    unittest.main()
