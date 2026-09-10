"""Regression checks for the immutable-release and draft-resumption boundaries."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import release

class ReleaseTests(unittest.TestCase):
    def fixture(self, root, source='input'):
        out = root / 'dist'
        out.mkdir()
        artifacts = {}
        for name in ('hermesvm.xcframework.zip', 'hermesc-macos-arm64.tar.gz'):
            data = name.encode()
            (out / name).write_bytes(data)
            artifacts[name] = hashlib.sha256(data).hexdigest()
        metadata = {'version': '0.1.0', 'sourceCommit': source, 'artifacts': artifacts}
        (out / 'release.json').write_text(json.dumps(metadata))
        return metadata

    def execute(self, root, metadata, draft=False):
        calls = []
        def run(*args, **kwargs):
            calls.append(args)
            if args == ('git', 'rev-parse', 'HEAD'): return 'input'
            if args[:2] == ('gh', 'api'): return json.dumps([{'tag_name': '0.1.0', 'draft': draft}])
            if args[:3] == ('gh', 'release', 'download'): return ''
            if args[:2] == ('git', 'fetch'): return ''
            if args[:2] == ('git', 'show'):
                return release.manifest('0.1.0', metadata['artifacts']['hermesvm.xcframework.zip']).strip()
            raise AssertionError(f'Unexpected operation, possibly a publication mutation: {args}')
        with patch.object(release, 'ROOT', root), patch.object(release, 'run', run), patch.object(sys, 'argv', ['release.py', '0.1.0']):
            release.main()
        return calls

    def test_published_release_only_verifies(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            metadata = self.fixture(root)
            calls = self.execute(root, metadata)
            self.assertTrue(any(c[:2] == ('git', 'show') for c in calls))
            self.assertFalse((root / 'Package.swift').exists())

    def test_corrupt_published_asset_fails_before_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            metadata = self.fixture(root)
            (root / 'dist/hermesvm.xcframework.zip').write_bytes(b'changed')
            with self.assertRaisesRegex(RuntimeError, 'checksum mismatch'):
                self.execute(root, metadata)

    def test_unrelated_draft_cannot_resume(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            metadata = self.fixture(root, source='other-input')
            with self.assertRaisesRegex(RuntimeError, 'different source'):
                self.execute(root, metadata, draft=True)
            self.assertFalse((root / 'Package.swift').exists())

if __name__ == '__main__':
    unittest.main()
