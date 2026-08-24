material_evidence = [ev for ev in result.replacement_result.evidence_ledger if "material" in ev.operation_name]
assert len(material_evidence) == 2
assert material_evidence[0].operation_name == "apply_material_variant"
assert material_evidence[1].operation_name == "verify_material_variant"
assert material_evidence[1].verified is True
