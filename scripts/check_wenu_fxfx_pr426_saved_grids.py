#!/usr/bin/env python3
"""Read-only check for reusing an existing MG5_aMC PR426 A/B integration.

Validates that the indicated Wenu Standard111 process has an existing
GF integration checkpoint and the intended, compiled FxFx cuts variant.
Does NOT start MadGraph, import pickle or modify any process files.

Usage: python3 scripts/check_wenu_fxfx_pr426_saved_grids.py before|after WORK
"""
import argparse
from pathlib import Path
import re
import sys

def values(card):
    result={}
    for raw in card.read_text(errors="replace").splitlines():
        line=raw.split("#",1)[0].split("!",1)[0]
        if "=" in line:
            a,b=line.rsplit("=",1)
            key=b.strip().lower()
            result[key]=a.strip()
    return result

def inspect(case,work):
    process=work/"PROCNLO_loop_sm-no_b_mass_0"
    if not process.is_dir():
        raise ValueError("missing NLO process: "+str(process))
    cuts=process/"SubProcesses/cuts.f"
    card=process/"Cards/run_card.dat"
    checkpoint=process/"SubProcesses/job_status.pkl"
    if not cuts.is_file() or not card.is_file():
        raise ValueError("missing cuts.f or run_card.dat")
    if not checkpoint.is_file() or checkpoint.stat().st_size==0:
        raise ValueError("missing non-empty job_status.pkl; no verified integration reuse")
    text=cuts.read_text(errors="replace")
    a=text.find("      logical function passcuts_fxfx(")
    b=text.find("      logical function passcuts_jets(",a+1)
    if a<0 or b<a:
        raise ValueError("FxFx function boundary missing")
    f=text[a:b]
    correct="amcatnlo_fastjetdmergemax(nQCD-2).lt.ptj**2" in f
    if correct!=(case=="after"):
        raise ValueError("unexpected PR426 FxFx variant: "+str(correct))
    x=values(card)
    required={"ickkw":"3","mcatnlo_delta":"False","folding":"1, 1, 1",
              "lhaid":"325100","event_norm":"bias"}
    for key,val in required.items():
        found=x.get(key)
        if found is None:
            raise ValueError("run card missing "+key)
        if key=="folding":
            if tuple(int(v) for v in re.split(r"[\s,]+",found) if v)!=(1,1,1):
                raise ValueError("wrong folding="+found)
        elif key=="mcatnlo_delta":
            if found.lower() not in ("false","f",".false.","0"):
                raise ValueError("not Standard111: mcatnlo_delta="+found)
        elif found.lower()!=val.lower():
            raise ValueError("wrong "+key+"="+found+" expected="+val)

    gf=list((process/"SubProcesses").glob("P*/GF*/mint_grids"))
    if not gf:
        raise ValueError("no GF mint_grids found; cannot certify reusable grids")
    # arrange_output() calls gunzip -f before validating systematic names;
    # when it fails, the physical original LHE is typically events.lhe.
    plain=process/"Events/run_01/events.lhe"
    zipped=process/"Events/run_01/events.lhe.gz"
    raw=plain if plain.is_file() else zipped
    if not raw.is_file() or raw.stat().st_size==0:
        raise ValueError("missing original 200-event LHE (plain or gzip)")
    # Validate the original small LHE; the wrapper exit code may be 8
    # because its failure happened later in arrange_output().
    import gzip
    reader = gzip.open if raw.suffix == ".gz" else open
    starts = ends = 0
    complete = False
    with reader(raw, "rt", errors="replace") as stream:
        for line in stream:
            starts += line.strip() == "<event>"
            ends += line.strip() == "</event>"
            complete |= "</LesHouchesEvents>" in line
    if starts != 200 or ends != 200 or not complete:
        raise ValueError("original LHE incomplete: %d opens %d closes" %
                         (starts, ends))
    print("AQP_FXFX_PR426_SAVED_GRIDS_PREFLIGHT_PASS")
    print("CASE",case)
    print("PROCESS",process)
    print("CHECKPOINT",checkpoint,"size",checkpoint.stat().st_size)
    print("GF_GRID_FILES",len(gf))
    print("PR426_PATCHED",correct)
    print("ORIGINAL_LHE",raw)
    print("RUN_CARD_NEV",x.get("nevents"))
    print("RUN_CARD_SEED",x.get("iseed"))
    return process

def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument("case",choices=("before","after"))
    a.add_argument("work",type=Path)
    args=a.parse_args()
    work=args.work.expanduser().resolve(strict=True)
    if not str(work).startswith("/home/aalida/AQP/fxfx_pr426_standard111_internal/"):
        a.error("Only support isolated Wenu FxFx PR426 process under known /home path")
    try:
        inspect(args.case,work)
    except (OSError,ValueError) as e:
        a.error(str(e))

if __name__=="__main__":
    main()
