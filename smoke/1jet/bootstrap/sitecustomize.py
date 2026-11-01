"""Load one source-pinned AQP Condor candidate for the disposable smoke test.

Works with both madgraph.various.cluster and generated internal.cluster.
Does not change CVMFS or an existing MadGraph process.
"""
import hashlib
import os
import sys
from importlib.machinery import PathFinder, SourceFileLoader

_candidate = os.environ.get("AQP_CLUSTER_CANDIDATE")
_expected_sha = "2286e475b32323f1e391fb8e64af06fa8e41531abccd4d2c701b7746a22cc5bd"

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
            spec.loader = _AQPClusterLoader(fullname, spec.origin)
            sys.stderr.write("AQP_CONDOR_PATCH_LOADED %s (original=%s)\n" %
                             (fullname, spec.origin))
            return spec

    sys.meta_path.insert(0, _AQPClusterFinder())
