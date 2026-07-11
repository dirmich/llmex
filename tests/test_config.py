from pathlib import Path
from typing import Any

import pytest

from llmex.config import DataConfig, ModelConfig, load_yaml
from llmex.errors import ConfigError

ROOT = Path(__file__).parents[1]


def test_sample_data_config_is_valid() -> None:
    config = load_yaml(ROOT / "configs/data/sample.yaml", DataConfig)
    assert config.dump.date == "20260701"
    assert config.cleaning.min_chars == 20


def test_smoke_model_config_is_valid() -> None:
    config = load_yaml(ROOT / "configs/model/smoke.yaml", ModelConfig)
    assert config.n_heads // config.n_kv_heads == 2


VALID_MODEL: dict[str, Any] = {
    "name": "smoke",
    "vocab_size": 10,
    "max_seq_len": 1,
    "n_layers": 1,
    "d_model": 8,
    "n_heads": 2,
    "n_kv_heads": 1,
    "ffn_hidden_size": 8,
    "dropout": 0.0,
}


@pytest.mark.parametrize(
    "override",
    [
        {"vocab_size": "16000"},
        {"d_model": 7},
        {"unknown": True},
    ],
)
def test_model_config_rejects_invalid_values(tmp_path: Path, override: dict[str, Any]) -> None:
    path = tmp_path / "invalid.yaml"
    values = {**VALID_MODEL, **override}
    import yaml

    path.write_text(yaml.safe_dump(values), encoding="utf-8")
    with pytest.raises(ConfigError, match="설정 검증"):
        load_yaml(path, ModelConfig)


def test_yaml_root_must_be_mapping(tmp_path: Path) -> None:
    path = tmp_path / "list.yaml"
    path.write_text("- 값\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="최상위"):
        load_yaml(path, ModelConfig)
