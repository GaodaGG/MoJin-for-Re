# Copyright, licensing and attribution

This is an unofficial experimental port. It is not affiliated with or endorsed by
the original game's rights holders, Sony Interactive Entertainment, the Nakagawa
authors, the PPSSPP authors, or OpenAI. Game and platform names identify the target
software and compatibility only.

## Project code

Copyrightable project contributions by the MoJin-for-Re contributors are offered
under **GPL-3.0-or-later**, unless a file carries a different existing notice.
See [LICENSE](LICENSE). Preserve upstream copyright and license notices. This
license statement does not claim ownership of third-party material or resolve
whether any particular AI-assisted output is independently copyrightable.

## Original game and generated inputs

The repository's prepared game-specific C, relocated image, extracted game files,
and converted icon are derived from the supplied game build. They are **not
relicensed as project-owned GPL material** by this notice. No additional license
to the original game, its audiovisual material, trademarks, or other proprietary
content is granted here. Availability in a Git repository is not proof of
permission to redistribute, relicense, or commercially exploit those materials.

Relevant paths:

- `development/prepared/game/`: translated game C, headers, imports and relocated image.
- `development/resources/game/`: extracted files, including original program and audiovisual data.
- `development/assets/game.ico`: icon converted from original game artwork.

The [official KADOKAWA PSP product page](https://www.kadokawa.co.jp/product/game1627/)
displays the following attribution:

> ©鎌池和馬／アスキー・メディアワークス／PROJECT-INDEX II ©2011 ASCII MEDIA WORKS Inc.

This credits the published work; it is not an authorization of this project or a
complete chain-of-title determination for each component. Additional modifications
or translations in the supplied build may have separate authors. The repository
does not assert that a game redistribution authorization has been obtained.
Combined executable distribution also needs appropriate rights and license
compatibility; this exclusion notice alone does not establish either.

## Third-party software

- [Nakagawa-Recomp](https://github.com/Jstar269/Nakagawa-Recomp), pinned submodule
  `2263985dd8882acbbf1a7313f3752979e7f88e2d`: GPL-3.0-or-later at project level,
  with per-file upstream terms. Retain its LICENSE, NOTICE.md, CREDITS.md and
  provenance records. Local changes are generated overlays; the submodule is
  unmodified. The submodule's statement that *its* repository contains no game
  files does not describe the game-derived directories in this parent project.
- [PPSSPP](https://github.com/hrydgard/ppsspp), direct semantic reference
  `4392fe67d06f8a88c317641daa71595f8c540de8`: GPL-2.0-or-later and per-file terms.
  Code adapted through Nakagawa retains its recorded lineage. No PPSSPP executable
  is launched by this port.
- Noto CJK SC Sans 2.004, pinned source
  `523d033d6cb47f4a80c58a35753646f5c3608a78`: SIL OFL 1.1; the setup script downloads
  the font together with its verified license.
- SDL, FFmpeg-derived codecs and other bundled runtime dependencies retain their
  respective licenses. The packaging step includes upstream third-party notices.
  Supplying notices does not replace applicable corresponding-source obligations.

See [AI_DISCLOSURE.md](AI_DISCLOSURE.md) for the substantial AI involvement in this
project. For a concern about this repository, contact the
[maintainer](https://github.com/GaodaGG).
