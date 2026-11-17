# Build and maintenance

Windows x64 is the tested platform. Install Git, Git LFS and Python 3.11+ before
bootstrapping. The fixed compiler/runtime prerequisite bundle supplies GCC 16.2,
SDL 3.4.20 and portable Python 3.15.2. A Vulkan driver is needed to play.
Use a build checkout path without spaces; the upstream Make targets cannot
represent spaces in an explicit build output path. Packaged games can use spaces
and Chinese paths.

## Clone and build without an ISO

```powershell
git -c core.autocrlf=false clone --no-checkout https://github.com/GaodaGG/MoJin-for-Re.git
cd MoJin-for-Re
git lfs install --local
git checkout main
git submodule update --init --recursive
git lfs pull
python development/tools/setup.py
python development/tools/build.py prepared --output-name mojin-isofree.exe
python development/tools/package_preview.py development/releases/local --exe mojin-isofree.exe
```

Double-click `development/releases/local/MoJin.exe`. The destination must be empty;
packaging refuses to overwrite existing settings or saves. To update a working
copy, use a fresh candidate directory and retain the previous package until the
new one has been tested. `play/`, `development/releases/`, test outputs and private
evidence are excluded from Git.

The explicit checkout avoids Git 2.45.1's clone-time LFS hook regression while
retaining clone protection. Git LFS installs its local hooks before that separate
checkout; no remote repository hook is supplied or run by this project. See the
[Git LFS discussion](https://github.com/git-lfs/git-lfs/discussions/5750) and
[Git 2.45.2 release notes](https://github.com/git/git/blob/v2.45.2/Documentation/RelNotes/2.45.2.txt).

`setup.py` fetches only the fixed upstream prerequisite archive and the pinned
Noto font/license. It verifies hashes before use. It does not install machine-wide
tools or change the machine's PATH. An existing verified download can be supplied
with `--archive <path>`. Offline use needs that archive and the pinned font files
already present at the paths recorded by `fetch_cjk_font.py`.

The prepared build consumes `development/prepared/game` and
`development/resources/game`. Git LFS pointers must be resolved; a missing payload
or changed hash stops the build. The original ISO and extracted ELF in
`development/inputs` are not read by this mode. Every native object is compiled
locally; no prebuilt game executable or object is a prepared input.

Upstream is a **submodule at one exact commit**, not a vendored copy. Keep it clean.
Local source adaptations are emitted into `development/generated/runtime` by
`prepare_runtime.py`, with pinned upstream anchors. To change the upstream
revision, review and revalidate these overlays rather than editing the submodule
in place or assuming a new release is compatible.

## Incremental builds and regenerated game code

Repeat the `build.py prepared` command to rebuild changed project runtime code.
The prepared manifest binds each generated C/header/data file and its generator
inputs. A changed lowering implementation or entry seed deliberately refuses the
old prepared set. Game-instruction changes must pass through static generation and
compilation; changing loaded MIPS bytes does not patch native code already built.

The existing original-input workflow remains available locally:

```powershell
python development/tools/disc_data.py extract
python development/tools/build.py all --output-name mojin-regenerated.exe
```

That workflow requires the exact local `魔法禁书目录.iso`, hash
`40469759cf0f033f8610f7920ab09b1866040d80b46ff0bdb16b03dfd137b9cb`.
No ISO should be committed. `prepared_game.py export --build <build.json>` freezes
new generated inputs into an empty `development/prepared/game`; preserve the old
set before replacing it. A manifest is an integrity/provenance record, not a grant
of rights to game material. See [COPYRIGHT.md](../COPYRIGHT.md).

## Visible diagnostics

After building `mojin-isofree.exe`, `development/Start-Visible-Battle.cmd` uses
private save/output directories and the controller script to enter vs CPU. It
hands input back to the user and exits when that game window is closed.
`probe.py --runtime-package development/releases/local` tests a packaged candidate
with a private save and a runtime PATH containing only System32.

Pillow 11.3.0 is used by image verification tools, not by the packaged game.
Diagnostic scripts that compare against original instructions or private captured
evidence require those additional local inputs; not every investigative script is
a clean-clone acceptance test.

Known future work: story and progression coverage; shared rendering defects;
timed 90/120 FPS validation; Windows-specific host-service isolation for Linux/macOS;
explicit state/animation/hitbox interfaces before promising new actions. Only
Windows has been built and run for this project.

## Retention and recovery

Keep `settings.ini`, `settings.ini.previous`, `saves`, `userdata` and `logs` when
updating. Never import a probe's save into normal play automatically. Runtime
resources are immutable; private packages may share regular hardlinks to avoid
duplicate physical data. Copy a resource before editing it for an experiment.

Record the Git commit, submodule commit, LFS OIDs, prepared manifest, tool archive
hash and candidate `.build.json`. A rebuild needs the corresponding LFS objects,
submodule source, fixed dependencies and font, even though it needs no ISO.
Revert to the previous tested package together with its matching runtime files;
keep user saves/settings separately. Do not delete directories just because they
are named cache, build or experiment.
