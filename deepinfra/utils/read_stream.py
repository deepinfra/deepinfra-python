from io import BytesIO
import base64

import httpx


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
        """
        response = httpx.get(url, follow_redirects=True)
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
