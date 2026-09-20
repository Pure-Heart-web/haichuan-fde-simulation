"""Metadata-first lexical retrieval over a small, governed offline corpus."""
import json
import re
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True)
class KnowledgeEvidence:
    document_id: str
    chunk_id: str
    title: str
    text: str
    fact_value: str
    intent: str
    version: str
    effective_date: str
    owner: str
    source_type: str
    relevance_score: float

    def to_dict(self):
        return asdict(self)


INTENT_PATTERNS = {
    'warranty': r'\bwarrant(?:y|ies)\b|保修|质保',
    'ce': r'\bCE\b|欧盟认证',
    'atex': r'\bATEX\b|防爆认证',
    'lead_time': r'\blead\s*time\b|\bdelivery\s*time\b|交期|交货期',
    'outdoor': r'\boutdoors?\b|户外',
}


def infer_intents(query):
    return tuple(key for key, pattern in INTENT_PATTERNS.items() if re.search(pattern, query, re.I))


class KnowledgeIndex:
    def __init__(self, root):
        path = Path(root) / 'stages/06-context-knowledge-reply/data/knowledge-documents.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        if data['status'] != 'training_approved_only':
            raise ValueError('知识包必须明确为教学模拟')
        self.dataset_id = data['dataset_id']
        self.documents = data['documents']
        doc_ids, chunk_ids = set(), set()
        for doc in self.documents:
            if doc['document_id'] in doc_ids or doc['status'] not in ('draft', 'active', 'superseded', 'archived'):
                raise ValueError('知识文档 ID 重复或状态无效')
            doc_ids.add(doc['document_id'])
            date.fromisoformat(doc['effective_date'])
            for key in ('title', 'version', 'owner', 'document_type', 'product_family', 'region', 'language'):
                if not doc.get(key):
                    raise ValueError(f'知识文档缺少 {key}')
            for chunk in doc['chunks']:
                if chunk['chunk_id'] in chunk_ids or chunk['intent'] not in INTENT_PATTERNS:
                    raise ValueError('知识 chunk ID 重复或意图无效')
                chunk_ids.add(chunk['chunk_id'])
                if not chunk.get('text') or not chunk.get('fact_value'):
                    raise ValueError('知识 chunk 缺少文本或结构化事实')

    def retrieve(self, query, *, intent, product_family='centrifugal_pump', region='global', sku=None,
                 as_of='2026-09-20', limit=5):
        if intent not in INTENT_PATTERNS:
            raise ValueError('未知知识意图')
        today = date.fromisoformat(as_of)
        terms = set(re.findall(r'[a-z0-9]+', query.casefold()))
        found = []
        for doc in self.documents:
            # Governance filters run before relevance ranking.
            if (doc['status'] != 'active' or date.fromisoformat(doc['effective_date']) > today or
                doc['product_family'] != product_family or doc['region'] not in ('global', region) or
                (doc.get('applicable_skus') and sku not in doc['applicable_skus'])):
                continue
            for chunk in doc['chunks']:
                if chunk['intent'] != intent:
                    continue
                words = set(re.findall(r'[a-z0-9]+', (doc['title'] + ' ' + chunk['text']).casefold()))
                score = 1.0 + len(terms & words) / max(1, len(terms))
                found.append(KnowledgeEvidence(doc['document_id'], chunk['chunk_id'], doc['title'],
                                               chunk['text'], chunk['fact_value'], intent, doc['version'],
                                               doc['effective_date'], doc['owner'], 'enterprise_knowledge_simulated',
                                               round(score, 4)))
        return tuple(sorted(found, key=lambda e: (-e.relevance_score, e.document_id, e.chunk_id))[:limit])
