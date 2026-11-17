# Isolated graphics diagnosis; no generated game CPU code or CPU interpreter.
include Makefile
# Match the player frontend's selected runtime optimization, including its
# conservative floating-point and aliasing flags, instead of upstream's -O2 rule.
$(BUILD_DIR)/ge.o: $(MOJIN_DEV)/generated/runtime/ge.c $(MOJIN_DEV)/ge-replay.mk
	$(CC) $(CFLAGS) -fno-math-errno $(DEPFLAGS) -c $< -o $@
SDL3VK_SRCS := $(subst src/rt/gpu_sdl3vk/sdl3vk.c,$(MOJIN_DEV)/generated/runtime/sdl3vk.c,$(SDL3VK_SRCS))
GEGPU_SRCS := $(subst src/rt/gpu_sdl3vk/ge_gpu.c,$(MOJIN_DEV)/generated/runtime/ge_gpu.c,$(GEGPU_SRCS))
GEGPU_SRCS := $(subst src/rt/gpu_sdl3vk/glyph_recon.c,$(MOJIN_DEV)/generated/runtime/glyph_recon.c,$(GEGPU_SRCS))
GEGPU_SRCS += $(MOJIN_DEV)/runtime/preparation.c
