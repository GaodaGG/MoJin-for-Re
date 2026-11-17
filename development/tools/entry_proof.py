"""Accept an observed entry only when it is an existing callable after leading NOPs.

SPDX-License-Identifier: GPL-3.0-or-later
This extends the build-time proof, not the runtime. It never makes an interior
frame callable: the predecessor must already have the callable emission contract,
and the entire skipped prefix must be canonical NOP words. The new body starts at
the requested address and still passes the upstream emitter checks.
"""
from bisect import bisect_left


def equivalent_prefix(elf, address, catalog, ranges):
    if address & 3 or address in catalog:
        return None
    starts = sorted(catalog)
    index = bisect_left(starts, address)
    if index == 0:
        return None
    prior = starts[index - 1]
    info = catalog[prior]
    if not info.callable or info.resumable:
        return None
    # Restrict this proof to a short alignment prefix contained in one code span.
    if not 0 < address - prior <= 60 or not any(lo <= prior < address < hi for lo, hi in ranges):
        return None
    raw = elf.read_at_vaddr(prior, address - prior)
    if raw != b"\0" * (address - prior):
        return None
    return prior


def install(upstream):
    import analyze as analysis
    original_analyze = upstream.analyze

    def analyze_with_prefix_proof(elf, *args, **kwargs):
        if not kwargs.get("seeds"):
            return original_analyze(elf, *args, **kwargs)
        original_resolve = analysis._resolve_seeds

        def resolve(unseeded, run, seeds, seed_check, report):
            catalog = upstream.build_entry_catalog(*unseeded, elf=elf)
            proven = {address: prior for address in seeds
                      if (prior := equivalent_prefix(elf, address, catalog, unseeded[1])) is not None}
            original_check = analysis._seed_not_callable

            def check(discovery, address):
                verdict = original_check(discovery, address)
                # A positive frame release is never excused by this proof.
                if (discovery.elf is elf and address in proven and verdict is not None
                        and not verdict[1] and "indeterminate" in verdict[0]):
                    return None
                return verdict

            analysis._seed_not_callable = check
            try:
                result = original_resolve(unseeded, run, seeds, seed_check, report)
            finally:
                analysis._seed_not_callable = original_check
            for address, prior in sorted(proven.items()):
                if address in result[0]:
                    print(f"MOJIN_ENTRY_PROOF target=0x{address:08x} callable=0x{prior:08x} "
                          f"leading_nops={(address-prior)//4}")
            return result

        analysis._resolve_seeds = resolve
        try:
            result = original_analyze(elf, *args, **kwargs)
        finally:
            analysis._resolve_seeds = original_resolve
        outcome = kwargs.get("report", {}).get("miss_seeds", {})
        rejected = {address: why for address, why in outcome.items()
                    if why not in (analysis.SEED_APPLIED, analysis.SEED_KNOWN)}
        if rejected:
            raise ValueError("Requested static entries were refused: " + ", ".join(
                f"0x{address:08x}: {why}" for address, why in sorted(rejected.items())))
        return result

    upstream.analyze = analyze_with_prefix_proof
