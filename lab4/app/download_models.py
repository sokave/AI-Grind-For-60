import argparse
from pathlib import Path

from huggingface_hub import hf_hub_download


REPOSITORY = "unsloth/Qwen3-1.7B-GGUF"
REVISION = "d7f544eead698dbd1f15126ef60b45a1e1933222"
FILES = ["Qwen3-1.7B-Q8_0.gguf", "Qwen3-1.7B-Q4_K_M.gguf"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", default=str(Path(__file__).resolve().parent / "models"))
    args = parser.parse_args()
    for filename in FILES:
        path = hf_hub_download(REPOSITORY, filename, revision=REVISION, local_dir=args.directory)
        print(path, flush=True)


if __name__ == "__main__":
    main()
