# Fixed dependencies

| Component | Pinned identity | Retrieval |
| --- | --- | --- |
| Nakagawa-Recomp | v0.0.3, commit `2263985dd8882acbbf1a7313f3752979e7f88e2d` | Git submodule at `development/third_party/nakagawa` |
| Windows prerequisites | Release archive SHA256 `af52764c7f25d55759cc05545aeb7bc7a6ca1f51aa223dc4ddb47d7bff760a0d`, 276,957,044 bytes | [Official release asset](https://github.com/Jstar269/Nakagawa-Recomp/releases/download/v0.0.3/nakagawa-recomp-0.0.3-windows-x64.zip) |
| Compiler / build Python / SDL | GCC 16.2 / portable Python 3.15.2 / SDL 3.4.20 | Verified prerequisite archive, extracted by `bootstrap_toolchain.py` |
| Chinese settings font | Noto CJK SC Sans 2.004, revision `523d033d6cb47f4a80c58a35753646f5c3608a78` | `fetch_cjk_font.py`, with SHA-256 verification of both OTF and OFL license |
| PPSSPP reference | `4392fe67d06f8a88c317641daa71595f8c540de8` | Semantic reference only; no separate checkout or executable required for this build |
| Git LFS | Local validation used 3.5.1 | Install with Git; required to materialize game resources and relocated image |
| Host Python | 3.11+; local validation used 3.13.5 | User-installed bootstrap/diagnostic dependency |
| Pillow | 11.3.0 used for image verification | Optional diagnostic dependency, not a runtime or prepared-build requirement |

Source/runtime license details remain in each upstream's notices; see
[COPYRIGHT.md](../COPYRIGHT.md). This pin list records the tested versions and
does not imply current universal PSP game support or compatibility with later
upstream releases. The native package uses the system's Vulkan driver.
