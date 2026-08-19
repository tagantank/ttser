from __future__ import annotations

import os
import platform
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QSettings

from engine.s2_voice import DEFAULT_VOICE_ID, preferred_voice_id, voice_search_dirs
from ttser.backends import normalize_backend, resolve_library_path
from ttser.i18n import DEFAULT_LANGUAGE, normalize_language
from ttser.model_catalog import find_downloaded_model, model_by_filename, model_by_id


def default_dictionary_paths() -> list[str]:
    in_flatpak = os.environ.get("FLATPAK_ID") == "com.tagantank.ttser"
    if in_flatpak:
        base = "/app/share/ttser/dictionaries"
        return [
            f"{base}/s2_terms_ru.json",
            f"{base}/s2_pronunciation_ru.json",
        ]
    return [
        "dictionaries/s2_terms_ru.json",
        "dictionaries/s2_pronunciation_ru.json",
    ]


def default_models_dir() -> str:
    in_flatpak = os.environ.get("FLATPAK_ID") == "com.tagantank.ttser"
    if in_flatpak:
        return str(Path.home() / ".var" / "app" / "com.tagantank.ttser" / "data" / "models")
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
    in_flatpak = os.environ.get("FLATPAK_ID") == "com.tagantank.ttser"
    if in_flatpak:
        return "/app/share/ttser/voices"
    return "voices"


@dataclass
class AppSettings:
    backend: str = "cpu"
    vulkan_device: int = 0
    threads: int = 8
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


def _adjust_defaults(settings: AppSettings) -> None:
    in_flatpak = os.environ.get("FLATPAK_ID") == "com.tagantank.ttser"
    if in_flatpak:
        settings.lib_cpu = "/app/lib/ttser/libs2_cpu.so"
        settings.lib_vulkan = "/app/lib/ttser/libs2_vulkan.so"
        settings.lib_cuda = "/app/lib/ttser/libs2_cuda.so"
        settings.lib_metal = "/app/lib/ttser/libs2_metal.dylib"
        settings.tokenizer_path = "/app/share/ttser/tokenizer.json"
        settings.voice_dir = default_voice_dir()
    if platform.system() == "Darwin":
        settings.lib_cpu = "lib/libs2_cpu.dylib"
        if settings.backend in {"vulkan", "cuda"}:
            settings.backend = "cpu"
        if in_flatpak:
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
    in_flatpak = os.environ.get("FLATPAK_ID") == "com.tagantank.ttser"
    default_tokenizer = "/app/share/ttser/tokenizer.json" if in_flatpak else "s2.cpp/tokenizer.json"
    default_cpu = "/app/lib/ttser/libs2_cpu.so" if in_flatpak else "lib/libs2_cpu.so"
    default_vk = "/app/lib/ttser/libs2_vulkan.so" if in_flatpak else "lib/libs2_vulkan.so"
    default_cuda = "/app/lib/ttser/libs2_cuda.so" if in_flatpak else "lib/libs2_cuda.so"
    default_metal = "/app/lib/ttser/libs2_metal.dylib" if in_flatpak else "lib/libs2_metal.dylib"
    default_dicts = default_dictionary_paths()
    stored_voice_id = q.value("selected_voice_id")
    legacy_ref_enabled = bool(q.value("reference_voice_enabled", False))
    s = AppSettings(
        backend=q.value("backend", "cpu"),
        vulkan_device=int(q.value("vulkan_device", 0)),
        threads=int(q.value("threads", 8)),
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
