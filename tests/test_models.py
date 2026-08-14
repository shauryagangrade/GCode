from unittest.mock import patch

from gcode.cli import _model_label
from gcode.models import list_all_models, list_free_models


def test_model_label_openrouter_shows_context_and_tools():
    label = _model_label(
        {
            "id": "qwen/qwen3-coder:free",
            "source": "openrouter",
            "context_length": 128000,
            "supports_tools": True,
        }
    )
    assert label == "qwen/qwen3-coder:free  [openrouter] (128k ctx) [tools]"


def test_model_label_openrouter_omits_tools_when_not_advertised():
    label = _model_label(
        {
            "id": "some/model:free",
            "source": "openrouter",
            "context_length": 32000,
            "supports_tools": False,
        }
    )
    assert label == "some/model:free  [openrouter] (32k ctx)"


def test_model_label_openrouter_hides_context_below_1000():
    label = _model_label(
        {
            "id": "tiny/model:free",
            "source": "openrouter",
            "context_length": 500,
            "supports_tools": False,
        }
    )
    assert label == "tiny/model:free  [openrouter]"


def test_model_label_openrouter_shows_fractional_context():
    label = _model_label(
        {
            "id": "vendor/x:free",
            "source": "openrouter",
            "context_length": 32768,
            "supports_tools": False,
        }
    )
    assert label == "vendor/x:free  [openrouter] (32.8k ctx)"


def test_model_label_ollama_shows_size():
    label = _model_label({"id": "ollama/llama3.2", "source": "ollama", "size": "4.7GB"})
    assert label == "ollama/llama3.2  [ollama] (4.7GB)"


def test_model_label_ollama_without_size():
    label = _model_label({"id": "ollama/codegemma", "source": "ollama"})
    assert label == "ollama/codegemma  [ollama]"


SAMPLE_CATALOG = {
    "data": [
        {
            "id": "vendor/a:free",
            "context_length": 128000,
            "supported_parameters": ["temperature", "tools", "tool_choice"],
        },
        {
            "id": "vendor/b:free",
            "context_length": 32000,
            "supported_parameters": ["temperature"],
        },
        {"id": "vendor/paid", "context_length": 64000, "supported_parameters": ["tools"]},
        {"id": "vendor/c:free", "context_length": 0},
    ]
}


@patch("gcode.models.requests.get")
def test_list_free_models_parses_catalog(mock_get):
    mock_get.return_value.raise_for_status.return_value = None
    mock_get.return_value.json.return_value = SAMPLE_CATALOG

    entries, err = list_free_models()
    assert err is None
    # Sorted by id; only :free models included.
    assert [e["id"] for e in entries] == ["vendor/a:free", "vendor/b:free", "vendor/c:free"]
    assert entries[0]["supports_tools"] is True
    assert entries[0]["context_length"] == 128000
    assert entries[1]["supports_tools"] is False
    assert entries[2]["context_length"] == 0
    assert entries[2]["supports_tools"] is False


@patch("gcode.models.is_ollama_running", return_value=True)
@patch("gcode.models.list_free_models", return_value=([], None))
@patch(
    "gcode.models.list_local_models",
    return_value=([{"name": "llama3.2", "size": "4.7GB"}], None),
)
def test_list_all_models_includes_ollama_entries(mock_ollama, _free, _running):
    all_models = list_all_models()
    assert all_models == [{"id": "ollama/llama3.2", "source": "ollama", "size": "4.7GB"}]


@patch("gcode.models.is_ollama_running", return_value=False)
@patch("gcode.models.list_free_models")
def test_list_all_models_passes_through_enrichment(mock_free, _ollama):
    mock_free.return_value = (
        [
            {
                "id": "qwen/qwen3-coder:free",
                "context_length": 128000,
                "supports_tools": True,
            }
        ],
        None,
    )
    all_models = list_all_models()
    assert all_models == [
        {
            "id": "qwen/qwen3-coder:free",
            "source": "openrouter",
            "context_length": 128000,
            "supports_tools": True,
        }
    ]
