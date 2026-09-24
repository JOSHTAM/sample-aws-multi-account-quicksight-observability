"""Executive Alerts Dashboard - Display Logic Helper Functions"""
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone


def alarm_state_color(state: str) -> str:
    """Map alarm state to display color. Property 14."""
    mapping = {
        'ALARM': 'red',
        'INSUFFICIENT_DATA': 'yellow',
        'OK': 'green'
    }
    return mapping.get(state, 'green')


def account_highlight_active(alarm_records: List[Dict], account_id: int) -> bool:
    """Returns True if account has more than 5 active ALARM-state alarms. Property 15."""
    alarm_count = sum(
        1 for a in alarm_records
        if a.get('account_id') == account_id and a.get('state') == 'ALARM'
    )
    return alarm_count > 5


def critical_detail_panel(records: List[Dict], limit: int = 100) -> List[Dict]:
    """Filter to Critical/High, sort by timestamp desc, limit to 100. Property 16."""
    filtered = [
        r for r in records
        if r.get('severity') in ['Critical', 'High', 'P1', 'P2']
    ]
    sorted_records = sorted(
        filtered,
        key=lambda x: x.get('timestamp') or x.get('state_updated_at') or x.get('start_time') or '',
        reverse=True
    )
    return sorted_records[:limit]


def apply_filters(
    records: List[Dict],
    account: Optional[str] = None,
    severity: Optional[str] = None,
    time_range_start: Optional[datetime] = None,
    source_type: Optional[str] = None,
    product: Optional[str] = None
) -> List[Dict]:
    """Apply all active filters simultaneously. Property 17."""
    result = records
    
    if account:
        result = [r for r in result if r.get('account_name') == account or r.get('aws_account_id') == account]
    
    if severity:
        result = [r for r in result if r.get('severity') == severity]
    
    if time_range_start:
        result = [
            r for r in result
            if _get_timestamp(r) and _get_timestamp(r) >= time_range_start
        ]
    
    if source_type:
        result = [r for r in result if r.get('source_type') == source_type]
    
    if product:
        result = [r for r in result if r.get('product_name') == product]
    
    return result


def executive_summary_counts(
    alarms: List[Dict],
    incidents: List[Dict],
    canaries: List[Dict],
    error_summaries: List[Dict]
) -> Dict[str, Any]:
    """Calculate summary panel totals. Property 18."""
    return {
        'critical_alarms': sum(1 for a in alarms if a.get('state') == 'ALARM' and a.get('severity') == 'Critical'),
        'high_alarms': sum(1 for a in alarms if a.get('state') == 'ALARM' and a.get('severity') == 'High'),
        'medium_alarms': sum(1 for a in alarms if a.get('state') == 'ALARM' and a.get('severity') == 'Medium'),
        'low_alarms': sum(1 for a in alarms if a.get('state') == 'ALARM' and a.get('severity') == 'Low'),
        'active_incidents_p1': sum(1 for i in incidents if i.get('status') == 'OPEN' and i.get('severity') == 'P1'),
        'active_incidents_p2': sum(1 for i in incidents if i.get('status') == 'OPEN' and i.get('severity') == 'P2'),
        'active_incidents_p3': sum(1 for i in incidents if i.get('status') == 'OPEN' and i.get('severity') == 'P3'),
        'active_incidents_p4': sum(1 for i in incidents if i.get('status') == 'OPEN' and i.get('severity') == 'P4'),
        'canary_failures': sum(1 for c in canaries if c.get('status') in ['ERROR', 'NOT_RUNNING']),
        'total_errors': sum(e.get('occurrence_count', 0) for e in error_summaries),
    }


def _get_timestamp(record: Dict) -> Optional[datetime]:
    """Extract timestamp from a record regardless of field name."""
    for field in ['timestamp', 'state_updated_at', 'start_time', 'last_occurrence', 'collection_timestamp']:
        val = record.get(field)
        if val:
            if isinstance(val, datetime):
                return val
            try:
                return datetime.fromisoformat(val.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                continue
    return None
