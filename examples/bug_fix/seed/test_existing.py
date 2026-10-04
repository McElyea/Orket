"""Layer: end-to-end. Existing checks execute the project's real Python CLI."""
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path


class ExistingTests(unittest.TestCase):
    def label(self, value):
        command = [sys.executable, str(Path(os.environ['LABEL_PROGRAM'])), json.dumps(value)]
        result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=10)
        return json.loads(result.stdout)

    def test_basic(self):
        self.assertEqual(self.label('Hello World'), 'hello-world')

    def test_empty(self):
        self.assertEqual(self.label(''), '')
