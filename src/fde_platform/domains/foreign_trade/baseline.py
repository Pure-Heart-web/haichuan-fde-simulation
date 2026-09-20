"""Interchangeable offline extractor for the training fixture, with raw units."""
import json
import re

from ...core.models import WorkItem

NUMBER = r'(-?\d+(?:\.\d+)?)'


def match_field(body, patterns, *, group=1, unit_group=None):
    for pattern in patterns:
        found = re.search(pattern, body, flags=re.IGNORECASE)
        if found:
            return {'value': found.group(group), 'unit': found.group(unit_group) if unit_group else None,
                    'text': found.group(0), 'start': found.start(), 'end': found.end()}
    return None


class RegexBaselineProvider:
    """Local baseline. It is not an LLM and has no external model calls."""

    model_version = 'regex-baseline-v1'

    def complete(self, work_item: WorkItem, prompt_version: str) -> str:
        body = work_item.body
        # A signature should not be mistaken for operating conditions.
        body = re.split(r'\n(?:--\s*$|best regards[,\s]*$|regards[,\s]*$|sent from my)', body,
                        maxsplit=1, flags=re.IGNORECASE | re.MULTILINE)[0]
        result = {
            'flow': match_field(body, [rf'(?:flow|capacity|流量)\s*[:=]?\s*{NUMBER}\s*(m3/h|m³/h|cmh|l/min)\b',
                                       rf'{NUMBER}\s*(m3/h|m³/h|cmh|l/min)\b'], unit_group=2),
            'head': match_field(body, [rf'(?:head|扬程)\s*[:=]?\s*{NUMBER}\s*(m(?:eters?)?)?\b',
                                        rf'{NUMBER}\s*m\s+head\b']),
            'temperature': match_field(body, [rf'{NUMBER}\s*(°?c|°?f)\b'], unit_group=2),
            'quantity': match_field(body, [rf'{NUMBER}\s*(pcs|pieces|sets|units)\b',
                                            rf'(?:qty|quantity)\s*[:=]?\s*{NUMBER}',
                                            rf'(?:数量)\s*[:=]?\s*{NUMBER}\s*台']),
            'voltage': match_field(body, [rf'{NUMBER}\s*v\b']),
            'frequency': match_field(body, [rf'{NUMBER}\s*hz\b']),
            'product_type': match_field(body, [r'centrifugal\s+pump', r'离心泵', r'wastewater\s+pump', r'seawater\s+pump', r'\bpump\b'], group=0),
            'medium': match_field(body, [r'\bseawater\b', r'\bfreshwater\b', r'\bcooling\s+water\b',
                                         r'\bhot\s+water\b', r'\bwastewater\b', r'\bchemical\b', r'\bwater\b',
                                         r'海水', r'淡水', r'冷却水', r'污水', r'化工液体'], group=0),
            'destination_port': match_field(body, [r'\bCIF\s+([A-Za-z][A-Za-z ]{2,40})',
                                                   r'目的港\s*[:：]?\s*([A-Za-z][A-Za-z ]{2,40})'], group=1),
            'application': match_field(body, [r'\bcooling\s+water\b', r'\bchemical\s+process\b', r'\bdesalination\b'], group=0),
        }
        return json.dumps(result, ensure_ascii=False)
