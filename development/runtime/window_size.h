/* SPDX-License-Identifier: GPL-3.0-or-later
 * Window output is independent of GE rendering and SSAA. The swapchain's
 * logged dimensions remain authoritative if the desktop limits this request.
 */
static int mojin_window_dimension(int axis) {
    const char *value = getenv("SR_MOJIN_WINDOW_SIZE");
    int w = 960, h = 544;
    char extra;
    if (value && (sscanf(value, "%dx%d%c", &w, &h, &extra) != 2 ||
                  w < 480 || h < 272 || w > 3840 || h > 2176)) {
        fprintf(stderr, "MOJIN_WINDOW_SIZE invalid: %s\n", value);
        abort();
    }
    if (!axis) fprintf(stderr, "MOJIN_WINDOW_SIZE requested=%dx%d (output only)\n", w, h);
    return axis ? h : w;
}
