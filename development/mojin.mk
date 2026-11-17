# Project overlay; invoke from the pinned Nakagawa source directory.
# Both interpreter objects are replaced with fatal diagnostics.
include Makefile
$(BUILD_DIR)/iso_public.o: $(MOJIN_DEV)/runtime/disc_data.c $(MOJIN_DEV)/generated/runtime/disc_manifest.h
	$(CC) $(CFLAGS) $(DEPFLAGS) -c $< -o $@
RT_OBJS += $(BUILD_DIR)/mojin_graphics_settings.o
RT_OBJS += $(BUILD_DIR)/mojin_preparation.o
RT_OBJS += $(BUILD_DIR)/mojin_loop_trace.o
RT_OBJS += $(BUILD_DIR)/mojin_frame_clock.o
compile: $(BUILD_DIR)/mojin_graphics_settings.o
compile: $(BUILD_DIR)/mojin_preparation.o
compile: $(BUILD_DIR)/mojin_loop_trace.o
compile: $(BUILD_DIR)/mojin_frame_clock.o

$(BUILD_DIR)/mojin_frame_clock.o: $(MOJIN_DEV)/runtime/frame_clock.c
	$(CC) $(CFLAGS) $(DEPFLAGS) -c $< -o $@

$(BUILD_DIR)/mojin_loop_trace.o: $(MOJIN_DEV)/runtime/loop_trace.c
	$(CC) $(CFLAGS) $(DEPFLAGS) -c $< -o $@

$(BUILD_DIR)/mojin_preparation.o: $(MOJIN_DEV)/runtime/preparation.c $(MOJIN_DEV)/runtime/preparation.h
	$(CC) $(CFLAGS) $(DEPFLAGS) -c $< -o $@

$(BUILD_DIR)/mojin_graphics_settings.o: $(MOJIN_DEV)/runtime/graphics_settings.c $(MOJIN_DEV)/runtime/graphics_settings.h
	$(CC) $(CFLAGS) $(DEPFLAGS) -c $< -o $@

$(BUILD_DIR)/gui.o: $(MOJIN_DEV)/generated/runtime/gui.c $(MOJIN_DEV)/runtime/graphics_settings.h
	$(CC) $(CFLAGS) $(RT_NK_UI_FLAGS) $(DEPFLAGS) -c $< -o $@

$(BUILD_DIR)/overlay_quick.o: $(MOJIN_DEV)/generated/runtime/overlay_quick.c $(MOJIN_DEV)/runtime/graphics_settings_page.h $(MOJIN_DEV)/runtime/graphics_settings.h
	$(CC) $(CFLAGS) $(RT_NK_UI_FLAGS) $(DEPFLAGS) -c $< -o $@

$(BUILD_DIR)/nk_overlay.o: $(MOJIN_DEV)/generated/runtime/nk_overlay.c
	$(CC) $(CFLAGS) $(RT_NK_UI_FLAGS) $(DEPFLAGS) -c $< -o $@

$(BUILD_DIR)/overlay_host.o: $(MOJIN_DEV)/generated/runtime/overlay_host.c
	$(CC) $(CFLAGS) $(RT_NK_UI_FLAGS) $(DEPFLAGS) -c $< -o $@
# Local proof logic and private entry seeds are code-generation inputs too.
$(BUILD_DIR)/$(GAME_NAME)_recomp.c $(BUILD_DIR)/$(GAME_NAME)_recomp_funcs.h: $(MOJIN_DEV)/tools/entry_proof.py $(MOJIN_DEV)/inputs/dispatch-seeds.txt
ASSET_COPY_STEP = $(POWERSHELL) -NoProfile -ExecutionPolicy Bypass -File "$(MOJIN_DEV)/generated/runtime/copy_build_assets.ps1" -BuildDir "$(BUILD_DIR)" -ProjectFontDir "$(PROJECT_FONT_GENERATED_DIR)" -Sdl3DllPath "$(SDL3_DLL)" $(ASSET_COPY_ARGS)

$(BUILD_DIR)/guest_interp.o: $(MOJIN_DEV)/generated/runtime/aot_dispatch.c $(MOJIN_DEV)/runtime/aot_guard.c src/rt/guest_interp.h
	$(CC) $(CFLAGS) -DMOJIN_GUEST_GUARD -MMD -MP -c $< -o $@

$(BUILD_DIR)/vfpu_interp.o: $(MOJIN_DEV)/runtime/aot_guard.c src/rt/guest_interp.h
	$(CC) $(CFLAGS) -DMOJIN_VFPU_GUARD -MMD -MP -c $< -o $@

$(BUILD_DIR)/hle_network.o: $(MOJIN_DEV)/generated/runtime/hle_network.c $(MOJIN_DEV)/runtime/offline_adhoc.h $(MOJIN_DEV)/runtime/offline_matching.h
	$(CC) $(CFLAGS) $(HLE_INCLUDES) $(DEPFLAGS) -c $< -o $@

$(BUILD_DIR)/hle_rtc.o: $(MOJIN_DEV)/generated/runtime/hle_rtc.c
	$(CC) $(CFLAGS) $(HLE_INCLUDES) $(DEPFLAGS) -c $< -o $@

$(BUILD_DIR)/hle_utility.o: $(MOJIN_DEV)/generated/runtime/hle_utility.c
	$(CC) $(CFLAGS) $(HLE_INCLUDES) $(DEPFLAGS) -c $< -o $@

$(BUILD_DIR)/hle_display.o: $(MOJIN_DEV)/generated/runtime/hle_display.c $(MOJIN_DEV)/runtime/display_trace.h
	$(CC) $(CFLAGS) $(HLE_INCLUDES) $(DEPFLAGS) -c $< -o $@

$(BUILD_DIR)/hle_mpeg.o: $(MOJIN_DEV)/generated/runtime/hle_mpeg.c $(MOJIN_DEV)/runtime/media_trace.h
	$(CC) $(CFLAGS) $(HLE_INCLUDES) $(DEPFLAGS) -c $< -o $@

$(BUILD_DIR)/mpeg.o: $(MOJIN_DEV)/generated/runtime/mpeg.c
	$(CC) $(CFLAGS) $(DEPFLAGS) -c $< -o $@

$(BUILD_DIR)/hle_route.o: $(MOJIN_DEV)/generated/runtime/hle_route.c
	$(CC) $(CFLAGS) $(HLE_INCLUDES) $(DEPFLAGS) -c $< -o $@

$(BUILD_DIR)/sdl3vk.o: $(MOJIN_DEV)/generated/runtime/sdl3vk.c $(MOJIN_DEV)/runtime/window_pump.h $(MOJIN_DEV)/runtime/window_size.h
	$(CC) $(CFLAGS) $(DEPFLAGS) -c $< -o $@

$(BUILD_DIR)/driver.o: $(MOJIN_DEV)/generated/runtime/driver.c $(MOJIN_DEV)/runtime/standalone.h
	$(CC) $(CFLAGS) -I$(TITLE_CONFIG_DIR) $(DEPFLAGS) -c $< -o $@

$(BUILD_DIR)/ge_gpu.o: $(MOJIN_DEV)/generated/runtime/ge_gpu.c $(MOJIN_DEV)/generated/runtime/glyph_recon.h
	$(CC) $(CFLAGS) $(DEPFLAGS) -c $< -o $@

$(BUILD_DIR)/ge_capture.o: $(MOJIN_DEV)/generated/runtime/ge_capture.c $(MOJIN_DEV)/runtime/capture_stream.h
	$(CC) $(CFLAGS) $(DEPFLAGS) -c $< -o $@

$(BUILD_DIR)/glyph_recon.o: $(MOJIN_DEV)/generated/runtime/glyph_recon.c $(MOJIN_DEV)/generated/runtime/glyph_recon.h
	$(CC) $(CFLAGS) $(DEPFLAGS) -c $< -o $@

ifeq ($(OS),Windows_NT)
LDFLAGS += -mwindows
TITLE_ICON_OBJ = $(BUILD_DIR)/mojin_icon.o
compile: $(BUILD_DIR)/mojin_icon.o
$(BUILD_DIR)/mojin_icon.o: $(MOJIN_DEV)/assets/game.rc $(MOJIN_DEV)/assets/game.ico
	$(WINDRES) --codepage=65001 --input-format=rc --output-format=coff --include-dir=$(MOJIN_DEV)/assets -i $< -o $@
endif
