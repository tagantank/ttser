from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

WidgetKind = Literal["int", "float", "bool", "choice", "codec"]

ALL_BACKENDS = frozenset({"cpu", "vulkan", "cuda", "metal"})
GPU_BACKENDS = frozenset({"vulkan", "cuda", "metal"})
DEVICE_BACKENDS = frozenset({"vulkan", "cuda"})

LOG_LEVELS: tuple[tuple[str, int], ...] = (
    ("error", 0),
    ("warn", 1),
    ("info", 2),
    ("debug", 3),
)
LOG_LEVEL_BY_NAME = {name: value for name, value in LOG_LEVELS}
LOG_LEVEL_BY_VALUE = {value: name for name, value in LOG_LEVELS}

DEFAULT_MAX_NEW_TOKENS = 1024
DEFAULT_TEMPERATURE = 0.8
DEFAULT_TOP_P = 0.8
DEFAULT_TOP_K = 30
DEFAULT_MIN_TOKENS_BEFORE_END = 0
DEFAULT_LINE_PAUSE_MS = 180
DEFAULT_THREADS = 8
DEFAULT_N_GPU_LAYERS = -1
DEFAULT_GPU_DEVICE = 0
DEFAULT_LOG_LEVEL = "info"
DEFAULT_VERBOSE = False


@dataclass(frozen=True)
class SynthParamSpec:
    id: str
    kind: WidgetKind
    backends: frozenset[str]
    default: Any
    minimum: float | int | None = None
    maximum: float | int | None = None
    decimals: int = 2
    choices: tuple[str, ...] = ()


SYNTH_PARAMS: tuple[SynthParamSpec, ...] = (
    SynthParamSpec(
        "max_new_tokens",
        "int",
        ALL_BACKENDS,
        DEFAULT_MAX_NEW_TOKENS,
        minimum=1,
        maximum=8192,
    ),
    SynthParamSpec(
        "temperature",
        "float",
        ALL_BACKENDS,
        DEFAULT_TEMPERATURE,
        minimum=0.0,
        maximum=2.0,
        decimals=2,
    ),
    SynthParamSpec(
        "top_p",
        "float",
        ALL_BACKENDS,
        DEFAULT_TOP_P,
        minimum=0.0,
        maximum=1.0,
        decimals=2,
    ),
    SynthParamSpec(
        "top_k",
        "int",
        ALL_BACKENDS,
        DEFAULT_TOP_K,
        minimum=0,
        maximum=200,
    ),
    SynthParamSpec(
        "min_tokens_before_end",
        "int",
        ALL_BACKENDS,
        DEFAULT_MIN_TOKENS_BEFORE_END,
        minimum=0,
        maximum=2048,
    ),
    SynthParamSpec(
        "line_pause_ms",
        "int",
        ALL_BACKENDS,
        DEFAULT_LINE_PAUSE_MS,
        minimum=0,
        maximum=2000,
    ),
    SynthParamSpec(
        "threads",
        "int",
        ALL_BACKENDS,
        DEFAULT_THREADS,
        minimum=0,
        maximum=64,
    ),
    SynthParamSpec(
        "log_level",
        "choice",
        ALL_BACKENDS,
        DEFAULT_LOG_LEVEL,
        choices=tuple(name for name, _ in LOG_LEVELS),
    ),
    SynthParamSpec(
        "verbose",
        "bool",
        ALL_BACKENDS,
        DEFAULT_VERBOSE,
    ),
    SynthParamSpec(
        "n_gpu_layers",
        "int",
        GPU_BACKENDS,
        DEFAULT_N_GPU_LAYERS,
        minimum=-1,
        maximum=36,
    ),
    SynthParamSpec(
        "gpu_device",
        "int",
        DEVICE_BACKENDS,
        DEFAULT_GPU_DEVICE,
        minimum=0,
        maximum=16,
    ),
    SynthParamSpec(
        "codec_follow_backend",
        "codec",
        GPU_BACKENDS,
        None,
    ),
)


def params_for_backend(backend: str) -> list[SynthParamSpec]:
    return [spec for spec in SYNTH_PARAMS if backend in spec.backends]


def default_codec_follow_backend(backend: str) -> int:
    # Vulkan on shared iGPU RAM: keep codec on CPU (0). CUDA/Metal follow GPU (1).
    if backend == "vulkan":
        return 0
    return 1


def default_n_gpu_layers(backend: str) -> int:
    if backend in GPU_BACKENDS:
        return DEFAULT_N_GPU_LAYERS
    return 0


def normalize_log_level(value: object) -> str:
    if isinstance(value, int):
        return LOG_LEVEL_BY_VALUE.get(value, DEFAULT_LOG_LEVEL)
    text = str(value).strip().lower()
    if text in LOG_LEVEL_BY_NAME:
        return text
    aliases = {"warning": "warn"}
    return aliases.get(text, DEFAULT_LOG_LEVEL)


def log_level_int(name: str) -> int:
    return LOG_LEVEL_BY_NAME[normalize_log_level(name)]


def synthesis_defaults(backend: str) -> dict[str, Any]:
    values: dict[str, Any] = {
        "max_new_tokens": DEFAULT_MAX_NEW_TOKENS,
        "temperature": DEFAULT_TEMPERATURE,
        "top_p": DEFAULT_TOP_P,
        "top_k": DEFAULT_TOP_K,
        "min_tokens_before_end": DEFAULT_MIN_TOKENS_BEFORE_END,
        "line_pause_ms": DEFAULT_LINE_PAUSE_MS,
        "threads": DEFAULT_THREADS,
        "log_level": DEFAULT_LOG_LEVEL,
        "verbose": DEFAULT_VERBOSE,
        "n_gpu_layers": default_n_gpu_layers(backend),
        "gpu_device": DEFAULT_GPU_DEVICE,
        "codec_follow_backend": default_codec_follow_backend(backend),
    }
    return values
