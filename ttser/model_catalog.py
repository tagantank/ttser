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
        return f"{self.title} ({self.size})"


MODELS: tuple[ModelOption, ...] = (
    ModelOption(
        id="q4_k_m",
        filename="s2-pro-q4_k_m.gguf",
        title="s2-pro-q4_k_m",
        size="~3.3 ГиБ",
        size_bytes=3_566_165_088,
        description=(
            "Быстрее на CPU и меньше занимает на диске. "
            "Подходит как запасной вариант или если мало RAM."
        ),
    ),
    ModelOption(
        id="q8_0",
        filename="s2-pro-q8_0.gguf",
        title="s2-pro-q8_0",
        size="~5.2 ГиБ",
        size_bytes=5_630_037_088,
        description=(
            "Рекомендуемый профиль качества. "
            "Лучший баланс между звуком и скоростью для повседневной работы."
        ),
    ),
    ModelOption(
        id="f16",
        filename="s2-pro-f16.gguf",
        title="s2-pro-f16",
        size="~9.2 ГиБ",
        size_bytes=9_906_568_704,
        description=(
            "Максимальное качество без квантования AR-блока. "
            "На CPU заметно медленнее, нужен большой объём памяти."
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
