SHELL := /usr/bin/env bash
.SHELLFLAGS := -eu -o pipefail -c

PYTHON ?= python3
CMAKE ?= cmake
JOBS ?= 8

S2_DIR ?= s2.cpp
LIB_DIR ?= lib

.PHONY: app init-submodule lib-cpu lib-vulkan lib-cuda lib-metal libs save-voice

app:
	$(PYTHON) -m ttser

init-submodule:
	git submodule update --init --recursive

lib-cpu:
	$(CMAKE) -S "$(S2_DIR)" -B "$(S2_DIR)/build-cpu" -DCMAKE_BUILD_TYPE=Release -DS2_BUILD_SHARED_LIBRARIES=ON
	$(CMAKE) --build "$(S2_DIR)/build-cpu" --config Release -j $(JOBS)
	mkdir -p "$(LIB_DIR)"
	cp "$(S2_DIR)/build-cpu/libs2.$(shell uname | sed 's/Linux/so/; s/Darwin/dylib/')" "$(LIB_DIR)/libs2_cpu.$(shell uname | sed 's/Linux/so/; s/Darwin/dylib/')"

lib-vulkan:
	@if [[ "$$(uname)" != "Linux" ]]; then echo "lib-vulkan is Linux only"; exit 1; fi
	$(CMAKE) -S "$(S2_DIR)" -B "$(S2_DIR)/build-vulkan" -DCMAKE_BUILD_TYPE=Release -DS2_VULKAN=ON -DS2_BUILD_SHARED_LIBRARIES=ON
	$(CMAKE) --build "$(S2_DIR)/build-vulkan" --config Release -j $(JOBS)
	mkdir -p "$(LIB_DIR)"
	cp "$(S2_DIR)/build-vulkan/libs2.so" "$(LIB_DIR)/libs2_vulkan.so"

lib-cuda:
	@if [[ "$$(uname)" != "Linux" ]]; then echo "lib-cuda is Linux only"; exit 1; fi
	$(CMAKE) -S "$(S2_DIR)" -B "$(S2_DIR)/build-cuda" -DCMAKE_BUILD_TYPE=Release -DS2_CUDA=ON -DS2_BUILD_SHARED_LIBRARIES=ON
	$(CMAKE) --build "$(S2_DIR)/build-cuda" --config Release -j $(JOBS)
	mkdir -p "$(LIB_DIR)"
	cp "$(S2_DIR)/build-cuda/libs2.so" "$(LIB_DIR)/libs2_cuda.so"

lib-dev:
	@mkdir -p "$(LIB_DIR)"
	@for f in flatpak/prebuilt/linux-x86_64/*.so; do ln -sf "../$$f" "$(LIB_DIR)/$$(basename "$$f")"; done
	@echo "Linked prebuilt libs into $(LIB_DIR)/"

lib-metal:
	@if [[ "$$(uname)" != "Darwin" ]]; then echo "lib-metal is macOS only"; exit 1; fi
	$(CMAKE) -S "$(S2_DIR)" -B "$(S2_DIR)/build-metal" -DCMAKE_BUILD_TYPE=Release -DS2_METAL=ON -DS2_BUILD_SHARED_LIBRARIES=ON -DGGML_METAL_EMBED_LIBRARY=ON
	$(CMAKE) --build "$(S2_DIR)/build-metal" --config Release -j $(JOBS)
	mkdir -p "$(LIB_DIR)"
	cp "$(S2_DIR)/build-metal/libs2.dylib" "$(LIB_DIR)/libs2_metal.dylib"

libs: lib-cpu
	@if [[ "$$(uname)" == "Linux" ]]; then $(MAKE) lib-vulkan; fi
	@if [[ "$$(uname)" == "Darwin" ]]; then $(MAKE) lib-metal; fi

save-voice:
	@echo "Use s2 CLI from build-* with --save-voice."
