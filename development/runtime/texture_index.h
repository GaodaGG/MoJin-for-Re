/* SPDX-License-Identifier: GPL-3.0-or-later
 * An advisory index into the renderer's existing texture table. The full key
 * and mip descriptor still decide identity. Content hashes, invalidation,
 * uploads and ownership remain in tex_get. A stale slot after eviction/reset
 * can only miss: it is range checked and revalidated before use.
 * Include after TexEnt, TexMipKey, s_tex and s_tex_n are defined.
 */
static unsigned mojin_texture_slots[1024]; /* index + 1; zero means empty */
static int mojin_texture_index_enabled = -1;
static unsigned mojin_texture_slot(uint64_t key) {
    key ^= key >> 33;
    key *= UINT64_C(0xff51afd7ed558ccd);
    key ^= key >> 33;
    return (unsigned)key & 1023u;
}
static int mojin_texture_start(uint64_t key, const TexMipKey *mip) {
    if (mojin_texture_index_enabled < 0) {
        const char *linear = getenv("SR_MOJIN_TEXTURE_LINEAR");
        mojin_texture_index_enabled = !(linear && strcmp(linear,"1") == 0);
    }
    if (!mojin_texture_index_enabled) return 0;
    unsigned stored = mojin_texture_slots[mojin_texture_slot(key)];
    if (stored && stored <= (unsigned)s_tex_n) {
        unsigned i = stored - 1u;
        if (s_tex[i].key == key && memcmp(&s_tex[i].mip,mip,sizeof(*mip)) == 0)
            return (int)i;
    }
    return 0; /* Original ordered lookup, including every collision/miss. */
}
static void mojin_texture_found(uint64_t key, unsigned index) {
    if (mojin_texture_index_enabled)
        mojin_texture_slots[mojin_texture_slot(key)] = index + 1u;
}
