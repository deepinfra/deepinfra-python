"""
The automatic speech recognition model.
"""

from typing import cast

from deepinfra._utils import tolerant_dataclass
from deepinfra.models.base import BaseModel
from deepinfra.types.automatic_speech_recognition.response import (
    AutomaticSpeechRecognitionResponse,
)
from deepinfra.utils.form_data import FormDataUtils


class AutomaticSpeechRecognition(BaseModel):
    """
    @docs Check the available models at https://deepinfra.com/models/automatic-speech-recognition
    """

    def generate(self, body) -> AutomaticSpeechRecognitionResponse:
        """
        Generates the automatic speech recognition response.
        @param body: The request body.
        @return: The response.

        """

        fields, files = FormDataUtils.get_form_data(body, blob_keys=["audio"])
        response = self._post(data=fields, files=files)
        return cast(AutomaticSpeechRecognitionResponse,
                    tolerant_dataclass(AutomaticSpeechRecognitionResponse, response.json()))
