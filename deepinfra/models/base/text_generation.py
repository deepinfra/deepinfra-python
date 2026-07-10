"""
    This module contains the TextGeneration class,
    which is the base class for all text generation models.
"""

from deepinfra.models.base import BaseModel
from deepinfra.types.text_generation.response import TextGenerationResponse


class TextGeneration(BaseModel):
    """
    Initializes one of the DeepInfra text generation models.
    @docs Check the available models at https://deepinfra.com/models/text-generation
    """

    def generate(self, body: dict) -> TextGenerationResponse:
        """
        Generates text.
        :param body:
        :return:
        """
        response = self._post(json=body)
        return TextGenerationResponse(**response.json())
