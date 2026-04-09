import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mdtomd.llm import create_llm_client, resolve_runtime_config


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeSDKResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def model_dump(self, mode: str = "json") -> dict:
        return dict(self._payload)


class _FakeSDKStream:
    def __init__(self, payload: dict) -> None:
        self._response = _FakeSDKResponse(payload)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def __iter__(self):
        return iter(())

    def get_final_response(self):
        return self._response


class LLMTests(TestCase):
    @staticmethod
    def _fake_jwt(exp: int = 4102444800) -> str:
        def _encode(part: dict) -> str:
            raw = json.dumps(part, separators=(",", ":")).encode("utf-8")
            import base64

            return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")

        return f"{_encode({'alg': 'none', 'typ': 'JWT'})}.{_encode({'exp': exp})}.sig"

    def test_resolve_runtime_config_prefers_auto_detected_provider(self) -> None:
        with mock.patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}, clear=False):
            config = resolve_runtime_config(provider="auto")

        self.assertEqual(config.provider, "openai")
        self.assertEqual(config.transport, "openai_chat")

    def test_auto_provider_rejects_ambiguous_direct_api_key(self) -> None:
        with self.assertRaises(ValueError):
            resolve_runtime_config(provider="auto", api_key="sk-test")

    def test_openai_responses_transport_is_selected_for_gpt5(self) -> None:
        with mock.patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}, clear=False):
            config = resolve_runtime_config(provider="openai", model="gpt-5")

        self.assertEqual(config.transport, "openai_responses")

    def test_openai_codex_reads_token_from_codex_home(self) -> None:
        with TemporaryDirectory() as temp_dir:
            codex_home = Path(temp_dir)
            (codex_home / "auth.json").write_text(
                json.dumps(
                    {
                        "tokens": {
                            "access_token": self._fake_jwt(),
                            "refresh_token": "refresh-token",
                        }
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch.dict("os.environ", {"CODEX_HOME": str(codex_home)}, clear=False):
                config = resolve_runtime_config(provider="openai-codex")

        self.assertEqual(config.provider, "openai-codex")
        self.assertEqual(config.transport, "openai_responses")
        self.assertEqual(config.base_url, "https://chatgpt.com/backend-api/codex")

    def test_openai_codex_reads_token_from_explicit_auth_file(self) -> None:
        with TemporaryDirectory() as temp_dir:
            auth_path = Path(temp_dir) / "custom-auth.json"
            auth_path.write_text(
                json.dumps(
                    {
                        "tokens": {
                            "access_token": self._fake_jwt(),
                            "refresh_token": "refresh-token",
                        }
                    }
                ),
                encoding="utf-8",
            )
            config = resolve_runtime_config(provider="openai-codex", auth_file=str(auth_path))

        self.assertEqual(config.provider, "openai-codex")
        self.assertEqual(config.transport, "openai_responses")
        self.assertEqual(config.base_url, "https://chatgpt.com/backend-api/codex")

    def test_openai_chat_request_is_parsed(self) -> None:
        client = create_llm_client(provider="openai-compatible", model="qwen", base_url="http://localhost:8000/v1", api_key="test-key")
        payload = {
            "model": "qwen",
            "choices": [
                {
                    "message": {"content": "译文"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 11, "total_tokens": 21},
        }

        with mock.patch("mdtomd.llm.client.request.urlopen", return_value=_FakeResponse(payload)) as urlopen:
            response = client.chat([{"role": "user", "content": "hello"}])

        self.assertEqual(response.content, "译文")
        req = urlopen.call_args.args[0]
        self.assertTrue(req.full_url.endswith("/chat/completions"))

    def test_openai_codex_request_uses_minimal_responses_payload(self) -> None:
        client = create_llm_client(provider="openai-codex", api_key="codex-token", model="gpt-5.4-mini")
        sdk_payload = {
            "model": "gpt-5.4-mini",
            "output_text": "译文",
            "usage": {"input_tokens": 9, "output_tokens": 12, "total_tokens": 21},
            "status": "completed",
        }

        fake_client = mock.Mock()
        fake_client.responses.stream.return_value = _FakeSDKStream(sdk_payload)
        with mock.patch("mdtomd.llm.client._create_openai_sdk_client", return_value=fake_client) as create_client:
            response = client.chat([{"role": "user", "content": "hello"}], system="system")

        self.assertEqual(response.content, "译文")
        create_client.assert_called_once()
        kwargs = fake_client.responses.stream.call_args.kwargs
        self.assertEqual(kwargs["instructions"], "system")
        self.assertEqual(kwargs["store"], False)
        self.assertEqual(kwargs["input"], [{"role": "user", "content": "hello"}])
        self.assertNotIn("temperature", kwargs)
        self.assertNotIn("max_output_tokens", kwargs)

    def test_anthropic_request_is_parsed(self) -> None:
        client = create_llm_client(provider="anthropic", api_key="test-key", model="claude-3-5-sonnet-latest")
        payload = {
            "model": "claude-3-5-sonnet-latest",
            "content": [{"type": "text", "text": "译文"}],
            "usage": {"input_tokens": 12, "output_tokens": 18},
            "stop_reason": "end_turn",
        }

        with mock.patch("mdtomd.llm.client.request.urlopen", return_value=_FakeResponse(payload)) as urlopen:
            response = client.chat([{"role": "user", "content": "hello"}], system="system")

        self.assertEqual(response.content, "译文")
        req = urlopen.call_args.args[0]
        self.assertTrue(req.full_url.endswith("/v1/messages"))

