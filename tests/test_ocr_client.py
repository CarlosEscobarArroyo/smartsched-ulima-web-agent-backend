from unittest.mock import MagicMock, patch

from app.integrations.ocr import client as ocr_client


def test_detect_document_text_returns_dict() -> None:
    ocr_client._get_client.cache_clear()

    fake_response = MagicMock()
    fake_response.error.message = ""
    fake_response._pb = MagicMock()

    fake_client = MagicMock()
    fake_client.document_text_detection.return_value = fake_response

    expected = {"fullTextAnnotation": {"text": "hola"}}

    with (
        patch.object(ocr_client.vision, "ImageAnnotatorClient", return_value=fake_client),
        patch.object(ocr_client, "MessageToDict", return_value=expected),
    ):
        result = ocr_client.detect_document_text(b"fake-image-bytes")

    assert result == expected
    fake_client.document_text_detection.assert_called_once()


def test_detect_document_text_raises_on_vision_error() -> None:
    ocr_client._get_client.cache_clear()

    fake_response = MagicMock()
    fake_response.error.message = "quota exceeded"

    fake_client = MagicMock()
    fake_client.document_text_detection.return_value = fake_response

    with patch.object(ocr_client.vision, "ImageAnnotatorClient", return_value=fake_client):
        try:
            ocr_client.detect_document_text(b"fake-image-bytes")
        except RuntimeError as exc:
            assert "quota exceeded" in str(exc)
        else:
            raise AssertionError("expected RuntimeError")
