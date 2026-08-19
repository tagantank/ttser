from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


HF_REPO = "rodrigomt/s2-pro-gguf"


@dataclass(frozen=True)
class ModelOption:
    id: str
    filename: str
    title: str
    size: str
    size_bytes: int
    description: str

    @property
    def url(self) -> str:
        return f"https://huggingface.co/{HF_REPO}/resolve/main/{self.filename}"

    @property
    def combo_label(self) -> str:
        from ttser.i18n import model_combo_label

        return model_combo_label(self.id, self.title)


MODELS: tuple[ModelOption, ...] = (
    ModelOption(
        id="q4_k_m",
        filename="s2-pro-q4_k_m.gguf",
        title="s2-pro-q4_k_m",
        size="~3.3 GiB",
        size_bytes=3_566_165_088,
        description=(
            "Fastest on CPU and smallest on disk. "
            "Useful as a fallback or when RAM is limited."
        ),
    ),
    ModelOption(
        id="q8_0",
        filename="s2-pro-q8_0.gguf",
        title="s2-pro-q8_0",
        size="~5.2 GiB",
        size_bytes=5_630_037_088,
        description=(
            "Recommended quality profile. "
            "Best balance of sound and speed for everyday use."
        ),
    ),
    ModelOption(
        id="f16",
        filename="s2-pro-f16.gguf",
        title="s2-pro-f16",
        size="~9.2 GiB",
        size_bytes=9_906_568_704,
        description=(
            "Maximum quality without quantizing the AR block. "
            "Much slower on CPU and needs a large amount of memory."
        ),
    ),
)


def model_by_id(model_id: str) -> ModelOption | None:
    for model in MODELS:
        if model.id == model_id:
            return model
    return None


def model_by_filename(filename: str) -> ModelOption | None:
    for model in MODELS:
        if model.filename == filename:
            return model
    return None


def model_destination(models_dir: str | Path, model: ModelOption) -> Path:
    return Path(models_dir).expanduser() / model.filename


def is_model_file_complete(path: Path, size_bytes: int = 0) -> bool:
    try:
        if not path.is_file():
            return False
        size = path.stat().st_size
    except OSError:
        return False
    minimum = 1024 * 1024
    if size_bytes > 0:
        return size >= max(minimum, int(size_bytes * 0.95))
    return size >= minimum


def find_downloaded_model(model: ModelOption, *locations: str | Path) -> Path | None:
    seen: set[Path] = set()
    for location in locations:
        if not location:
            continue
        path = Path(location).expanduser()
        candidate = path if path.name == model.filename else path / model.filename
        key = candidate
        if key in seen:
            continue
        seen.add(key)
        if is_model_file_complete(candidate, model.size_bytes):
            return candidate
    return None


def is_model_downloaded(models_dir: str | Path, model: ModelOption) -> bool:
    return find_downloaded_model(model, models_dir) is not None
