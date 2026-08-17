from unittest.mock import patch

import pytest

import gcode.models as models
from gcode.cli import _model_label
from gcode.models import list_all_models, list_free_models


@pytest.fixture(autouse=True)
def _isolated_catalog_cache(monkeypatch):
    monkeypatch.setattr(models, "_model_catalog_cache", None)


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


@patch("gcode.models.requests.get")
def test_list_free_models_network_error_is_actionable(mock_get):
    import requests
    from gcode.models import list_free_models

    mock_get.side_effect = requests.exceptions.ConnectionError("boom")
    entries, err = list_free_models()
    assert entries == []
    assert "Could not fetch the OpenRouter model list" in err
    assert "internet connection" in err
    assert "boom" in err


@patch("gcode.models.requests.get")
def test_list_free_models_reuses_cache_within_ttl(mock_get):
    mock_get.return_value.raise_for_status.return_value = None
    mock_get.return_value.json.return_value = SAMPLE_CATALOG

    first, err1 = list_free_models()
    second, err2 = list_free_models()

    assert err1 is None and err2 is None
    assert first == second
    assert mock_get.call_count == 1


@patch("gcode.models.requests.get")
def test_list_free_models_refetches_after_ttl_expiry(mock_get):
    mock_get.return_value.raise_for_status.return_value = None
    mock_get.return_value.json.return_value = SAMPLE_CATALOG

    with patch("gcode.models.time.monotonic", return_value=100.0):
        list_free_models(ttl_seconds=1)
    with patch("gcode.models.time.monotonic", return_value=102.0):
        list_free_models(ttl_seconds=1)

    assert mock_get.call_count == 2


@patch("gcode.models.requests.get")
def test_list_free_models_ttl_zero_forces_fresh_fetch(mock_get):
    mock_get.return_value.raise_for_status.return_value = None
    mock_get.return_value.json.return_value = SAMPLE_CATALOG

    list_free_models()
    list_free_models(ttl_seconds=0)

    assert mock_get.call_count == 2


@patch("gcode.models.requests.get")
def test_list_free_models_failure_is_not_cached(mock_get):
    import requests

    mock_get.side_effect = requests.exceptions.ConnectionError("boom")
    entries, err = list_free_models()
    assert entries == []
    assert err is not None

    mock_get.side_effect = requests.exceptions.Timeout("slow")
    _, err2 = list_free_models()

    assert "slow" in err2
    assert mock_get.call_count == 2


def test_resolve_model_id_unknown_suggests_models():
    from gcode.models import resolve_model_id

    _, err = resolve_model_id("gpt-4", [{"id": "qwen/qwen3-coder:free"}])
    assert "Unknown model" in err
    assert "/models" in err


def test_resolve_model_id_accepts_hash_index():
    from gcode.models import resolve_model_id

    models = [{"id": "a/x:free"}, {"id": "b/y:free"}, {"id": "c/z:free"}]
    model_id, err = resolve_model_id("#2", models)
    assert err is None
    assert model_id == "b/y:free"


def test_resolve_model_id_hash_index_out_of_range():
    from gcode.models import resolve_model_id

    models = [{"id": "a/x:free"}]
    model_id, err = resolve_model_id("#9", models)
    assert model_id is None
    assert "Unknown model" in err


def test_resolve_model_id_plain_index_still_works():
    from gcode.models import resolve_model_id

    models = [{"id": "a/x:free"}, {"id": "b/y:free"}]
    model_id, err = resolve_model_id("1", models)
    assert err is None
    assert model_id == "a/x:free"
