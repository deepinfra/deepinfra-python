import json
import unittest

import respx

from deepinfra import TextToImage

model_name = "CompVis/stable-diffusion-v1-4"
api_key = "API KEY"


class TestTextToImage(unittest.TestCase):
    @respx.mock
    def test_generate(self):
        images = ["image data"]
        route = respx.post(
            f"https://api.deepinfra.com/v1/inference/{model_name}"
        ).respond(
            json={
                "request_id": "123",
                "inference_status": None,
                "images": images,
                "nsfw_content_detected": False,
                "seed": "seed",
                "version": "1.0",
                "created_at": "2022-01-01",
            }
        )

        text_to_image = TextToImage(model_name, api_key)
        body = {"text": "Hello, World!"}
        response = text_to_image.generate(body)

        request = route.calls.last.request
        self.assertEqual(
            str(request.url), f"https://api.deepinfra.com/v1/inference/{model_name}"
        )
        self.assertEqual(response.images, images)
        self.assertEqual(request.headers["Authorization"], f"Bearer {api_key}")
        self.assertEqual(json.loads(request.content), body)
