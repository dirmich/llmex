"""llm_math.data: small dataset loaders.

- Tiny Shakespeare
- Tiny English text
- XOR data
- MNIST through scikit-learn fetch_openml
"""

from __future__ import annotations

import os
import urllib.request
from pathlib import Path
from typing import Optional

import numpy as np

# Data cache directory
_DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
_TINY_SHAKESPEARE_URL = "https://raw.githubusercontent.com/karpathy/char-rnn/master/data/tinyshakespeare/input.txt"


def get_data_dir(data_dir: Optional[str] = None) -> Path:
    """Return the data directory path and create it if needed."""
    d = Path(data_dir) if data_dir else _DEFAULT_DATA_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_tiny_shakespeare(data_dir: Optional[str] = None, max_chars: Optional[int] = None) -> str:
    """Load Tiny Shakespeare text.

    Parameters
    ----------
    data_dir : str, optional
        Directory used to store data. Defaults to repository `data/`.
    max_chars : int, optional
        Maximum number of characters to return.

    Returns
    -------
    str
        Tiny Shakespeare text.
    """
    d = get_data_dir(data_dir)
    fp = d / "tiny_shakespeare.txt"
    if not fp.exists():
        try:
            urllib.request.urlretrieve(_TINY_SHAKESPEARE_URL, fp)
        except Exception:
            # Small fallback text for offline environments.
            dummy = (
                "To be, or not to be, that is the question:\n"
                "Whether 'tis nobler in the mind to suffer\n"
                "The slings and arrows of outrageous fortune,\n"
                "Or to take Arms against a Sea of troubles,\n"
                "And by opposing end them: to die, to sleep\n"
            ) * 100
            fp.write_text(dummy, encoding='utf-8')
    text = fp.read_text(encoding='utf-8')
    if max_chars is not None:
        text = text[:max_chars]
    return text


def load_mini_english(data_dir: Optional[str] = None) -> str:
    """Load a tiny English practice corpus."""
    d = get_data_dir(data_dir)
    fp = d / "mini_wiki_en.txt"
    if not fp.exists():
        dummy = (
            "Natural language processing studies how computers process human language. "
            "Large language models have changed many NLP workflows. "
            "Transformer architectures rely on attention mechanisms. "
            "Attention helps models learn relationships between tokens in a sequence. "
            "These methods are used for translation, summarization, and question answering.\n"
        ) * 50
        fp.write_text(dummy, encoding='utf-8')
    return fp.read_text(encoding='utf-8')


load_mini_korean = load_mini_english


def make_xor_data() -> tuple[np.ndarray, np.ndarray]:
    """Return a dataset for XOR classification."""
    X = np.array([[0, 0], [0, 1], [1, 0], [1, 1]], dtype=np.float32)
    y = np.array([0, 1, 1, 0], dtype=np.float32).reshape(-1, 1)
    return X, y


def make_spiral_data(n_per_class: int = 100, n_classes: int = 3, noise: float = 0.1,
                     seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """Create a spiral classification dataset."""
    rng = np.random.default_rng(seed)
    X = []
    y = []
    for k in range(n_classes):
        r = np.linspace(0.0, 1, n_per_class)
        t = np.linspace(k * 2 * np.pi / n_classes, (k + 1) * 2 * np.pi / n_classes, n_per_class) + \
            rng.normal(0, noise, n_per_class)
        X.append(np.stack([r * np.sin(t), r * np.cos(t)], axis=1))
        y.append(np.full(n_per_class, k))
    X = np.concatenate(X).astype(np.float32)
    y = np.concatenate(y).astype(np.int64)
    return X, y


def make_regression_data(n: int = 100, noise: float = 0.1, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """Create a simple regression dataset: y = 2x + 1 + noise."""
    rng = np.random.default_rng(seed)
    X = rng.uniform(-3, 3, (n, 1)).astype(np.float32)
    y = (2 * X[:, 0] + 1 + rng.normal(0, noise, n)).astype(np.float32).reshape(-1, 1)
    return X, y


def load_mnist_small(n_train: int = 5000, n_test: int = 1000, seed: int = 0
                     ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Load a small MNIST subset through scikit-learn fetch_openml.

    Returns
    -------
    (X_train, y_train, X_test, y_test)
        X: (N, 784) float32 normalized to [0, 1]
        y: (N,) int64
    """
    from sklearn.datasets import fetch_openml
    from sklearn.model_selection import train_test_split

    cache_dir = get_data_dir() / "mnist_cache"
    cache_dir.mkdir(exist_ok=True)
    cache_file = cache_dir / "mnist.npz"
    if cache_file.exists():
        d = np.load(cache_file)
        X, y = d['X'], d['y']
    else:
        X, y = fetch_openml('mnist_784', version=1, return_X_y=True, as_frame=False,
                             parser='auto')
        X = X.astype(np.float32) / 255.0
        y = y.astype(np.int64)
        np.savez_compressed(cache_file, X=X, y=y)

    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(X))
    X, y = X[idx], y[idx]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, train_size=n_train, test_size=n_test, random_state=seed, stratify=y
    )
    return X_train, y_train, X_test, y_test


def make_tiny_corpus(max_chars: int = 10000, language: str = 'en',
                     data_dir: Optional[str] = None) -> str:
    """Return a tiny corpus for language-model experiments."""
    if language == 'ko':
        return load_mini_english(data_dir)[:max_chars]
    return load_tiny_shakespeare(data_dir, max_chars=max_chars)
