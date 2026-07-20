import json
import unittest

import respx

from deepinfra import Embeddings

model_name = "BAAI/bge-large-en-v1.5"
api_key = "API KEY"


class TestEmbeddings(unittest.TestCase):
    @respx.mock
    def test_generate(self):
        route = respx.post(
            f"https://api.deepinfra.com/v1/inference/{model_name}"
        ).respond(
            json={
                "embeddings": [1, 2, 3],
                "input_tokens": 123,
                "inference_status": None,
            }
        )

        embeddings = Embeddings(model_name, api_key)
        body = {"text": "Hello, World!"}
        response = embeddings.generate(body)

        request = route.calls.last.request
        self.assertEqual(
            str(request.url), f"https://api.deepinfra.com/v1/inference/{model_name}"
        )
        self.assertEqual(json.loads(request.content), body)
        self.assertEqual(response.embeddings, [1, 2, 3])
        self.assertEqual(request.headers["Authorization"], f"Bearer {api_key}")
