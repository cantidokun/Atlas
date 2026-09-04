# Stage 17 Unreal Production Artifact Provenance

Atlas treats Unreal production artifacts as provenance records, not execution authority.

The Unreal lineage gate requires:

1. a verified `inspect_render_job` evidence record;
2. semantic render completion (`status` completed/finished, `success=True`, `failed=False`);
3. an evidence-bound immutable `UnrealRenderReceipt`;
4. the manifest artifact path to be present in the independently observed `output_files` evidence;
5. the manifest engine identity to remain `Unreal`;
6. exact receipt and evidence digests during independent lineage verification.

The manifest and its store do not execute Unreal work, authorize renders, retry failed work, or recover render jobs.

Cross-process Unreal render-job recovery remains a separate capability and is not implied by receipt or artifact persistence.
