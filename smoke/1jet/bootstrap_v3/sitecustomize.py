"""Load one source-pinned AQP Condor candidate for the isolated reweight replay (v3 candidate).

Works with both madgraph.various.cluster and generated internal.cluster.
Does not change CVMFS or an existing MadGraph process.
"""
import hashlib
import importlib.util
import os
import sys
from importlib.machinery import PathFinder, SourceFileLoader

# Python imports only the first sitecustomize.py on sys.path. Preserve the
# AthGeneration/LCG startup customization before adding our isolated hook;
# otherwise LCG paths (including six) can disappear from the interpreter.
_here = os.path.realpath(__file__)
for _directory in tuple(sys.path):
    if not _directory:
        continue
    _original = PathFinder.find_spec('sitecustomize', [_directory])
    if (_original is None or _original.origin is None or
            os.path.realpath(_original.origin) == _here):
        continue
    _original_module = importlib.util.module_from_spec(_original)
    _original.loader.exec_module(_original_module)
    break

_candidate = os.environ.get("AQP_CLUSTER_CANDIDATE")
_expected_sha = "ab60358a273531522835cd64c0f76acaca91faed1d426374ae8c04796ca4ef3c"

if _candidate:
    _candidate = os.path.realpath(_candidate)
    if not os.path.isfile(_candidate):
        raise RuntimeError("Missing AQP cluster candidate: " + _candidate)
    with open(_candidate, "rb") as _handle:
        if hashlib.sha256(_handle.read()).hexdigest() != _expected_sha:
            raise RuntimeError("Unexpected AQP cluster candidate SHA256")

    class _AQPClusterLoader(SourceFileLoader):
        def get_code(self, fullname):
            with open(_candidate, "rb") as handle:
                source = handle.read()
            # Preserve the original location and __file__ for MadGraph.
            return compile(source, self.path, "exec")

    class _AQPClusterFinder:
        def find_spec(self, fullname, path=None, target=None):
            if fullname not in ("madgraph.various.cluster", "internal.cluster"):
                return None
            spec = PathFinder.find_spec(fullname, path, target)
            if spec is None or not spec.origin:
                raise ImportError("Cannot locate MadGraph cluster module: " + fullname)
            # Source pin is essential: the candidate was generated from
            # atlas13-dbd05, not an arbitrary MadGraph 3.5.11 build.
            with open(spec.origin, 'rb') as _fh:
                actual_sha = hashlib.sha256(_fh.read()).hexdigest()
            if actual_sha != 'feb07ff8af81eb5524ee810d6f4976502457fdf45106a9e2702d1ea46b7ef7fe':
                raise ImportError('AQP Condor source mismatch for %s: SHA256=%s' %
                                  (spec.origin, actual_sha))
            spec.loader = _AQPClusterLoader(fullname, spec.origin)
            return spec

    sys.meta_path.insert(0, _AQPClusterFinder())
