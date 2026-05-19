import tempfile
import unittest
from pathlib import Path

from auto_register.config import WorkerMailConfig
from auto_register.providers.one_sec_mail_provider import (
    CloudflareWorkerMailProvider,
    _normalize_mail_item,
)


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeClient:
    def __init__(self, post_responses=None, get_responses=None):
        self.post_responses = list(post_responses or [])
        self.get_responses = list(get_responses or [])
        self.posts = []
        self.gets = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url, **kwargs):
        self.posts.append((url, kwargs))
        return self.post_responses.pop(0)

    def get(self, url, **kwargs):
        self.gets.append((url, kwargs))
        return self.get_responses.pop(0)


def make_config(tmp_dir):
    return WorkerMailConfig(
        cf_worker_domain="mail.example.com",
        cf_email_domain=("example.com",),
        cf_admin_password="secret",
        cf_enable_random_subdomain=True,
        accounts_file=Path(tmp_dir) / "accounts.txt",
    )


class WorkerMailProviderTests(unittest.TestCase):
    def test_generate_email_uses_worker_new_address_api(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            client = FakeClient(
                post_responses=[FakeResponse(200, {"address": "new@example.com", "jwt": "mail-token"})]
            )
            provider = CloudflareWorkerMailProvider(
                config=make_config(tmp_dir),
                client_factory=lambda **_: client,
            )

            email = provider.generate_email()

        self.assertEqual(email, "new@example.com")
        self.assertEqual(len(client.posts), 1)
        url, kwargs = client.posts[0]
        self.assertEqual(url, "https://mail.example.com/admin/new_address")
        self.assertEqual(kwargs["headers"]["x-admin-auth"], "secret")
        self.assertEqual(kwargs["json"]["domain"], "example.com")
        self.assertTrue(kwargs["json"]["enablePrefix"])
        self.assertTrue(kwargs["json"]["enableRandomSubdomain"])
        self.assertTrue(kwargs["json"]["name"])

    def test_normalize_mail_item_preserves_subject_source_and_body(self):
        item = _normalize_mail_item(
            {
                "id": "m1",
                "subject": "Activate Qwen",
                "from": {"address": "noreply@example.com"},
                "html": ["<a href='https://example.com/activate'>activate</a>"],
            }
        )

        self.assertEqual(item["id"], "m1")
        self.assertEqual(item["subject"], "Activate Qwen")
        self.assertEqual(item["source"], "noreply@example.com")
        self.assertIn("https://example.com/activate", item["raw"])

    def test_wait_for_activation_link_skips_snapshot_mail(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            client = FakeClient(
                post_responses=[FakeResponse(200, {"address": "new@example.com", "jwt": "mail-token"})],
                get_responses=[
                    FakeResponse(
                        200,
                        {
                            "results": [
                                {
                                    "id": "old",
                                    "subject": "old",
                                    "raw": "old https://example.com/activate?token=old",
                                }
                            ]
                        },
                    ),
                    FakeResponse(
                        200,
                        {
                            "results": [
                                {
                                    "id": "old",
                                    "subject": "old",
                                    "raw": "old https://example.com/activate?token=old",
                                },
                                {
                                    "id": "new",
                                    "subject": "new",
                                    "raw": "new https://example.com/activate?token=new",
                                },
                            ]
                        },
                    ),
                ],
            )
            provider = CloudflareWorkerMailProvider(
                config=make_config(tmp_dir),
                poll_interval=0,
                timeout=1,
                client_factory=lambda **_: client,
                sleep=lambda _: None,
            )
            provider.generate_email()

            url = provider.wait_for_activation_link("new@example.com")

        self.assertEqual(url, "https://example.com/activate?token=new")
        self.assertEqual(client.gets[0][0], "https://mail.example.com/api/mails")
        self.assertEqual(client.gets[0][1]["headers"]["Authorization"], "Bearer mail-token")

    def test_wait_for_activation_link_returns_empty_string_when_stopped(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            client = FakeClient(
                post_responses=[FakeResponse(200, {"address": "new@example.com", "jwt": "mail-token"})],
            )
            provider = CloudflareWorkerMailProvider(
                config=make_config(tmp_dir),
                poll_interval=0,
                timeout=1,
                client_factory=lambda **_: client,
                sleep=lambda _: None,
            )
            provider.generate_email()

            url = provider.wait_for_activation_link("new@example.com", check_stop=lambda: True)

        self.assertEqual(url, "")


if __name__ == "__main__":
    unittest.main()
