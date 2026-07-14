from typing import cast

from deepinfra._utils import tolerant_dataclass
from deepinfra.models.base import BaseModel
from deepinfra.types.embeddings.response import EmbeddingsResponse


class Embeddings(BaseModel):
    """
    @docs Check the available models at https://deepinfra.com/models/embeddings
    """

    def generate(self, body) -> EmbeddingsResponse:
        """
        Generates embeddings.
        :param body:
        :return:
        """
        response = self._post(json=body)
        return cast(EmbeddingsResponse,
                    tolerant_dataclass(EmbeddingsResponse, response.json()))
