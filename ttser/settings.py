from __future__ import annotations

import platform
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QSettings

from engine.runtime import is_flatpak, is_frozen, resource_root, user_data_dir
from engine.s2_voice import DEFAULT_VOICE_ID, preferred_voice_id, voice_search_dirs
from ttser.backends import normalize_backend, resolve_library_path
from ttser.i18n import DEFAULT_LANGUAGE, normalize_language
from ttser.model_catalog import find_downloaded_model, model_by_filename, model_by_id
from ttser.synth_params import (
    DEFAULT_LOG_LEVEL,
    DEFAULT_MAX_NEW_TOKENS,
    DEFAULT_MIN_TOKENS_BEFORE_END,
    DEFAULT_LINE_PAUSE_MS,
    DEFAULT_N_GPU_LAYERS,
    DEFAULT_TEMPERATURE,
    DEFAULT_THREADS,
    DEFAULT_TOP_K,
    DEFAULT_TOP_P,
    DEFAULT_VERBOSE,
    default_codec_follow_backend,
    normalize_log_level,
)


def default_dictionary_paths() -> list[str]:
    if is_flatpak():
        base = Path("/app/share/ttser/dictionaries")
        return [str(base / "s2_terms_ru.json"), str(base / "s2_pronunciation_ru.json")]
    if is_frozen():
        base = resource_root() / "dictionaries"
        return [str(base / "s2_terms_ru.json"), str(base / "s2_pronunciation_ru.json")]
    return [
        "dictionaries/s2_terms_ru.json",
        "dictionaries/s2_pronunciation_ru.json",
    ]


def user_dictionary_dir() -> Path:
    if is_flatpak() or is_frozen():
        return user_data_dir() / "dictionaries"
    return Path("dictionaries")


def default_models_dir() -> str:
    if is_flatpak() or is_frozen():
        return str(user_data_dir() / "models")
    return "s2.cpp/models"


def model_lookup_dirs(models_dir: str | None = None) -> list[str]:
    dirs = [
        models_dir or "",
        default_models_dir(),
        str(Path.home() / ".var" / "app" / "com.tagantank.ttser" / "data" / "models"),
        "s2.cpp/models",
    ]
    seen: set[str] = set()
    unique: list[str] = []
    for item in dirs:
        if not item or item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return unique


def default_voice_dir() -> str:
    if is_flatpak():
        return "/app/share/ttser/voices"
    if is_frozen():
        return str(resource_root() / "voices")
    return "voices"


@dataclass
class AppSettings:
    backend: str = "cpu"
    vulkan_device: int = 0
    threads: int = DEFAULT_THREADS
    max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS
    temperature: float = DEFAULT_TEMPERATURE
    top_p: float = DEFAULT_TOP_P
    top_k: int = DEFAULT_TOP_K
    min_tokens_before_end: int = DEFAULT_MIN_TOKENS_BEFORE_END
    line_pause_ms: int = DEFAULT_LINE_PAUSE_MS
    n_gpu_layers: int = DEFAULT_N_GPU_LAYERS
    codec_follow_backend: int | None = None
    log_level: str = DEFAULT_LOG_LEVEL
    verbose: bool = DEFAULT_VERBOSE
    model_path: str = "s2.cpp/models/s2-pro-q8_0.gguf"
    models_dir: str = field(default_factory=default_models_dir)
    selected_model_id: str = "q8_0"
    tokenizer_path: str = "s2.cpp/tokenizer.json"
    voice_dir: str = field(default_factory=default_voice_dir)
    lib_cpu: str = "lib/libs2_cpu.so"
    lib_vulkan: str = "lib/libs2_vulkan.so"
    lib_cuda: str = "lib/libs2_cuda.so"
    lib_metal: str = "lib/libs2_metal.dylib"
    dictionary_paths: list[str] = field(default_factory=default_dictionary_paths)
    dictionaries_enabled: bool = True
    selected_voice_id: str = DEFAULT_VOICE_ID
    ui_language: str = DEFAULT_LANGUAGE


def effective_codec_follow_backend(settings: AppSettings) -> int:
    if settings.codec_follow_backend is not None:
        return 1 if settings.codec_follow_backend else 0
    return default_codec_follow_backend(settings.backend)


def effective_n_gpu_layers(settings: AppSettings) -> int:
    if settings.backend == "cpu":
        return 0
    return settings.n_gpu_layers


def _bundled_lib(name: str) -> str:
    root = resource_root()
    nested = {
        "libs2_cpu.dylib": root / "lib" / "cpu" / "libs2_cpu.dylib",
        "libs2_cpu.so": root / "lib" / "cpu" / "libs2_cpu.so",
        "libs2_metal.dylib": root / "lib" / "metal" / "libs2_metal.dylib",
    }.get(name)
    if nested is not None and nested.is_file():
        return str(nested)
    return str(root / "lib" / name)


def _adjust_defaults(settings: AppSettings) -> None:
    if is_flatpak():
        settings.lib_cpu = "/app/lib/ttser/libs2_cpu.so"
        settings.lib_vulkan = "/app/lib/ttser/libs2_vulkan.so"
        settings.lib_cuda = "/app/lib/ttser/libs2_cuda.so"
        settings.lib_metal = "/app/lib/ttser/libs2_metal.dylib"
        settings.tokenizer_path = "/app/share/ttser/tokenizer.json"
        settings.voice_dir = default_voice_dir()
    if is_frozen():
        suffix = ".dylib" if platform.system() == "Darwin" else ".so"
        settings.lib_cpu = _bundled_lib(f"libs2_cpu{suffix}")
        settings.lib_metal = _bundled_lib("libs2_metal.dylib")
        tokenizer = resource_root() / "s2.cpp" / "tokenizer.json"
        if not tokenizer.is_file():
            tokenizer = resource_root() / "tokenizer.json"
        settings.tokenizer_path = str(tokenizer)
        settings.voice_dir = default_voice_dir()
        settings.dictionary_paths = default_dictionary_paths()
        models_dir = Path(default_models_dir())
        settings.models_dir = str(models_dir)
        settings.model_path = str(models_dir / Path(settings.model_path).name)
    if platform.system() == "Darwin":
        if not is_frozen() and not is_flatpak():
            settings.lib_cpu = "lib/libs2_cpu.dylib"
        if settings.backend in {"vulkan", "cuda"}:
            settings.backend = "cpu"
        if is_flatpak():
            settings.lib_cpu = "/app/lib/ttser/libs2_cpu.dylib"


def _migrate_library_paths(settings: AppSettings) -> None:
    for lib_attr in ("lib_cpu", "lib_vulkan", "lib_cuda", "lib_metal"):
        resolved = resolve_library_path(settings, lib_attr)
        if resolved.is_file():
            setattr(settings, lib_attr, str(resolved))


def _migrate_tokenizer_path(settings: AppSettings) -> None:
    path = Path(settings.tokenizer_path)
    candidates = [
        path,
        resource_root() / "s2.cpp" / "tokenizer.json",
        resource_root() / "tokenizer.json",
        Path("s2.cpp/tokenizer.json"),
        Path("s2.cpp/models/tokenizer.json"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            settings.tokenizer_path = str(candidate)
            return


def _migrate_model_paths(settings: AppSettings) -> None:
    model = model_by_id(settings.selected_model_id) or model_by_filename(Path(settings.model_path).name)
    if model is None:
        return
    found = find_downloaded_model(
        model,
        settings.model_path,
        *model_lookup_dirs(settings.models_dir),
    )
    if found is None:
        return
    settings.model_path = str(found)
    settings.models_dir = str(found.parent)


def load_settings() -> AppSettings:
    q = QSettings("ttser", "ttser")
    in_flatpak = is_flatpak()
    default_tokenizer = "/app/share/ttser/tokenizer.json" if in_flatpak else "s2.cpp/tokenizer.json"
    default_cpu = "/app/lib/ttser/libs2_cpu.so" if in_flatpak else "lib/libs2_cpu.so"
    default_vk = "/app/lib/ttser/libs2_vulkan.so" if in_flatpak else "lib/libs2_vulkan.so"
    default_cuda = "/app/lib/ttser/libs2_cuda.so" if in_flatpak else "lib/libs2_cuda.so"
    default_metal = "/app/lib/ttser/libs2_metal.dylib" if in_flatpak else "lib/libs2_metal.dylib"
    default_dicts = default_dictionary_paths()
    stored_voice_id = q.value("selected_voice_id")
    legacy_ref_enabled = bool(q.value("reference_voice_enabled", False))
    codec_raw = q.value("codec_follow_backend")
    codec_follow: int | None
    if codec_raw is None:
        codec_follow = None
    else:
        codec_follow = 1 if int(codec_raw) else 0
    s = AppSettings(
        backend=q.value("backend", "cpu"),
        vulkan_device=int(q.value("vulkan_device", 0)),
        threads=int(q.value("threads", DEFAULT_THREADS)),
        max_new_tokens=int(q.value("max_new_tokens", DEFAULT_MAX_NEW_TOKENS)),
        temperature=float(q.value("temperature", DEFAULT_TEMPERATURE)),
        top_p=float(q.value("top_p", DEFAULT_TOP_P)),
        top_k=int(q.value("top_k", DEFAULT_TOP_K)),
        min_tokens_before_end=int(
            q.value("min_tokens_before_end", DEFAULT_MIN_TOKENS_BEFORE_END)
        ),
        line_pause_ms=int(q.value("line_pause_ms", DEFAULT_LINE_PAUSE_MS)),
        n_gpu_layers=int(q.value("n_gpu_layers", DEFAULT_N_GPU_LAYERS)),
        codec_follow_backend=codec_follow,
        log_level=normalize_log_level(q.value("log_level", DEFAULT_LOG_LEVEL)),
        verbose=bool(q.value("verbose", DEFAULT_VERBOSE)),
        model_path=q.value("model_path", "s2.cpp/models/s2-pro-q8_0.gguf"),
        models_dir=q.value("models_dir", default_models_dir()),
        selected_model_id=q.value("selected_model_id", "q8_0"),
        tokenizer_path=q.value("tokenizer_path", default_tokenizer),
        voice_dir=q.value("voice_dir", default_voice_dir()),
        lib_cpu=q.value("lib_cpu", default_cpu),
        lib_vulkan=q.value("lib_vulkan", default_vk),
        lib_cuda=q.value("lib_cuda", default_cuda),
        lib_metal=q.value("lib_metal", default_metal),
        dictionary_paths=q.value("dictionary_paths", default_dicts),
        dictionaries_enabled=bool(q.value("dictionaries_enabled", True)),
        selected_voice_id=DEFAULT_VOICE_ID,
        ui_language=normalize_language(q.value("ui_language", DEFAULT_LANGUAGE)),
    )
    _adjust_defaults(s)
    _migrate_library_paths(s)
    _migrate_tokenizer_path(s)
    _migrate_model_paths(s)
    s.backend = normalize_backend(s)
    if not s.selected_model_id or model_by_id(s.selected_model_id) is None:
        matched = model_by_filename(Path(s.model_path).name)
        s.selected_model_id = matched.id if matched else "q8_0"
    if in_flatpak:
        if not Path(s.lib_cpu).is_file():
            s.lib_cpu = default_cpu
        if not Path(s.lib_vulkan).is_file():
            s.lib_vulkan = default_vk
        if not Path(s.lib_metal).is_file():
            s.lib_metal = default_metal
        if not Path(s.tokenizer_path).is_file():
            s.tokenizer_path = default_tokenizer
        if not all(Path(path).is_file() for path in s.dictionary_paths):
            s.dictionary_paths = default_dicts
        elif any(not str(path).startswith("/app/") for path in s.dictionary_paths):
            s.dictionary_paths = default_dicts
        if not Path(s.voice_dir).is_dir() or not str(s.voice_dir).startswith("/app/"):
            if Path("/app/share/ttser/voices/tankindycast.s2voice").is_file():
                s.voice_dir = default_voice_dir()
    search_dirs = [str(path) for path in voice_search_dirs(s.voice_dir)]
    if stored_voice_id is None or not q.contains("selected_voice_id"):
        if legacy_ref_enabled:
            s.selected_voice_id = preferred_voice_id(*search_dirs)
        else:
            s.selected_voice_id = DEFAULT_VOICE_ID
    else:
        migrated = str(stored_voice_id)
        if migrated == "tankvoice":
            migrated = "tankindycast"
        s.selected_voice_id = preferred_voice_id(*search_dirs, requested=migrated)
    return s


def save_settings(s: AppSettings) -> None:
    q = QSettings("ttser", "ttser")
    q.setValue("backend", s.backend)
    q.setValue("vulkan_device", s.vulkan_device)
    q.setValue("threads", s.threads)
    q.setValue("max_new_tokens", s.max_new_tokens)
    q.setValue("temperature", s.temperature)
    q.setValue("top_p", s.top_p)
    q.setValue("top_k", s.top_k)
    q.setValue("min_tokens_before_end", s.min_tokens_before_end)
    q.setValue("line_pause_ms", s.line_pause_ms)
    q.setValue("n_gpu_layers", s.n_gpu_layers)
    if s.codec_follow_backend is None:
        q.remove("codec_follow_backend")
    else:
        q.setValue("codec_follow_backend", int(s.codec_follow_backend))
    q.setValue("log_level", normalize_log_level(s.log_level))
    q.setValue("verbose", s.verbose)
    q.setValue("model_path", s.model_path)
    q.setValue("models_dir", s.models_dir)
    q.setValue("selected_model_id", s.selected_model_id)
    q.setValue("tokenizer_path", s.tokenizer_path)
    q.setValue("voice_dir", s.voice_dir)
    q.setValue("lib_cpu", s.lib_cpu)
    q.setValue("lib_vulkan", s.lib_vulkan)
    q.setValue("lib_cuda", s.lib_cuda)
    q.setValue("lib_metal", s.lib_metal)
    q.setValue("dictionary_paths", s.dictionary_paths)
    q.setValue("dictionaries_enabled", s.dictionaries_enabled)
    q.setValue("selected_voice_id", s.selected_voice_id)
    q.setValue("ui_language", normalize_language(s.ui_language))
