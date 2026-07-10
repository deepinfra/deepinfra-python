"""
    Base class for all models.
"""

import os
from typing import Any, Dict, Optional

import httpx

from deepinfra.clients import DeepInfraClient, RequestSpec
from deepinfra.constants.client import ROOT_URL
from deepinfra.utils.url import URLUtils


class BaseModel:
    """
    Base class for all models
    @param endpoint: The endpoint of the model or the model name.
    @param auth_token: The API key to authenticate the requests.
    """

    def __init__(self, endpoint: str, auth_token: Optional[str] = None) -> None:
        if URLUtils.is_valid_url(endpoint):
            self.endpoint = endpoint
        else:
            self.endpoint = ROOT_URL + endpoint
        self.auth_token = (
            auth_token
            or self._get_auth_token_from_env()
            or self._warn_about_missing_api_key()
        )
        self.client = DeepInfraClient(self.auth_token)

    def _post(
        self,
        *,
        json: Any = None,
        data: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
    ) -> httpx.Response:
        return self.client.request(
            RequestSpec(
                "POST",
                self.endpoint,
                json=json,
                data=data,
                files=files,
                retry_connect=True,
            )
        )

    def _get_auth_token_from_env(self) -> Optional[str]:
        """
        Fetches the API key from the environment.
        @return: The API key.
        """
        return os.getenv("DEEPINFRA_API_KEY")

    def _warn_about_missing_api_key(self) -> str:
        """
        Warns the user about the missing API key.
        @return: An empty string.
        """
        if not self.auth_token:
            print(
                "Warning: No API key provided. "
                "Please provide an API key to authenticate your requests."
            )
        return ""
