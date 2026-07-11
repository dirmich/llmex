import json
import math
from pathlib import Path

import pytest
import torch
from hypothesis import given, settings
from hypothesis import strategies as st
from torch.nn import functional as F
from typer.testing import CliRunner

from llmex.cli import app
from llmex.config import ModelConfig
from llmex.model import CausalLM, GenerationConfig
from llmex.model.attention import GroupedQueryAttention
from llmex.model.norm import RMSNorm
from llmex.model.rope import RotaryEmbedding

ROOT = Path(__file__).parents[1]


def tiny_config(**overrides: object) -> ModelConfig:
    values: dict[str, object] = {
        "name": "tiny",
        "vocab_size": 31,
        "max_seq_len": 16,
        "n_layers": 2,
        "d_model": 16,
        "n_heads": 4,
        "n_kv_heads": 2,
        "ffn_hidden_size": 32,
        "dropout": 0.0,
    }
    values.update(overrides)
    return ModelConfig.model_validate(values)


def test_rmsnorm_matches_equation_and_has_finite_gradient() -> None:
    inputs = torch.tensor([[[1.0, -2.0, 3.0, -4.0]]], requires_grad=True)
    norm = RMSNorm(4, eps=1e-6)
    actual = norm(inputs)
    expected = inputs * torch.rsqrt(inputs.square().mean(dim=-1, keepdim=True) + 1e-6)
    torch.testing.assert_close(actual, expected)
    actual.square().sum().backward()
    assert inputs.grad is not None and bool(torch.isfinite(inputs.grad).all())


def test_rope_matches_manual_rotation_and_offset() -> None:
    rope = RotaryEmbedding(4, 8, theta=10.0)
    value = torch.tensor([[[[1.0, 2.0, 3.0, 4.0]]]])
    actual = rope(value, offset=2)
    angles = torch.tensor([2.0, 2.0 / math.sqrt(10.0)])
    expected = torch.tensor(
        [
            [
                [
                    [
                        math.cos(angles[0]) - 2 * math.sin(angles[0]),
                        math.sin(angles[0]) + 2 * math.cos(angles[0]),
                        3 * math.cos(angles[1]) - 4 * math.sin(angles[1]),
                        3 * math.sin(angles[1]) + 4 * math.cos(angles[1]),
                    ]
                ]
            ]
        ]
    )
    torch.testing.assert_close(actual, expected)
    cached_cos, _ = rope.cos_sin(1, offset=2, device=value.device, dtype=value.dtype)
    rope(value, offset=3)
    next_cos, _ = rope.cos_sin(1, offset=2, device=value.device, dtype=value.dtype)
    assert cached_cos.untyped_storage().data_ptr() == next_cos.untyped_storage().data_ptr()
    with pytest.raises(ValueError, match="max_seq_len"):
        rope(value, offset=8)


@given(batch=st.integers(1, 3), length=st.integers(1, 8), kv_heads=st.sampled_from([1, 2, 4]))
@settings(max_examples=12, deadline=None)
def test_gqa_shape_property_and_sdpa_reference(batch: int, length: int, kv_heads: int) -> None:
    torch.manual_seed(1)  # pyright: ignore[reportUnknownMemberType]
    attention = GroupedQueryAttention(tiny_config(n_kv_heads=kv_heads)).eval()
    inputs = torch.randn(batch, length, 16)
    sdpa, _ = attention(inputs, implementation="sdpa")
    eager, _ = attention(inputs, implementation="eager")
    assert sdpa.shape == inputs.shape
    torch.testing.assert_close(sdpa, eager, atol=2e-6, rtol=2e-5)


def test_causality_future_changes_do_not_affect_past_logits() -> None:
    torch.manual_seed(2)  # pyright: ignore[reportUnknownMemberType]
    model = CausalLM(tiny_config()).eval()
    first = torch.randint(0, 31, (2, 8))
    second = first.clone()
    second[:, 5:] = torch.randint(0, 31, (2, 3))
    torch.testing.assert_close(
        model(first).logits[:, :5], model(second).logits[:, :5], atol=0, rtol=0
    )


def test_forward_shifted_loss_backward_tying_and_state_round_trip() -> None:
    torch.manual_seed(3)  # pyright: ignore[reportUnknownMemberType]
    model = CausalLM(tiny_config())
    tokens = torch.randint(0, 31, (3, 9))
    output = model(tokens, targets=tokens)
    assert output.logits.shape == (3, 9, 31)
    assert output.loss is not None and bool(torch.isfinite(output.loss))
    expected = F.cross_entropy(output.logits[:, :-1].reshape(-1, 31), tokens[:, 1:].reshape(-1))
    torch.testing.assert_close(output.loss, expected)
    output.loss.backward()
    assert model.lm_head.weight is model.token_embedding.weight
    assert all(parameter.grad is not None for parameter in model.parameters())
    restored = CausalLM(tiny_config()).eval()
    restored.load_state_dict(model.state_dict())
    model.eval()
    torch.testing.assert_close(model(tokens).logits, restored(tokens).logits)


def test_padding_ignore_index_and_input_contract() -> None:
    model = CausalLM(tiny_config())
    tokens = torch.randint(0, 31, (1, 5))
    targets = tokens.clone()
    targets[:, 3:] = -100
    assert model(tokens, targets=targets).loss is not None
    with pytest.raises(ValueError, match="int64"):
        model(tokens.float())
    with pytest.raises(ValueError, match="max_seq_len"):
        model(torch.zeros((1, 17), dtype=torch.long))


def test_kv_cache_and_uncached_generation_have_parity() -> None:
    torch.manual_seed(4)  # pyright: ignore[reportUnknownMemberType]
    model = CausalLM(tiny_config()).eval()
    prompt = torch.tensor([[1, 2, 3, 4]])
    cached = model.generate(
        prompt, GenerationConfig(max_new_tokens=6, temperature=0, use_cache=True)
    )
    uncached = model.generate(
        prompt, GenerationConfig(max_new_tokens=6, temperature=0, use_cache=False)
    )
    assert torch.equal(cached, uncached)


def test_parameter_count_deduplicates_tied_weight() -> None:
    model = CausalLM(tiny_config())
    assert model.parameter_count() == sum(parameter.numel() for parameter in model.parameters())
    estimate = model.memory_estimate()
    assert estimate["weights_bytes"] == estimate["parameters"] * 4


def test_128_document_overfit_loss_decreases() -> None:
    torch.manual_seed(5)  # pyright: ignore[reportUnknownMemberType]
    model = CausalLM(
        tiny_config(
            n_layers=1, d_model=8, n_heads=2, n_kv_heads=1, ffn_hidden_size=16, vocab_size=8
        )
    )
    documents = torch.tensor([[1, 2, 3, 4, 5, 6, 7, 0]]).repeat(128, 1)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.03)
    initial_loss = model(documents, targets=documents).loss
    assert initial_loss is not None
    initial = float(initial_loss.detach())
    for _ in range(20):
        optimizer.zero_grad(set_to_none=True)
        loss = model(documents, targets=documents).loss
        assert loss is not None
        loss.backward()
        optimizer.step()  # pyright: ignore[reportUnknownMemberType]
    final_loss = model(documents, targets=documents).loss
    assert final_loss is not None
    final = float(final_loss.detach())
    assert final < initial * 0.35


def test_model_inspect_cli_artifact_contract(tmp_path: Path) -> None:
    output = tmp_path / "inspect.json"
    result = CliRunner().invoke(
        app,
        [
            "model",
            "inspect",
            "--config",
            str(ROOT / "configs/model/smoke.yaml"),
            "--output",
            str(output),
        ],
    )
    assert result.exit_code == 0, result.output
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert artifact["schema_version"] == 1
    assert artifact["weight_tying"] is True
    assert artifact["parameters"] > 0
    assert output.with_name("resolved-config.json").exists()
    conflict = CliRunner().invoke(
        app,
        [
            "model",
            "inspect",
            "--config",
            str(ROOT / "configs/model/smoke.yaml"),
            "--output",
            str(output),
        ],
    )
    assert conflict.exit_code == 4
