/* Diagnostic capture only: preserve bytes when consumed, not untouched future
 * commands in a page that the CPU is still constructing behind a GE stall.
 * A static page fixture cannot encode two values read from the same byte. Refuse
 * such a capture rather than silently choosing one. A GE-produced RAM write can
 * also trigger this conservative refusal; temporal write replay is not modeled.
 * The original eager VRAM preimage is retained for renderer-produced pixels. */
void ge_capture_note_memory(uint32_t addr, uint32_t bytes) {
    if (!s_capture.active || bytes == 0) return;
    uint64_t first = SR_PHYS(addr), last = first + (uint64_t)bytes - 1u;
    if (first >= GE_CAPTURE_ARENA_SIZE || last >= GE_CAPTURE_ARENA_SIZE) return;
    uint32_t first_page = (uint32_t)first / GE_CAPTURE_PAGE_SIZE;
    uint32_t last_page = (uint32_t)last / GE_CAPTURE_PAGE_SIZE;
    for (uint32_t index = first_page; index <= last_page; index++) {
        uint32_t page_addr = index * GE_CAPTURE_PAGE_SIZE;
        if (page_addr >= GE_CAPTURE_VRAM_BASE &&
            page_addr < GE_CAPTURE_VRAM_BASE + GE_CAPTURE_VRAM_SIZE) continue;
        if (!s_capture.seen[index]) {
            if (!append_page(page_addr)) {
                fprintf(stderr, "GE_CAPTURE: out of memory while saving page 0x%08x\n", page_addr);
                ge_capture_abort();
                return;
            }
            s_capture.seen[index] = s_capture.fixture.page_count;
        }
        GeCapturePage *page = &s_capture.fixture.pages[s_capture.seen[index] - 1u];
        const uint8_t *live = SR_HOST(page_addr);
        uint32_t lo = first > page_addr ? (uint32_t)(first - page_addr) : 0;
        uint32_t hi = last < (uint64_t)page_addr + GE_CAPTURE_PAGE_SIZE
            ? (uint32_t)(last - page_addr) : GE_CAPTURE_PAGE_SIZE - 1u;
        for (uint32_t offset = lo; offset <= hi; offset++) {
            uint32_t at = page_addr + offset;
            uint8_t bit = (uint8_t)(1u << (at & 7u));
            uint8_t *observed = &s_capture.observed[at >> 3u];
            if ((*observed & bit) && page->data[offset] != live[offset]) {
                s_mojin_capture_refused = 1;
                s_mojin_refused_frame = s_capture.fixture.frame;
                fprintf(stderr, "MOJIN_GE_CAPTURE_REFUSED frame=%u reason=memory-reread-changed addr=0x%08x old=%02x new=%02x\n",
                        s_capture.fixture.frame, at, page->data[offset], live[offset]);
                ge_capture_abort();
                return;
            }
            if (!(*observed & bit)) {
                s_capture.late_bytes += page->data[offset] != live[offset];
                page->data[offset] = live[offset];
                *observed |= bit;
            }
        }
    }
}
