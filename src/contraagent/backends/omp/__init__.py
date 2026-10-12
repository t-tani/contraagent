"""oh-my-pi (`omp -p`): one-shot text/trace mode and the RPC variant."""

from contraagent.backends.omp.backend import OMP_PREAMBLE, OmpBackend
from contraagent.backends.omp.rpc import OmpRpcBackend

__all__ = ["OMP_PREAMBLE", "OmpBackend", "OmpRpcBackend"]
