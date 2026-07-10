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
