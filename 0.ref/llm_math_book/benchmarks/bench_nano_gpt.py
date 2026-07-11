"""벤치마크 스크립트.

사용법:
    python benchmarks/bench_<name>.py
    # 또는 노트북에서:
    # %run benchmarks/bench_<name>.py

출력: Markdown 표 + 그래프 PNG (benchmarks/results/ 에 저장)
"""
import sys
import os
from pathlib import Path

# 레포 루트를 path에 추가
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))

import numpy as np
import torch
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# 한글 폰트 설정 (가능한 경우)
try:
    for p in ['/usr/share/fonts/truetype/chinese/NotoSansSC-Regular.ttf',
              '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']:
        try: fm.fontManager.addfont(p)
        except: pass
    plt.rcParams['font.sans-serif'] = ['Noto Sans SC', 'Nanum Gothic', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
except Exception:
    pass

from llm_math.bench import time_fn, format_results_table, get_device

RESULTS_DIR = Path(__file__).resolve().parent / 'results'
RESULTS_DIR.mkdir(exist_ok=True)

# === Bench: nano-GPT 전체 학습 ===

def main():
    print("=== nano-GPT 전체 학습 ===")
    print("이 벤치마크는 해당 챕터 노트북에서 실행하는 것을 권장합니다.")
    print("노트북에서 직접 실행하면 더 자세한 결과와 시각화를 볼 수 있습니다.")
    print()
    print("권장 실행 방법:")
    print("  1. Colab에서 해당 챕터 노트북 열기")
    print("  2. 런타임을 GPU로 전환")
    print("  3. 노트북의 벤치마크 셀 실행")
    print()
    # 간단한 데모
    print("데모: 간단한 행렬곱 시간 측정")
    n = 1024
    A = torch.randn(n, n); B = torch.randn(n, n)
    res = time_fn(lambda A, B: A @ B, A, B, device='cpu', warmup=2, repeat=3)
    print(f"  n={n} 행렬곱: {res['mean_ms']:.3f} ms")


if __name__ == '__main__':
    main()
