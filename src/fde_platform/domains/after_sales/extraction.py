"""Offline domain provider using the unchanged shared ExtractionRuntime."""
import json
import re

from fde_platform.core.extraction import extract
from fde_platform.core.models import ExtractionConfig
from .schema import ServiceCase


class ServiceRegexProvider:
    def complete(self, work_item, prompt_version):
        text = work_item.body
        model = re.search(r'\bQH-\d+\b', text, re.I)
        serial = re.search(r'\bQH\d{7,}\b', text, re.I)
        code = re.search(r'\bE\d{2,3}\b', text, re.I)
        pressure = re.search(r'\bpressure\s*(?:is|:)?\s*(\d+(?:\.\d+)?)\s*bar\b', text, re.I)
        normal = re.search(r'\bnormal\s*(\d+(?:\.\d+)?)\s*bar\b', text, re.I)
        temp = re.search(r'\btemperature\s*(?:is|:)?\s*(\d+(?:\.\d+)?)\s*°?C\b', text, re.I)
        noise = bool(re.search(r'\babnormal\s+noise\b|异响', text, re.I))
        electrical = bool(re.search(r'\belectrical\s+cabinet\b|电柜', text, re.I))
        vessel = bool(re.search(r'\bpressure\s+vessel\b|储气罐', text, re.I))
        maintenance = bool(re.search(r'\bmaintenance\s+yesterday\b|\brecently\s+serviced\b|昨天.*保养', text, re.I))
        symptoms = tuple(x for x, present in (
            ('abnormal_noise', noise), ('electrical_cabinet', electrical), ('pressure_vessel', vessel),
            ('low_pressure', bool(pressure and normal and float(pressure.group(1)) < float(normal.group(1))))
        ) if present)
        return json.dumps({
            'device_model': model.group(0).upper() if model else None,
            'serial_number': serial.group(0).upper() if serial else None,
            'error_code': code.group(0).upper() if code else None,
            'current_pressure_bar': float(pressure.group(1)) if pressure else None,
            'normal_pressure_bar': float(normal.group(1)) if normal else None,
            'temperature_c': float(temp.group(1)) if temp else None,
            'abnormal_noise': noise, 'electrical_cabinet': electrical,
            'pressure_vessel': vessel, 'recent_maintenance_reported': maintenance,
            'symptoms': symptoms,
        }, ensure_ascii=False)


def extract_service_case(work_item):
    if work_item.domain != 'after_sales':
        raise ValueError('售后抽取只接受 after_sales WorkItem')
    result = extract(work_item, ServiceRegexProvider(), ExtractionConfig(
        prompt_version='qihang-service-regex-v1', model_version='offline-regex-no-llm', max_parse_retries=0))
    if result.status != 'extracted':
        raise ValueError('售后抽取失败：' + str(result.error))
    return result, ServiceCase.from_fields(work_item.id, result.raw_fields)
