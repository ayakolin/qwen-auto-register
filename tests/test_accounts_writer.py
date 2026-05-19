import tempfile
import unittest
from pathlib import Path

from auto_register.writer.accounts_writer import append_account


class AccountsWriterTests(unittest.TestCase):
    def test_append_account_writes_email_password_line(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "accounts.txt"

            result = append_account("user@example.com", "Password123", path=path)

            self.assertEqual(result, path)
            self.assertEqual(path.read_text(encoding="utf-8"), "user@example.com:Password123\n")

    def test_append_account_does_not_overwrite_existing_lines(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "accounts.txt"

            append_account("first@example.com", "First123", path=path)
            append_account("second@example.com", "Second123", path=path)

            self.assertEqual(
                path.read_text(encoding="utf-8"),
                "first@example.com:First123\nsecond@example.com:Second123\n",
            )

    def test_append_account_creates_parent_directories(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "nested" / "accounts.txt"

            append_account("user@example.com", "Password123", path=path)

            self.assertTrue(path.exists())


if __name__ == "__main__":
    unittest.main()
