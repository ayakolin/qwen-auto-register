import json
import tempfile
import unittest
from pathlib import Path

from auto_register.config import load_worker_mail_config, project_root


class ConfigTests(unittest.TestCase):
    def test_load_worker_mail_config_reads_codexoauthloop_style_fields(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "cf_worker_domain": "mail.example.com",
                        "cf_email_domain": ["example.com", "example.net"],
                        "cf_admin_password": "secret",
                        "cf_enable_random_subdomain": False,
                    }
                ),
                encoding="utf-8",
            )

            config = load_worker_mail_config(config_path)

        self.assertEqual(config.cf_worker_domain, "mail.example.com")
        self.assertEqual(config.cf_email_domain, ("example.com", "example.net"))
        self.assertEqual(config.cf_admin_password, "secret")
        self.assertFalse(config.cf_enable_random_subdomain)

    def test_load_worker_mail_config_rejects_missing_required_field(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "cf_worker_domain": "mail.example.com",
                        "cf_email_domain": ["example.com"],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "cf_admin_password"):
                load_worker_mail_config(config_path)

    def test_project_root_points_to_repository_root(self):
        self.assertTrue((project_root() / "pyproject.toml").exists())


if __name__ == "__main__":
    unittest.main()
