#!/usr/bin/env python3
"""Make a FULL isolated Δ441 JobOptions file for a local-multicore gridpack smoke test.

The original JO in /home is NEVER modified. This creates a complete copy
of its JO directory in /home/.../smoke_jo/100003/, and changes only
the gridpack-generation config to run_mode=2 and nb_core=4,
and explicitly initializes MGControl from the already-extracted madevent.  

Only the already-extracted input gridpack takes the gridpack branch.
There is no MadGraph reintegration. No files are written to /data here.
"""
import argparse
import ast
import re
import shutil
import sys
from pathlib import Path

BASENAME = "mc.aMCPy8EG_Wenu_FxFx_2jets_HT2bias_delta441.py"

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", required=True, help="Original full JO path in /home")
    ap.add_argument("--target-dir", required=True, help="New /home/.../smoke_jo/100003 directory")
    ap.add_argument("--cores", type=int, choices=(1, 2, 4, 8), default=4)
    a = ap.parse_args()
    src = Path(a.source).expanduser().resolve(strict=True)
    dst = Path(a.target_dir).expanduser().resolve()
    if not str(src).startswith("/home/") or not str(dst).startswith("/home/"):
        ap.error("Both source and target must be under /home")
    if src.name != BASENAME:
        ap.error("Source is not the expected original delta441 JO")
    if dst.exists():
        ap.error("Target already exists; refusing to overwrite: {}".format(dst))
    original = src.read_text()
    checks = (
        "if not is_gen_from_gridpack():",
        "MADGRAPH_GRIDPACK_LOCATION",
        "modify_config_card(",
        "modify_run_card(",
        "grid_pack=True",
    )
    for needle in checks:
        if needle not in original:
            raise ValueError("Expected JO component not found: {!r}".format(needle))
    if original.count("\nmodify_config_card(") != 1:
        raise ValueError("Expected exactly one top-level modify_config_card(...) call")
    marker = "\nmodify_config_card("
    patch = (
        "\n# Smoke test: use multicore execution within the HTCondor slot, NOT\n"
        "# MadGraph's nested HTCondor cluster mode. Only applies to an\n"
        "# already extracted gridpack; the original production JO is unchanged.\n"
        "if is_gen_from_gridpack():\n"
        "    config_settings['run_mode'] = 2\n"
        "    config_settings['nb_core'] = {}\n"
        "    print('AQP_DELTA441_SMOKE_LOCAL_MULTICORE={}')\n"
        "\n".format(a.cores, a.cores)
    )
    amended = original.replace(marker, patch + "modify_config_card(", 1)
    # A missing/extraction-failed gridpack MUST NOT fall through to
    # new_process() and trigger MINT0/1. Abort before that branch.
    fail_closed_guard = (
        "# AQP smoke safety: NEVER create a fresh process here.\n"
        "if not is_gen_from_gridpack():\n"
        "    raise RuntimeError('AQP_SMOKE_ABORT_NO_EXTRACTED_GRIDPACK')\n"
        "\n"
    )
    amended = amended.replace("if not is_gen_from_gridpack():",
                              fail_closed_guard + "if not is_gen_from_gridpack():", 1)

    # In the AthGeneration/23.6.63 legacy MGControl API, new_process()
    # normally initializes MadGraphUtils.my_MGC_instance. On gridpack
    # generation, new_process() is correctly skipped; however, the
    # release's modify_run_card() has no None guard and fails attempting
    # my_MGC_instance.runCardDict.update(settings). Initialize the
    # existing-gridpack-only object from 'madevent/' without relying on
    # the newer, release-incompatible pdf_setting constructor keyword.
    # Place this after MADGRAPH_PDFSETTING is defined and BEFORE the
    # first modify_run_card() call.
    if amended.count("\nmodify_run_card(") != 1:
        raise ValueError("Expected exactly one top-level modify_run_card call")
    mg_init = (
        "\n# AQP smoke fix: legacy MadGraphControl needs an MGControl object\n"
        "# when loading an already-extracted NLO gridpack. Never call\n"
        "# new_process() from this path: that would recreate integration.\n"
        "if is_gen_from_gridpack():\n"
        "    import MadGraphControl.MadGraphUtils as _aqp_mg_utils\n"
        "    import MadGraphControl.MGC as _aqp_mgc_module\n"
        "    from MadGraphControl.MGC import MGControl as _AQP_MGControl\n"
        "    import inspect as _aqp_inspect\n"
        "    _aqp_ctor = _aqp_inspect.signature(_AQP_MGControl.__init__)\n"
        "    print('AQP_DELTA441_MGCONTROL_CTOR_SIGNATURE=' + str(_aqp_ctor))\n"
        "    # The 23.6.63 MGControl constructor has no pdf_setting keyword.\n"
        "    # Preserve PDF configuration through the legacy module setting.\n"
        "    _aqp_mgc_module.MADGRAPH_PDFSETTING = (\n"
        "        _aqp_mg_utils.MADGRAPH_PDFSETTING\n"
        "    )\n"
        "    # Adapt only to the two known safe signatures: optional process\n"
        "    # or required process, without passing unsupported PDF kwargs.\n"
        "    _aqp_required = [\n"
        "        p for name, p in _aqp_ctor.parameters.items()\n"
        "        if name != 'self' and p.default is _aqp_inspect.Parameter.empty\n"
        "        and p.kind in (_aqp_inspect.Parameter.POSITIONAL_ONLY,\n"
        "                       _aqp_inspect.Parameter.POSITIONAL_OR_KEYWORD)\n"
        "    ]\n"
        "    if _aqp_mg_utils.my_MGC_instance is None:\n"
        "        if not _aqp_required:\n"
        "            _aqp_mg_utils.my_MGC_instance = _AQP_MGControl()\n"
        "        elif len(_aqp_required) == 1 and _aqp_required[0].name == 'process':\n"
        "            _aqp_mg_utils.my_MGC_instance = _AQP_MGControl(None)\n"
        "        else:\n"
        "            raise RuntimeError('AQP_SMOKE_ABORT_UNKNOWN_MGCONTROL_SIGNATURE')\n"
        "    _aqp_mgc = _aqp_mg_utils.my_MGC_instance\n"
        "    if hasattr(_aqp_mgc, 'pdf_setting'):\n"
        "        _aqp_mgc.pdf_setting = _aqp_mg_utils.MADGRAPH_PDFSETTING\n"
        "    if not getattr(_aqp_mgc, 'is_gen_from_gridpack', False):\n"
        "        raise RuntimeError('AQP_SMOKE_ABORT_MGCONTROL_NOT_GRIDPACK')\n"
        "    if _aqp_mgc.process_dir != str(MADGRAPH_GRIDPACK_LOCATION):\n"
        "        raise RuntimeError('AQP_SMOKE_ABORT_WRONG_PROCESS_DIR')\n"
        "    if not getattr(_aqp_mgc, 'isNLO', False):\n"
        "        raise RuntimeError('AQP_SMOKE_ABORT_NOT_NLO')\n"
        "    if not getattr(_aqp_mgc, 'runCardDict', None):\n"
        "        raise RuntimeError('AQP_SMOKE_ABORT_MISSING_RUN_CARD')\n"
        "    print('AQP_DELTA441_MGCONTROL_GRIDPACK_INIT_PASS')\n"
        "\n"
    )
    amended = amended.replace("\nmodify_run_card(", mg_init + "modify_run_card(", 1)

    # Parse, but DO NOT execute the JO outside Athena.
    ast.parse(amended, filename=str(src))
    if src.parent.is_symlink() or dst.parent.is_symlink():
        raise ValueError("JO parent may not be a symlink")

    # Stage only small local JO support files, not unknown bulk content.
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.mkdir()
    allowed = {".py", ".dat", ".f", ".inc", ".txt", ".cfg"}
    for f in src.parent.iterdir():
        if not f.is_file() or f.suffix not in allowed:
            continue
        if f.is_symlink():
            raise ValueError("Refusing source JO symlink: {}".format(f))
        if f.stat().st_size > 10 * 1024 * 1024:
            raise ValueError("Unexpected large JO companion file: {}".format(f))
        shutil.copy2(f, dst / f.name)
    jo_out = dst / BASENAME
    jo_out.write_text(amended)
    print("AQP_DELTA441_JO_SMOKE_PREP_PASS")
    print("Original (unchanged):", src)
    print("Full JO copy:", jo_out)
    print("Run-mode override: 2 (local multicore), cores:", a.cores)
    print("MGControl initialization: existing-gridpack branch only, no new_process")
    print("Original JO size:", len(original), "patched JO size:", len(amended))
    print("No new-process generation or MadGraph executable was invoked.")

if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, SyntaxError) as e:
        print("AQP_DELTA441_JO_SMOKE_PREP_FAILED:", e, file=sys.stderr)
        raise SystemExit(1)
