#!/usr/bin/env python3
"""Prepare an isolated MG5_aMC FxFx exclusive-kT patch (upstream PR #426).

Source of truth: https://github.com/mg5amcnlo/mg5amcnlo/pull/426
Target: Template/NLO/SubProcesses/cuts.f, passcuts_fxfx().
Compatible only if the target contains the EXACT known old code fragment;
otherwise fails closed. No MadGraph imports, no gridpack operations, no runs.

Default: read-only diff.
--write: create a new patched cuts.f outside CVMFS, /data and any production
tree; never overwrite an existing path. The original source is unmodified.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import re
from pathlib import Path

OLD_DECL = "      double precision rfj,sycut,palg,amcatnlo_fastjetdmerge,etaj_max\n"
NEW_DECL = (
    "      double precision rfj,sycut,palg,amcatnlo_fastjetdmergemax\n"
    "      external amcatnlo_fastjetdmergemax\n"
)
OLD_SELECT = """c First apply a numerical stability cut
c Define jet clustering parameters with a pTmin=1 GeV
      palg=1d0                  ! jet algorithm: 1.0=kt, 0.0=C/A, -1.0 = anti-kt
      rfj=1d0                   ! the radius parameter
      sycut=ptj                 ! minimum transverse momentum
      etaj_max=1000d0
c     call FASTJET to get all the jets
      call amcatnlo_fastjetppgenkt_etamax_timed(
     $     pQCD,nQCD,rfj,sycut,etaj_max,palg,pjet,njet,jet)
c     Apply the jet cut
      if (njet .ne. nQCD .and. njet .ne. nQCD-1) then
         passcuts_fxfx=.false.
         return
      endif
"""
NEW_SELECT = """c Require at least nQCD-1 jets resolved at the generation kT scale.
c nQCD includes the zero-momentum FKS slot for Born/counterevents.
c Use the exclusive resolution, as in the Pythia FxFx veto: counting
c inclusive R=1 jets removes hard collinear configurations even when
c their kT separation is above the merging scale.
      if (nQCD.gt.1 .and. ptj.gt.0d0) then
         palg=1d0
         rfj=1d0
         sycut=0d0
         call amcatnlo_fastjetppgenkt_timed(
     $        pQCD,nQCD,rfj,sycut,palg,pjet,njet,jet)
         if (amcatnlo_fastjetdmergemax(nQCD-2).lt.ptj**2) then
            passcuts_fxfx=.false.
            return
         endif
      endif
"""
START = "      logical function passcuts_fxfx(p,pQCD,nQCD)"
NEXT = "      logical function passcuts_jets("


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def patched_text(source: str) -> str:
    if source.count(START) != 1 or source.count(NEXT) != 1:
        raise ValueError("Unexpected passcuts_fxfx / passcuts_jets boundaries")
    pre, remainder = source.split(START, 1)
    function, post = remainder.split(NEXT, 1)
    if function.count(OLD_DECL) != 1 or function.count(OLD_SELECT) != 1:
        raise ValueError(
            "Unexpected original FxFx source. Do not patch automatically; "
            "inspect ATLAS 3.5.11 source and upstream PR #426."
        )
    if ("amcatnlo_fastjetdmergemax" in function or
            "amcatnlo_fastjetppgenkt_timed(" in function):
        raise ValueError("Source is partly/fully patched already; refuse mixed state")
    function = function.replace(OLD_DECL, NEW_DECL, 1)
    function = function.replace(OLD_SELECT, NEW_SELECT, 1)
    candidate = pre + START + function + NEXT + post
    if candidate == source:
        raise ValueError("No changes made")
    # Verify the only changes are within passcuts_fxfx and both replacements
    # are exactly what upstream PR #426 intended.
    bprefix, brest = source.split(START, 1)
    bfunction, bsuffix = brest.split(NEXT, 1)
    aprefix, arest = candidate.split(START, 1)
    afunction, asuffix = arest.split(NEXT, 1)
    if (bprefix != aprefix or bsuffix != asuffix or
            afunction != bfunction.replace(OLD_DECL, NEW_DECL, 1)
                                  .replace(OLD_SELECT, NEW_SELECT, 1)):
        raise ValueError("Patch changed unexpected source regions")
    return candidate


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    src = args.source.expanduser().resolve(strict=True)
    if not src.is_file() or src.name != "cuts.f":
        parser.error("--source must point to an existing cuts.f")
    original = src.read_bytes()
    try:
        original_text = original.decode("utf-8")
        candidate = patched_text(original_text)
    except (UnicodeDecodeError, ValueError) as exc:
        parser.error(str(exc))
    print("SOURCE_SHA256", sha256(original))
    print("CANDIDATE_SHA256", sha256(candidate.encode()))
    print("PR426_EXCLUSIVE_KT_FXFX_PATCH_VERIFIED")
    print("".join(difflib.unified_diff(
        original_text.splitlines(keepends=True),
        candidate.splitlines(keepends=True),
        fromfile="before/cuts.f", tofile="after/cuts.f", n=3,
    )))
    if not args.write:
        print("DRY_RUN_ONLY; nothing was modified")
        return
    if args.output is None:
        parser.error("--write requires --output")
    out = args.output.expanduser().absolute()
    if (out.name != "cuts.f" or out.exists() or out.is_symlink() or out == src
            or not out.parent.is_dir()):
        parser.error("Output must be a NEW cuts.f inside an existing directory")
    if (str(out).startswith("/cvmfs/") or str(out).startswith("/data/") or
            "/Wjets/WENU/" in str(out) or "/Zjets/" in str(out)):
        parser.error("Refusing output in CVMFS, Ceph, or existing production trees")
    with out.open("x", encoding="utf-8") as stream:
        stream.write(candidate)
    print("PATCHED_COPY_CREATED", out)
    print("ORIGINAL_UNCHANGED; PATCH_NOT_INSTALLED_IN_MADGRAPH")


if __name__ == "__main__":
    main()
