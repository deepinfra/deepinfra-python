# deepinfra

[![CI](https://github.com/deepinfra/deepinfra-python/actions/workflows/ci.yml/badge.svg)](https://github.com/deepinfra/deepinfra-python/actions/workflows/ci.yml)
[![PyPI version](https://badge.fury.io/py/deepinfra.svg)](https://pypi.org/project/deepinfra/)
[![Python Version](https://img.shields.io/pypi/pyversions/deepinfra.svg)](https://pypi.org/project/deepinfra/)
[![License](https://img.shields.io/github/license/deepinfra/deepinfra-python.svg)](LICENSE)

`deepinfra` is a Python library designed to provide a simple interface for interacting with DeepInfra's Inference API, facilitating various AI and machine learning tasks.

## Installation

To install `deepinfra`, run the following command:

```bash
pip install deepinfra
```

## Examples

### Use Automatic Speech Recognition

You can use the Automatic Speech Recognition (ASR) API to transcribe audio files, URLs and buffer objects.
#### Transcribe an audio file

```python
from deepinfra import AutomaticSpeechRecognition

model_name = "openai/whisper-base"
asr = AutomaticSpeechRecognition(model_name)

file_path = "path/to/audio/file" 
body = {
    "audio": file_path
}
transcription = asr.generate(body)
print(transcription["text"])
```

#### Transcribe an audio URL

```python
from deepinfra import AutomaticSpeechRecognition

model_name = "openai/whisper-base"
asr = AutomaticSpeechRecognition(model_name)

url = "https://path/to/audio/file"
body = {
    "audio": url
}
transcription = asr.generate(body)
print(transcription["text"])
```


