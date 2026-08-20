from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication

DEFAULT_LANGUAGE = "en"
SUPPORTED_LANGUAGES = frozenset({"en", "ru"})
LANGUAGES: tuple[tuple[str, str], ...] = (
    ("en", "English"),
    ("ru", "Русский"),
)

_CATALOG: dict[str, dict[str, str]] = {
    "en": {
        "main.title": "ttser — Fish Audio S2 Pro",
        "main.input": "Input",
        "main.text_btn": "Text...",
        "main.output_mp3": "Output MP3",
        "main.mp3_btn": "MP3...",
        "main.voice": "Voice",
        "main.create_voice": "Create voice",
        "main.apply_dicts": "Apply dictionaries",
        "main.settings": "Settings",
        "main.dictionaries": "Dictionaries",
        "main.synthesize": "Synthesize",
        "main.stop": "Stop",
        "main.pick_input": "Select text file",
        "main.pick_output": "Save MP3 as",
        "main.error": "Error",
        "main.input_not_found": "Input file not found",
        "main.library_not_found": "Library not found: {path}",
        "main.voice_not_found": "Voice profile not found: {voice_id}",
        "main.stopping": "Stopping synthesis...",
        "main.done": "Done",
        "main.mp3_created": "MP3 created:\n{path}",
        "main.synthesis_stopped": "Synthesis stopped.",
        "main.done_log": "Done: {output}",
        "main.error_log": "Error: {error}",
        "settings.title": "Settings",
        "settings.interface": "Interface",
        "settings.language": "Language",
        "settings.model_group": "Fish Audio S2 Pro Model",
        "settings.variant": "Variant",
        "settings.description": "Description",
        "settings.models_dir": "Models directory",
        "settings.model_path": "Model path",
        "settings.download": "Download model",
        "settings.already_downloaded": "Model already downloaded",
        "settings.pick_models_dir": "Models directory",
        "settings.resolving_size": "Resolving size...",
        "settings.download_done": "Done",
        "settings.model_downloaded": "Model downloaded:\n{path}",
        "settings.download_error": "Download error",
        "settings.size_label": "Size: {size}.",
        "settings.cuda_device": "CUDA device",
        "settings.vulkan_device": "Vulkan device",
        "settings.metal_device": "Metal device",
        "settings.gpu_device": "GPU device",
        "model.combo_label": "{title} ({size})",
        "model.q4_k_m.description": (
            "Fastest on CPU and smallest on disk. "
            "Useful as a fallback or when RAM is limited."
        ),
        "model.q4_k_m.size": "~3.3 GiB",
        "model.q8_0.description": (
            "Recommended quality profile. "
            "Best balance of sound and speed for everyday use."
        ),
        "model.q8_0.size": "~5.2 GiB",
        "model.f16.description": (
            "Maximum quality without quantizing the AR block. "
            "Much slower on CPU and needs a large amount of memory."
        ),
        "model.f16.size": "~9.2 GiB",
        "voice.default_label": "Model default voice",
        "voice.error.empty_name": "Enter a voice name",
        "voice.error.invalid_name": (
            "Voice name may only contain Latin letters, digits, _ and -"
        ),
        "voice.error.bundled_protected": (
            "Profile {name} is bundled and cannot be overwritten"
        ),
        "voice.error.audio_missing": "Specify an existing audio file",
        "voice.error.transcript_missing": "Enter the reference audio transcript",
        "voice.error.overwrite_title": "Overwrite?",
        "voice.error.overwrite_message": (
            "Profile {voice_id}.s2voice already exists. Overwrite?"
        ),
        "voice.error.reserved_name": (
            "Name {voice_id} is reserved for a bundled profile"
        ),
        "voice.error.model_missing": "Model not found. Download it in Settings.",
        "voice_create.title": "Create voice",
        "voice_create.name": "Name",
        "voice_create.audio": "Audio",
        "voice_create.transcript": "Transcript",
        "voice_create.transcript_placeholder": (
            "Exact text spoken in the reference audio"
        ),
        "voice_create.hint": (
            "A short 5–30 second clip (WAV or MP3) and an exact transcript are required."
        ),
        "voice_create.pick_audio": "Select reference audio",
        "dict.title": "Dictionaries",
        "dict.connected": "Connected dictionaries",
        "dict.attach_json": "Attach JSON",
        "dict.detach": "Detach",
        "dict.add_row": "Add row",
        "dict.delete_row": "Delete row",
        "dict.save": "Save",
        "dict.pick_json": "Select dictionary JSON",
        "dict.validation_error": "Dictionary error",
        "dict.unsaved_title": "Unsaved changes",
        "dict.unsaved_message": (
            "There are unsaved changes. Continue without saving?"
        ),
        "dict.rule_empty": "Rule #{idx}: 'from' and 'to' must be non-empty",
        "dict.rule_duplicate": "Duplicate 'from': {source}",
        "worker.pronunciation_replacements": "Pronunciation replacements: {total}",
        "worker.gpu_init_retry": "GPU pipeline died during init; retrying...",
        "worker.gpu_device_lost": (
            "Line {line} failed ({snippet}); retrying in a fresh process..."
        ),
        "worker.gpu_skip_line": (
            "Skipping line {line} after repeated GPU crash "
            "(inserted silence): {snippet}"
        ),
        "worker.gpu_pipeline_failed": (
            "GPU pipeline failed to start. Try the CPU backend or a smaller model."
        ),
        "worker.gpu_repeated_crash": "Synthesis stopped after repeated GPU crashes",
        "worker.no_lines": "No lines to synthesize",
        "download.downloading": "Downloading {filename}...",
        "dialog.ok": "OK",
        "dialog.cancel": "Cancel",
        "synth.title": "Synthesis parameters",
        "synth.start": "Synthesize",
        "synth.reset": "Reset",
        "synth.backend_hint": "Backend: {backend}",
        "synth.codec_cpu": "CPU",
        "synth.codec_gpu": "GPU",
        "synth.param.max_new_tokens.label": "Max tokens",
        "synth.param.max_new_tokens.help": (
            "Maximum number of tokens to generate for each line "
            "(--max-tokens). Quality often degrades after about 800 tokens "
            "(~37 s of audio); split long text into lines."
        ),
        "synth.param.temperature.label": "Temperature",
        "synth.param.temperature.help": (
            "Sampling temperature (--temperature). Higher values make speech "
            "more varied; lower values are more stable and predictable. Default 0.8."
        ),
        "synth.param.top_p.label": "Top-p",
        "synth.param.top_p.help": (
            "Nucleus sampling (--top-p). Only tokens within the top probability "
            "mass are considered. Default 0.8."
        ),
        "synth.param.top_k.label": "Top-k",
        "synth.param.top_k.help": (
            "Top-k sampling (--top-k). Limits candidates to the k most likely "
            "tokens. Default 30."
        ),
        "synth.param.min_tokens_before_end.label": "Min tokens before EOS",
        "synth.param.min_tokens_before_end.help": (
            "Minimum tokens before end-of-sequence is allowed "
            "(--min-tokens-before-end). 0 matches fish-speech defaults; "
            "non-zero values bias against early stopping."
        ),
        "synth.param.line_pause_ms.label": "Line pause (ms)",
        "synth.param.line_pause_ms.help": (
            "Silence appended after each synthesized line before WAV chunks "
            "are concatenated. This makes the joined MP3 sound less like hard "
            "cuts. 0 disables the extra gap. Default 180 ms, matching s2.cpp "
            "sentence_pause_ms. Explicit [pause ...] lines are left as-is, "
            "and a speech line is not padded when the next line is already a pause."
        ),
        "synth.param.threads.label": "Threads",
        "synth.param.threads.help": (
            "CPU worker threads (--threads). 0 uses hardware concurrency "
            "(or 4 if unavailable). Also used when encoding reference audio."
        ),
        "synth.param.log_level.label": "Log level",
        "synth.param.log_level.help": (
            "Runtime log verbosity (SetS2LogLevel): error, warn, info, or debug. "
            "Default is info."
        ),
        "synth.param.verbose.label": "Verbose generation",
        "synth.param.verbose.help": (
            "Extra per-step generation logging inside the model "
            "(GenerateParams.verbose)."
        ),
        "synth.param.n_gpu_layers.label": "GPU layers",
        "synth.param.n_gpu_layers.help": (
            "Transformer layers offloaded to GPU (--gpu-layers). "
            "-1 = all layers when a GPU backend is selected; 0 = CPU only. "
            "Fewer layers use less VRAM but are slower. The KV cache still "
            "goes to GPU when any layer is offloaded."
        ),
        "synth.param.gpu_device.label": "GPU device",
        "synth.param.gpu_device.help": (
            "GPU device index (--vulkan / --cuda). 0 is the first device."
        ),
        "synth.param.codec_follow_backend.label": "Audio codec",
        "synth.param.codec_follow_backend.help": (
            "Where the audio codec runs. CPU keeps the codec on the CPU "
            "(--codec-cpu). GPU lets the codec follow the selected backend "
            "(--codec-follow-backend / --codec-auto). Vulkan always uses the "
            "CPU codec: a GPU codec on shared iGPU memory creates a second "
            "Vulkan context and can decode to silence or truncated WAV files."
        ),
        "synth.log.error": "error",
        "synth.log.warn": "warn",
        "synth.log.info": "info",
        "synth.log.debug": "debug",
    },
    "ru": {
        "main.title": "ttser — Fish Audio S2 Pro",
        "main.input": "Вход",
        "main.text_btn": "Текст...",
        "main.output_mp3": "Выходной MP3",
        "main.mp3_btn": "MP3...",
        "main.voice": "Голос",
        "main.create_voice": "Создать голос",
        "main.apply_dicts": "Применять словари",
        "main.settings": "Настройки",
        "main.dictionaries": "Словари",
        "main.synthesize": "Синтез",
        "main.stop": "Стоп",
        "main.pick_input": "Выберите текст",
        "main.pick_output": "Куда сохранить mp3",
        "main.error": "Ошибка",
        "main.input_not_found": "Входной файл не найден",
        "main.library_not_found": "Библиотека не найдена: {path}",
        "main.voice_not_found": "Профиль голоса не найден: {voice_id}",
        "main.stopping": "Остановка синтеза...",
        "main.done": "Готово",
        "main.mp3_created": "MP3 создан:\n{path}",
        "main.synthesis_stopped": "Синтез остановлен.",
        "main.done_log": "Готово: {output}",
        "main.error_log": "Ошибка: {error}",
        "settings.title": "Настройки",
        "settings.interface": "Интерфейс",
        "settings.language": "Язык",
        "settings.model_group": "Модель Fish Audio S2 Pro",
        "settings.variant": "Вариант",
        "settings.description": "Описание",
        "settings.models_dir": "Каталог моделей",
        "settings.model_path": "Путь к модели",
        "settings.download": "Скачать модель",
        "settings.already_downloaded": "Модель уже скачана",
        "settings.pick_models_dir": "Каталог для моделей",
        "settings.resolving_size": "Определение размера...",
        "settings.download_done": "Готово",
        "settings.model_downloaded": "Модель скачана:\n{path}",
        "settings.download_error": "Ошибка скачивания",
        "settings.size_label": "Размер: {size}.",
        "settings.cuda_device": "CUDA device",
        "settings.vulkan_device": "Vulkan device",
        "settings.metal_device": "Metal device",
        "settings.gpu_device": "GPU device",
        "model.combo_label": "{title} ({size})",
        "model.q4_k_m.description": (
            "Быстрее на CPU и меньше занимает на диске. "
            "Подходит как запасной вариант или если мало RAM."
        ),
        "model.q4_k_m.size": "~3.3 ГиБ",
        "model.q8_0.description": (
            "Рекомендуемый профиль качества. "
            "Лучший баланс между звуком и скоростью для повседневной работы."
        ),
        "model.q8_0.size": "~5.2 ГиБ",
        "model.f16.description": (
            "Максимальное качество без квантования AR-блока. "
            "На CPU заметно медленнее, нужен большой объём памяти."
        ),
        "model.f16.size": "~9.2 ГиБ",
        "voice.default_label": "Стандартный голос модели",
        "voice.error.empty_name": "Укажите имя голоса",
        "voice.error.invalid_name": (
            "Имя голоса может содержать только латинские буквы, цифры, _ и -"
        ),
        "voice.error.bundled_protected": (
            "Профиль {name} встроен в приложение и не может быть перезаписан"
        ),
        "voice.error.audio_missing": "Укажите существующий аудиофайл",
        "voice.error.transcript_missing": "Укажите транскрипт reference-аудио",
        "voice.error.overwrite_title": "Перезаписать?",
        "voice.error.overwrite_message": (
            "Профиль {voice_id}.s2voice уже существует. Перезаписать?"
        ),
        "voice.error.reserved_name": (
            "Имя {voice_id} зарезервировано для встроенного профиля"
        ),
        "voice.error.model_missing": "Модель не найдена. Скачайте её в Настройках.",
        "voice_create.title": "Создать голос",
        "voice_create.name": "Имя",
        "voice_create.audio": "Аудио",
        "voice_create.transcript": "Транскрипт",
        "voice_create.transcript_placeholder": (
            "Точный текст, произнесённый в reference-аудио"
        ),
        "voice_create.hint": (
            "Нужен короткий клип 5–30 секунд (WAV или MP3) и точный транскрипт."
        ),
        "voice_create.pick_audio": "Выберите reference-аудио",
        "dict.title": "Словари",
        "dict.connected": "Подключенные словари",
        "dict.attach_json": "Подключить JSON",
        "dict.detach": "Отключить",
        "dict.add_row": "Добавить строку",
        "dict.delete_row": "Удалить строку",
        "dict.save": "Сохранить",
        "dict.pick_json": "Выбрать JSON словарь",
        "dict.validation_error": "Ошибка словаря",
        "dict.unsaved_title": "Несохраненные правки",
        "dict.unsaved_message": (
            "Есть несохраненные изменения. Продолжить без сохранения?"
        ),
        "dict.rule_empty": "Правило #{idx}: поля 'from' и 'to' не должны быть пустыми",
        "dict.rule_duplicate": "Дубликат 'from': {source}",
        "worker.pronunciation_replacements": "Замены произношения: {total}",
        "worker.gpu_init_retry": "GPU pipeline упал при инициализации; повтор...",
        "worker.gpu_device_lost": (
            "Строка {line} не удалась ({snippet}); повтор в новом процессе..."
        ),
        "worker.gpu_skip_line": (
            "Пропуск строки {line} после повторного сбоя GPU "
            "(вставлена тишина): {snippet}"
        ),
        "worker.gpu_pipeline_failed": (
            "Не удалось запустить GPU pipeline. "
            "Попробуйте CPU backend или модель меньше."
        ),
        "worker.gpu_repeated_crash": "Синтез остановлен после повторных сбоев GPU",
        "worker.no_lines": "Нет строк для синтеза",
        "download.downloading": "Скачивание {filename}...",
        "dialog.ok": "ОК",
        "dialog.cancel": "Отмена",
        "synth.title": "Параметры синтеза",
        "synth.start": "Синтез",
        "synth.reset": "Сброс",
        "synth.backend_hint": "Движок: {backend}",
        "synth.codec_cpu": "CPU",
        "synth.codec_gpu": "GPU",
        "synth.param.max_new_tokens.label": "Макс. токенов",
        "synth.param.max_new_tokens.help": (
            "Максимум токенов на строку (--max-tokens). После примерно 800 токенов "
            "(~37 с аудио) качество часто падает — длинный текст лучше разбивать "
            "на строки."
        ),
        "synth.param.temperature.label": "Температура",
        "synth.param.temperature.help": (
            "Температура сэмплирования (--temperature). Выше — речь разнообразнее; "
            "ниже — стабильнее и предсказуемее. По умолчанию 0.8."
        ),
        "synth.param.top_p.label": "Top-p",
        "synth.param.top_p.help": (
            "Nucleus sampling (--top-p). Учитываются только токены в верхней "
            "доле вероятностной массы. По умолчанию 0.8."
        ),
        "synth.param.top_k.label": "Top-k",
        "synth.param.top_k.help": (
            "Top-k sampling (--top-k). Ограничивает кандидатов k наиболее "
            "вероятными токенами. По умолчанию 30."
        ),
        "synth.param.min_tokens_before_end.label": "Мин. токенов до EOS",
        "synth.param.min_tokens_before_end.help": (
            "Минимум токенов до разрешения конца последовательности "
            "(--min-tokens-before-end). 0 — как в fish-speech; ненулевые значения "
            "сдерживают раннюю остановку."
        ),
        "synth.param.line_pause_ms.label": "Пауза после строки (мс)",
        "synth.param.line_pause_ms.help": (
            "Тишина в конце каждой озвученной строки перед склейкой WAV в MP3. "
            "Так стыки чанков звучат естественнее, а не как резкий монтаж. "
            "0 отключает добавление паузы. По умолчанию 180 мс, как sentence_pause_ms "
            "в s2.cpp. Строки [pause ...] не меняются; если следующая строка уже "
            "пауза, дополнительная тишина не добавляется."
        ),
        "synth.param.threads.label": "Потоки",
        "synth.param.threads.help": (
            "Число CPU-потоков (--threads). 0 — авто (число ядер или 4). "
            "Также используется при кодировании reference-аудио."
        ),
        "synth.param.log_level.label": "Уровень логов",
        "synth.param.log_level.help": (
            "Подробность логов (SetS2LogLevel): error, warn, info или debug. "
            "По умолчанию info."
        ),
        "synth.param.verbose.label": "Подробный генератор",
        "synth.param.verbose.help": (
            "Дополнительные пошаговые логи генерации "
            "(GenerateParams.verbose)."
        ),
        "synth.param.n_gpu_layers.label": "Слои на GPU",
        "synth.param.n_gpu_layers.help": (
            "Сколько слоёв трансформера вынести на GPU (--gpu-layers). "
            "-1 — все слои при GPU-бэкенде; 0 — только CPU. Меньше слоёв — "
            "меньше VRAM, но медленнее. KV-кэш всё равно на GPU, если "
            "хотя бы один слой на GPU."
        ),
        "synth.param.gpu_device.label": "GPU device",
        "synth.param.gpu_device.help": (
            "Индекс GPU-устройства (--vulkan / --cuda). 0 — первое устройство."
        ),
        "synth.param.codec_follow_backend.label": "Аудиокодек",
        "synth.param.codec_follow_backend.help": (
            "Где выполняется аудиокодек. CPU — кодек на процессоре (--codec-cpu). "
            "GPU — кодек следует выбранному бэкенду (--codec-follow-backend / "
            "--codec-auto). На Vulkan кодек всегда на CPU: GPU-кодек в общей "
            "памяти iGPU создаёт второй Vulkan-контекст и может записать тишину "
            "или обрезанный WAV."
        ),
        "synth.log.error": "error",
        "synth.log.warn": "warn",
        "synth.log.info": "info",
        "synth.log.debug": "debug",
    },
}

_current_language = DEFAULT_LANGUAGE
_qt_translator: QTranslator | None = None


def normalize_language(code: str | None) -> str:
    if code in SUPPORTED_LANGUAGES:
        return code
    return DEFAULT_LANGUAGE


def current_language() -> str:
    return _current_language


def set_language(code: str) -> None:
    global _current_language
    _current_language = normalize_language(code)


def t(key: str, **kwargs: object) -> str:
    lang = _current_language
    text = _CATALOG.get(lang, {}).get(key) or _CATALOG[DEFAULT_LANGUAGE].get(key) or key
    if kwargs:
        return text.format(**kwargs)
    return text


def model_description(model_id: str) -> str:
    return t(f"model.{model_id}.description")


def model_size_label(model_id: str) -> str:
    return t(f"model.{model_id}.size")


def model_combo_label(model_id: str, title: str) -> str:
    return t("model.combo_label", title=title, size=model_size_label(model_id))


def translate_voice_error(message: str) -> str:
    mapping = {
        "voice name is required": "voice.error.empty_name",
        "voice name may only contain Latin letters, digits, _ and -": "voice.error.invalid_name",
    }
    if message.startswith("bundled voice profile cannot be overwritten:"):
        name = message.split(":", 1)[1].strip()
        return t("voice.error.bundled_protected", name=name)
    key = mapping.get(message)
    if key:
        return t(key)
    return message


def translate_dict_validation_error(message: str) -> str:
    if message.startswith("Rule #"):
        parts = message.split(":", 1)
        if len(parts) == 2 and "'from' and 'to' must be non-empty" in parts[1]:
            idx = parts[0].replace("Rule #", "").strip()
            return t("dict.rule_empty", idx=idx)
    if message.startswith("Duplicate 'from':"):
        source = message.split(":", 1)[1].strip()
        return t("dict.rule_duplicate", source=source)
    return message


def apply_language(app: QApplication, code: str) -> None:
    global _qt_translator
    set_language(code)
    if _qt_translator is not None:
        app.removeTranslator(_qt_translator)
        _qt_translator = None
    if code == "ru":
        _qt_translator = QTranslator(app)
        translations_path = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
        if _qt_translator.load(QLocale("ru"), "qtbase", "_", translations_path):
            app.installTranslator(_qt_translator)
        elif _qt_translator.load(QLocale("ru"), "qt", "_", translations_path):
            app.installTranslator(_qt_translator)
        else:
            _qt_translator = None
