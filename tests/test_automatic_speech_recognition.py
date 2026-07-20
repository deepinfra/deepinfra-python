import unittest

import respx

from deepinfra import AutomaticSpeechRecognition

model_name = "openai/whisper-base"
api_key = "API KEY"


class TestAutomaticSpeechRecognition(unittest.TestCase):
    @respx.mock
    def test_generate(self):
        route = respx.post(
            f"https://api.deepinfra.com/v1/inference/{model_name}"
        ).respond(
            json={
                "text": "Hello, World!",
                "segments": [{"start": 0, "end": 1, "text": "Hello"}],
                "language": "en",
                "input_length_ms": 1000,
                "request_id": "123",
                "inference_status": None,
            }
        )

        audio_data = b"audio data"
        asr = AutomaticSpeechRecognition(model_name, api_key)
        body = {"audio": audio_data}
        response = asr.generate(body)

        request = route.calls.last.request
        self.assertEqual(
            str(request.url), f"https://api.deepinfra.com/v1/inference/{model_name}"
        )
        self.assertEqual(request.headers["Authorization"], f"Bearer {api_key}")
        self.assertIn("multipart/form-data", request.headers["Content-Type"])
        self.assertIn(b"audio data", request.content)
        self.assertEqual(response.text, "Hello, World!")
