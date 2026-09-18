from pathlib import Path


def merge_adapter(base_model: str, adapter_path: Path, output_path: Path) -> None:
    raise NotImplementedError(
        "Adapter merging is a Phase 1 interface; implementation requires the validated model stack."
    )
