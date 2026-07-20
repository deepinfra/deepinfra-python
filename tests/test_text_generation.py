import json
import unittest

import respx

from deepinfra.models.base.text_generation import TextGeneration

model_name = "mistralai/Mistral-7B-Instruct-v0.2"
api_key = "API KEY"


class TestTextGeneration(unittest.TestCase):
    @respx.mock
    def test_generate(self):
        route = respx.post(
            f"https://api.deepinfra.com/v1/inference/{model_name}"
        ).respond(
            json={
                "results": [],
                "num_tokens": 0,
                "num_input_tokens": 0,
                "inference_status": None,
            }
        )

        text_generation = TextGeneration(model_name, api_key)
        body = {"text": "Hello, World!"}
        response = text_generation.generate(body)

        request = route.calls.last.request
        self.assertEqual(
            str(request.url), f"https://api.deepinfra.com/v1/inference/{model_name}"
        )
        self.assertEqual(response.results, [])
        self.assertEqual(request.headers["Authorization"], f"Bearer {api_key}")
        self.assertEqual(json.loads(request.content), body)


class TestSchemaDrift(unittest.TestCase):
    @respx.mock
    def test_extra_and_missing_response_fields_tolerated(self):
        respx.post(f"https://api.deepinfra.com/v1/inference/{model_name}").respond(json={
            "results": [{"generated_text": "hi"}],
            "request_id": "new-field-2026",
            "another_new_field": {"x": 1},
            # num_tokens / num_input_tokens / inference_status absent
        })
        response = TextGeneration(model_name, api_key).generate({"input": "x"})
        self.assertEqual(response.results[0]["generated_text"], "hi")
        self.assertIsNone(response.num_tokens)
        self.assertIsNone(response.inference_status)


def test_missing_api_key_warns_instead_of_crashing(monkeypatch, capsys):
    # Regression: 0.2.0 briefly raised AttributeError here because the
    # env-lookup no longer assigned self.auth_token before the warning read it.
    monkeypatch.delenv("DEEPINFRA_API_KEY", raising=False)
    model = TextGeneration(model_name)
    assert model.auth_token == ""
    assert "No API key provided" in capsys.readouterr().out
