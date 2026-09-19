"""URL inputs must fail loudly.

A blob field given as a URL used to be fetched without checking the response,
so a 404 page was uploaded to the API as if it were the file.
"""

import base64

import httpx
import pytest
import respx

from deepinfra import APIConnectionError, APIStatusError, APITimeoutError
from deepinfra.utils.form_data import FormDataUtils
from deepinfra.utils.read_stream import ReadStreamUtils

URL = "https://example.com/audio.mp3"


@respx.mock
def test_url_download_returns_content():
    respx.get(URL).mock(return_value=httpx.Response(200, content=b"audio-bytes"))

    assert ReadStreamUtils.get_read_stream(URL).read() == b"audio-bytes"


@respx.mock
@pytest.mark.parametrize("status", [404, 401, 500])
def test_error_status_raises_instead_of_uploading_the_error_page(status):
    respx.get(URL).mock(return_value=httpx.Response(status, html="<h1>nope</h1>"))

    with pytest.raises(APIStatusError) as exc_info:
        ReadStreamUtils.get_read_stream(URL)

    assert exc_info.value.status_code == status
    assert URL in str(exc_info.value)


@respx.mock
def test_form_data_propagates_the_download_failure():
    respx.get(URL).mock(return_value=httpx.Response(404))

    with pytest.raises(APIStatusError):
        FormDataUtils.get_form_data({"audio": URL}, blob_keys=["audio"])


@respx.mock
def test_connect_error_raises_api_connection_error():
    respx.get(URL).mock(side_effect=httpx.ConnectError("no route"))

    with pytest.raises(APIConnectionError):
        ReadStreamUtils.get_read_stream(URL)


@respx.mock
def test_timeout_raises_api_timeout_error():
    respx.get(URL).mock(side_effect=httpx.ReadTimeout("too slow"))

    with pytest.raises(APITimeoutError):
        ReadStreamUtils.get_read_stream(URL)


def test_bytes_and_base64_inputs_are_unaffected():
    assert ReadStreamUtils.get_read_stream(b"raw").read() == b"raw"

    encoded = base64.b64encode(b"raw").decode()
    data_uri = f"data:audio/mpeg;base64,{encoded}"
    assert ReadStreamUtils.get_read_stream(data_uri).read() == b"raw"


def test_missing_file_still_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        ReadStreamUtils.get_read_stream(str(tmp_path / "absent.wav"))
