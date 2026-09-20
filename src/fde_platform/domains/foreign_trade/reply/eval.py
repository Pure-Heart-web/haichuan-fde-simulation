"""Transparent synthetic Stage 6 evaluations; real human acceptance is N/A until reviews exist."""
import json
from pathlib import Path

from fde_platform.core.context.resolution import resolve_identity
from fde_platform.core.policy.claims import ClaimPolicyError, load_claim_policy, validate_claims

from .workflow import run_case


def _jsonl(path):
    rows = [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]
    ids = [x['id'] for x in rows]
    if len(ids) != len(set(ids)):
        raise ValueError(f'{path}: 重复 ID')
    return rows


def evaluate_context(path, provider):
    rows = []
    for case in _jsonl(path):
        identity = resolve_identity(provider.entities, case.get('sender', ''), case.get('company_name', ''))
        order = provider.previous_order(identity.customer_id) if identity.status == 'resolved' and case.get('reference') else None
        actual_order = order.source_id if order else None
        rows.append({'id': case['id'], 'identity_status_expected': case['expected_status'],
                     'identity_status_actual': identity.status, 'customer_expected': case.get('expected_customer_id'),
                     'customer_actual': identity.customer_id, 'previous_order_expected': case.get('expected_order_id'),
                     'previous_order_actual': actual_order})
    refs = [x for x in rows if x['previous_order_expected'] is not None]
    wrong_context = [x for x in rows if x['previous_order_actual'] is not None and
                     x['previous_order_actual'] != x['previous_order_expected']]
    return {'case_count': len(rows), 'previous_order_labeled_cases': len(refs),
            'customer_resolution_accuracy': sum(x['identity_status_expected'] == x['identity_status_actual'] and
                x['customer_expected'] == x['customer_actual'] for x in rows) / len(rows) if rows else None,
            'previous_order_resolution_accuracy': sum(x['previous_order_actual'] == x['previous_order_expected']
                for x in refs) / len(refs) if refs else None,
            'wrong_customer_context_rate': len(wrong_context) / len(rows) if rows else None,
            'rows': rows}


def evaluate_knowledge(path, index):
    rows = []
    for case in _jsonl(path):
        found = index.retrieve(case['query'], intent=case['intent'], sku=case.get('sku'),
                               region=case.get('region', 'global'), as_of=case.get('as_of', '2026-09-20'))
        actual = [x.document_id for x in found]
        expected = case.get('expected_document_id')
        rows.append({'id': case['id'], 'expected_document_id': expected, 'retrieved': actual,
                     'source_at_1_correct': actual[0] == expected if expected else None,
                     'recall_at_5': expected in actual[:5] if expected else None,
                     'gap_expected': expected is None, 'gap_actual': not actual})
    labeled = [x for x in rows if x['expected_document_id']]
    doc_status = {x['document_id']: x['status'] for x in index.documents}
    retrieved_count = sum(len(x['retrieved']) for x in rows)
    outdated = sum(doc_status[doc_id] != 'active' for x in rows for doc_id in x['retrieved'])
    return {'case_count': len(rows), 'source_labeled_cases': len(labeled),
            'correct_source_at_1': sum(x['source_at_1_correct'] for x in labeled) / len(labeled) if labeled else None,
            'recall_at_5': sum(x['recall_at_5'] for x in labeled) / len(labeled) if labeled else None,
            'outdated_document_retrieval_rate': outdated / retrieved_count if retrieved_count else None,
            'knowledge_gap_rate': sum(x['gap_actual'] for x in rows) / len(rows) if rows else None,
            'gap_detection_accuracy': sum(x['gap_expected'] == x['gap_actual'] for x in rows) / len(rows) if rows else None,
            'rows': rows}


def evaluate_generation(scenarios_path, labels_path, *, root, provider, index, products, review_store=None):
    labels = {x['id']: x for x in _jsonl(labels_path)}
    policy = load_claim_policy(root)
    rows = []
    total_claims = unsupported = fact_checks = facts_correct = required_claims = covered = 0
    for case in _jsonl(scenarios_path):
        artifact = run_case(case, root=root, context_provider=provider, knowledge_index=index,
                            product_components=products)
        draft = artifact['draft']
        label = labels[case['id']]
        refs = {artifact['work_item']['id']}
        if artifact['previous_order']:
            refs.add(artifact['previous_order']['source_id'])
        refs.update(x['document_id'] + ':' + x['chunk_id'] for xs in artifact['knowledge_evidence'].values() for x in xs)
        claims = []
        from fde_platform.core.generation.draft import GeneratedClaim
        for raw in draft['claims']:
            claim = GeneratedClaim(raw['claim_type'], raw['text'], tuple(raw['source_refs']), raw.get('approval_ref'))
            claims.append(claim)
            total_claims += 1
            try:
                validate_claims([claim], refs, policy)
            except ClaimPolicyError:
                unsupported += 1
            if policy['claim_types'][claim.claim_type].get('evidence_required'):
                required_claims += 1
                covered += int(bool(claim.source_refs) and set(claim.source_refs) <= refs)
        phrase_ok = all(phrase.casefold() in draft['body'].casefold() for phrase in label.get('expected_phrases', []))
        absent_ok = all(phrase.casefold() not in draft['body'].casefold() for phrase in label.get('forbidden_phrases', []))
        fact_checks += 1
        facts_correct += int(phrase_ok and absent_ok)
        rows.append({'id': case['id'], 'expected_claim_types': label['expected_claim_types'],
                     'actual_claim_types': sorted(set(x.claim_type for x in claims if x.claim_type != 'acknowledgement')),
                     'expected_gaps': label['expected_gaps'],
                     'actual_gaps': sorted(x['intent'] for x in draft['knowledge_gaps']),
                     'fact_label_pass': phrase_ok and absent_ok,
                     'identity_status': artifact['identity']['status'], 'draft_status': draft['status']})
    events = review_store.reviews() if review_store else []
    assessed = [x for x in events if x['action'] in ('approve', 'minor_edit', 'major_edit', 'reject')]
    return {'case_count': len(rows), 'claim_count': total_claims,
            'unsupported_claim_rate': unsupported / total_claims if total_claims else None,
            'evidence_coverage': covered / required_claims if required_claims else None,
            'fact_accuracy_on_labeled_cases': facts_correct / fact_checks if fact_checks else None,
            'claim_type_match_rate': sum(x['expected_claim_types'] == x['actual_claim_types'] for x in rows) / len(rows) if rows else None,
            'gap_match_rate': sum(x['expected_gaps'] == x['actual_gaps'] for x in rows) / len(rows) if rows else None,
            'human_review_events': len(assessed),
            'draft_acceptance_rate': sum(x['action'] in ('approve', 'minor_edit') for x in assessed) / len(assessed) if assessed else None,
            'human_edit_rate': sum(x['action'] in ('minor_edit', 'major_edit') for x in assessed) / len(assessed) if assessed else None,
            'rows': rows}


def render_report(report):
    def fmt(value):
        return 'N/A' if value is None else f'{value:.1%}'
    context, knowledge, generation = (report[key] for key in ('context', 'knowledge', 'generation'))
    failed = [x['id'] for x in generation['rows'] if not x['fact_label_pass'] or
              x['expected_claim_types'] != x['actual_claim_types'] or x['expected_gaps'] != x['actual_gaps']]
    return ('# Stage 6 合成评估\n\n全部数据为教学构造；没有真实客户、政策或销售 Pilot。人工接受率无审核事件时为 N/A。\n\n'
            f'## Customer Context（{context["case_count"]} 条）\n\n'
            f'- Customer Resolution Accuracy：{fmt(context["customer_resolution_accuracy"])}\n'
            f'- Previous Order Resolution Accuracy：{fmt(context["previous_order_resolution_accuracy"])}\n'
            f'- Wrong Customer Context Rate：{fmt(context["wrong_customer_context_rate"])}\n\n'
            f'## Knowledge（{knowledge["case_count"]} 条）\n\n'
            f'- Correct Source@1：{fmt(knowledge["correct_source_at_1"])}\n'
            f'- Recall@5：{fmt(knowledge["recall_at_5"])}\n'
            f'- Outdated Document Retrieval Rate：{fmt(knowledge["outdated_document_retrieval_rate"])}\n'
            f'- Knowledge Gap Rate：{fmt(knowledge["knowledge_gap_rate"])}\n'
            f'- Gap Detection Accuracy：{fmt(knowledge["gap_detection_accuracy"])}\n\n'
            f'## Reply（{generation["case_count"]} 条，{generation["claim_count"]} 个 Claim）\n\n'
            f'- Unsupported Claim Rate：{fmt(generation["unsupported_claim_rate"])}\n'
            f'- Evidence Coverage：{fmt(generation["evidence_coverage"])}\n'
            f'- Labeled Fact Accuracy：{fmt(generation["fact_accuracy_on_labeled_cases"])}\n'
            f'- Claim Type Match：{fmt(generation["claim_type_match_rate"])}\n'
            f'- Knowledge Gap Match：{fmt(generation["gap_match_rate"])}\n'
            f'- Draft Accept/Minor Edit：{fmt(generation["draft_acceptance_rate"])}（审核事件 {generation["human_review_events"]}）\n'
            f'- Human Edit Rate：{fmt(generation["human_edit_rate"])}\n\n'
            f'需复盘的场景：{", ".join(failed) or "无"}。完整逐案证据见 `stage6-eval.json`。\n')
