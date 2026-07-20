from typing import Any, Dict, List, Optional, Tuple

from deepinfra.utils.read_stream import ReadStreamUtils


class FormDataUtils:
    """
    Utilities for creating form data.

    """

    @staticmethod
    def get_form_data(
        data: dict, blob_keys: Optional[List[str]] = None
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Splits the data into httpx multipart (fields, files).
        :param data:
        :param blob_keys:
        :return:
        """
        if blob_keys is None:
            blob_keys = list()
        fields: Dict[str, Any] = {}
        files: Dict[str, Any] = {}

        for key, value in data.items():
            if key in blob_keys:
                files[key] = (key, ReadStreamUtils.get_read_stream(value))
            else:
                fields[key] = value

        return fields, files
