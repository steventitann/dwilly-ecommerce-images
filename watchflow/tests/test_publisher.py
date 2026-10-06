import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
from watchflow.publisher import Publisher

class PublishedBytesTests(unittest.TestCase):
    @patch('watchflow.publisher.subprocess.run')
    @patch('requests.get')
    def test_raw_verification_uses_committed_bytes_with_windows_line_endings(self, get, run):
        run.return_value=Mock(returncode=0, stdout=b'{"ok":true}\n')
        get.return_value=Mock(ok=True, content=b'{"ok":true}\n')
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); package=root/'job'; package.mkdir()
            (package/'manifest.json').write_bytes(b'{"ok":true}\r\n')
            Publisher(root,'origin','main').verify(package,'https://raw.githubusercontent.com/test/repo/main/')
            self.assertEqual(get.call_count,1)
            self.assertEqual(run.call_args.args[0][-1],'HEAD:job/manifest.json')
