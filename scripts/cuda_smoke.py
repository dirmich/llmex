"""DGX Spark 컨테이너의 CUDA bf16 행렬곱을 확인한다."""

import json

import torch


def main() -> None:
    if not torch.cuda.is_available():
        raise SystemExit("CUDA를 사용할 수 없습니다")
    left = torch.randn((512, 512), device="cuda", dtype=torch.bfloat16)
    result = left @ left
    torch.cuda.synchronize()
    print(
        json.dumps(
            {
                "cuda": torch.version.cuda,
                "device": torch.cuda.get_device_name(),
                "dtype": str(result.dtype),
                "finite": bool(torch.isfinite(result).all().item()),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
