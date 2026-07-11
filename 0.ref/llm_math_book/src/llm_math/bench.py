"""llm_math.bench: CPU/GPU benchmark helpers.

>>> from llm_math.bench import time_fn, format_results_table
>>> import torch
>>> def f(x): return x @ x
>>> x_cpu = torch.randn(1024, 1024)
>>> t_cpu = time_fn(f, x_cpu, device='cpu', repeat=5)
>>> # Only when a GPU is available.
>>> if torch.cuda.is_available():
...     x_gpu = x_cpu.cuda()
...     t_gpu = time_fn(f, x_gpu, device='cuda', repeat=5)
"""

from __future__ import annotations

import time
from statistics import mean, stdev
from typing import Callable, Any, Optional

try:
    import torch
    _HAS_TORCH = True
except ImportError:  # pragma: no cover
    _HAS_TORCH = False


def _sync(device: str) -> None:
    """Wait for asynchronous CUDA work to finish."""
    if device.startswith('cuda') and _HAS_TORCH and torch.cuda.is_available():
        torch.cuda.synchronize()


def time_fn(
    fn: Callable[..., Any],
    *args,
    device: str = 'cpu',
    warmup: int = 3,
    repeat: int = 10,
    **kwargs,
) -> dict:
    """Measure the execution time of ``fn(*args, **kwargs)``.

    Parameters
    ----------
    fn : callable
        Function to measure. The return value is ignored.
    device : str
        'cpu' or 'cuda'. Used to decide synchronization behavior.
    warmup : int
        Number of warmup iterations excluded from measurement.
    repeat : int
        Number of measured repetitions.

    Returns
    -------
    dict
        {'mean_ms', 'std_ms', 'min_ms', 'max_ms', 'repeat'}
    """
    # warmup
    for _ in range(warmup):
        fn(*args, **kwargs)
        _sync(device)

    times: list[float] = []
    for _ in range(repeat):
        _sync(device)
        t0 = time.perf_counter()
        fn(*args, **kwargs)
        _sync(device)
        t1 = time.perf_counter()
        times.append((t1 - t0) * 1000.0)  # ms

    return {
        'mean_ms': mean(times),
        'std_ms': stdev(times) if len(times) > 1 else 0.0,
        'min_ms': min(times),
        'max_ms': max(times),
        'repeat': repeat,
        'all_ms': times,
    }


def format_results_table(results: dict[str, dict], title: str = '') -> str:
    """Format benchmark results as a Markdown table.

    Parameters
    ----------
    results : dict
        {'CPU': {'mean_ms':..., 'std_ms':...}, 'GPU': {...}}
    title : str
        Table title used as a Markdown heading.

    Returns
    -------
    str
        Markdown table string.
    """
    header = f"### {title}\n\n" if title else ""
    header += "| Device | Mean (ms) | Std (ms) | Min (ms) | Max (ms) | Repeat |\n"
    header += "|--------|-----------|----------|----------|----------|--------|\n"
    rows = []
    for dev, m in results.items():
        rows.append(
            f"| {dev} | {m['mean_ms']:.3f} | {m['std_ms']:.3f} | "
            f"{m['min_ms']:.3f} | {m['max_ms']:.3f} | {m['repeat']} |"
        )
    return header + "\n".join(rows)


def get_device(prefer_gpu: bool = True) -> str:
    """Return the selected available device.

    Return 'cuda' when a GPU is available and preferred; otherwise 'cpu'.
    """
    if prefer_gpu and _HAS_TORCH and torch.cuda.is_available():
        return 'cuda'
    return 'cpu'


def memory_info(device: str = 'cpu') -> dict:
    """Return memory usage for the current device.

    CUDA uses torch.cuda memory counters. CPU returns None for allocated_mb.
    """
    info = {'device': device}
    if device.startswith('cuda') and _HAS_TORCH and torch.cuda.is_available():
        info['allocated_mb'] = torch.cuda.memory_allocated() / 1024**2
        info['reserved_mb'] = torch.cuda.memory_reserved() / 1024**2
        info['max_allocated_mb'] = torch.cuda.max_memory_allocated() / 1024**2
    elif _HAS_TORCH:
        info['allocated_mb'] = None
    return info


def reset_memory_stats(device: str = 'cuda') -> None:
    """Reset CUDA memory statistics."""
    if device.startswith('cuda') and _HAS_TORCH and torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()


def estimate_speedup(cpu_ms: float, gpu_ms: float) -> float:
    """Return the GPU speedup factor over CPU time."""
    if gpu_ms <= 0:
        return float('inf')
    return cpu_ms / gpu_ms
