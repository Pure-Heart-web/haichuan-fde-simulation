from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ReviewTask:
    task_id: str
    case_id: str
    trace_id: str
    type: str
    risk_level: str
    assignee_role: str
    assignee_id: str
    payload: dict
    evidence: dict
    prerequisite_task_id: str | None = None
    status: str = 'pending'
    tenant_id: str = 'haichuan-training'
    domain: str = 'foreign_trade'

    def to_dict(self):
        return asdict(self)
