from __future__ import annotations

import platform
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from engine.runtime import resource_root

if TYPE_CHECKING:
    from ttser.settings import AppSettings


def _library_filenames() -> dict[str, str]:
    if platform.system() == "Darwin":
        return {
            "lib_cpu": "libs2_cpu.dylib",
            "lib_vulkan": "libs2_vulkan.so",
            "lib_cuda": "libs2_cuda.so",
            "lib_metal": "libs2_metal.dylib",
        }
    return {
        "lib_cpu": "libs2_cpu.so",
        "lib_vulkan": "libs2_vulkan.so",
        "lib_cuda": "libs2_cuda.so",
        "lib_metal": "libs2_metal.dylib",
    }


def library_candidates(lib_attr: str) -> list[Path]:
    filename = _library_filenames()[lib_attr]
    root = resource_root()
    nested = {
        "lib_cpu": "cpu",
        "lib_metal": "metal",
        "lib_vulkan": "vulkan",
        "lib_cuda": "cuda",
    }.get(lib_attr)
    candidates = [root / "lib" / filename]
    if nested:
        candidates.insert(0, root / "lib" / nested / filename)
    if platform.system() == "Linux":
        candidates.append(root / "flatpak" / "prebuilt" / "linux-x86_64" / filename)
        build_name = {
            "lib_cpu": "build-cpu-sdk",
            "lib_vulkan": "build-vulkan-sdk",
            "lib_cuda": "build-cuda",
        }.get(lib_attr)
        if build_name:
            candidates.append(root / "s2.cpp" / build_name / "libs2.so")
    return candidates


def resolve_library_path(settings: AppSettings, lib_attr: str) -> Path:
    configured = Path(getattr(settings, lib_attr))
    if configured.is_file():
        return configured
    for candidate in library_candidates(lib_attr):
        if candidate.is_file():
            return candidate
    return configured


@dataclass(frozen=True)
class BackendSpec:
    id: str
    label: str
    backend_type: int
    lib_attr: str
    platforms: tuple[str, ...] | None = None

    def library_path(self, settings: AppSettings) -> Path:
        return resolve_library_path(settings, self.lib_attr)

    def uses_gpu_device(self) -> bool:
        return self.id in {"vulkan", "cuda", "metal"}


BACKENDS: tuple[BackendSpec, ...] = (
    BackendSpec("cpu", "CPU", -1, "lib_cpu"),
    BackendSpec("vulkan", "Vulkan", 0, "lib_vulkan", ("Linux",)),
    BackendSpec("cuda", "CUDA", 1, "lib_cuda", ("Linux",)),
    BackendSpec("metal", "Metal", 2, "lib_metal", ("Darwin",)),
)


def backend_by_id(backend_id: str) -> BackendSpec | None:
    for backend in BACKENDS:
        if backend.id == backend_id:
            return backend
    return None


def platform_backends() -> list[BackendSpec]:
    system = platform.system()
    return [b for b in BACKENDS if b.platforms is None or system in b.platforms]


def available_backends(settings: AppSettings) -> list[BackendSpec]:
    available: list[BackendSpec] = []
    for backend in platform_backends():
        if backend.id == "cpu" or backend.library_path(settings).is_file():
            available.append(backend)
    return available


def normalize_backend(settings: AppSettings) -> str:
    available = available_backends(settings)
    ids = {backend.id for backend in available}
    if settings.backend in ids:
        return settings.backend
    if "cpu" in ids:
        return "cpu"
    if available:
        return available[0].id
    return "cpu"


def library_path_for_backend(settings: AppSettings, backend_id: str | None = None) -> Path:
    backend = backend_by_id(backend_id or settings.backend)
    if backend is None:
        return resolve_library_path(settings, "lib_cpu")
    return backend.library_path(settings)


def library_search_path(settings: AppSettings, backend_id: str | None = None) -> Path:
    return library_path_for_backend(settings, backend_id).parent


def backend_type_for(settings: AppSettings, backend_id: str | None = None) -> int:
    backend = backend_by_id(backend_id or settings.backend)
    return backend.backend_type if backend else -1
