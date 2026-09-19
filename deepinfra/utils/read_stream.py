from io import BytesIO
import base64

import httpx

from deepinfra._exceptions import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
)

DOWNLOAD_TIMEOUT = 30.0


class ReadStreamUtils:
    """
    Utility class for working with files.
    """

    @staticmethod
    def buffer_to_stream(buffer):
        """
        Creates a BytesIO from a Buffer.
        :param buffer: The Buffer to be streamed.
        :return: A BinaryIO object.
        """
        return BytesIO(buffer)

    @staticmethod
    def file_to_stream(filename):
        """
        Creates a BytesIO from a file path.
        :param file_path: The path to the image file.
        :return: A BinaryIO of the file contents.
        """
        with open(filename, "rb") as file:
            return BytesIO(file.read())

    @staticmethod
    def url_to_stream(url):
        """
        Downloads an image from a URL and returns it as a BytesIO.
        :param url: The URL of the image.
        :return: A BytesIO containing the image data.
        :raises APIStatusError: the URL answered with an error status. Without
            this the error page's bytes would be uploaded as the file.
        :raises APIConnectionError: the download never got a response.
        """
        try:
            response = httpx.get(
                url, follow_redirects=True, timeout=DOWNLOAD_TIMEOUT
            )
        except httpx.TimeoutException as exc:
            raise APITimeoutError(f"Timed out downloading {url}") from exc
        except httpx.TransportError as exc:
            raise APIConnectionError(f"Failed to download {url}: {exc}") from exc
        if response.is_error:
            raise APIStatusError(
                f"Failed to download {url}",
                status_code=response.status_code,
                response=response,
            )
        return BytesIO(response.content)

    @staticmethod
    def base64_to_stream(base64_string):
        """
        Converts a Base64 string to a BytesIO.
        :param base64_string: The Base64 string to be converted.
        :return: A BytesIO of the image data.
        """
        image_data = base64.b64decode(base64_string)
        return BytesIO(image_data)

    @staticmethod
    def get_read_stream(input_data):
        """
        Returns a BytesIO from an object.
        The object can be a Buffer, a file path, or a URL.
        :param input_data: The input data.
        :return: A BytesIO of the image data.
        """
        if isinstance(input_data, bytes):
            return ReadStreamUtils.buffer_to_stream(input_data)
        elif isinstance(input_data, str):
            if input_data.startswith("http"):
                return ReadStreamUtils.url_to_stream(input_data)
            elif input_data.startswith("data"):
                base64_data = input_data.split(",")[1]
                return ReadStreamUtils.base64_to_stream(base64_data)
            else:
                return ReadStreamUtils.file_to_stream(input_data)
        else:
            raise ValueError("Invalid input type")
