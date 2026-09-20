"""Validate structured claims before any reply text is assembled."""
import json
from pathlib import Path


class ClaimPolicyError(ValueError):
    pass


def load_claim_policy(root):
    path = Path(root) / 'tenants/haichuan/claim-policy.json'
    policy = json.loads(path.read_text(encoding='utf-8'))
    if policy['status'] != 'training_only' or not isinstance(policy.get('claim_types'), dict):
        raise ClaimPolicyError('Claim Policy 模式无效')
    return policy


def validate_claims(claims, evidence_refs, policy, approved_refs=()):
    for claim in claims:
        rule = policy['claim_types'].get(claim.claim_type)
        if rule is None or not rule.get('allowed'):
            raise ClaimPolicyError(f'禁止的 Claim：{claim.claim_type}')
        if rule.get('evidence_required') and not claim.source_refs:
            raise ClaimPolicyError(f'{claim.claim_type} 缺少证据')
        if not set(claim.source_refs) <= set(evidence_refs):
            raise ClaimPolicyError(f'{claim.claim_type} 引用了不存在的证据')
        if rule.get('approval_required') and claim.approval_ref not in approved_refs:
            raise ClaimPolicyError(f'{claim.claim_type} 缺少审批')
        qualifier = rule.get('required_qualifier')
        if qualifier and qualifier.casefold() not in claim.text.casefold():
            raise ClaimPolicyError(f'{claim.claim_type} 缺少限定语')
    return True
