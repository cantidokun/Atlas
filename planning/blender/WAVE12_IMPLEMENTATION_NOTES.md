# Wave 12 Implementation Checkpoint

Implementation remains blocked at the design boundary until the contract is reviewed against the existing hierarchy validator and Wave 4 executor boundary.

Required implementation invariants:

- one selected target edge only;
- exact expected parent binding;
- fresh source digest binding;
- no inferred replacement parent;
- no cascade or multi-edge mutation;
- post-state proves acyclic hierarchy and preservation of all unrelated state;
- no persistence, receipt, recovery, workflow, or action-runner authority.
