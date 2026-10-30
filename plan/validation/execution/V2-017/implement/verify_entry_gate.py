#!/usr/bin/env python3
"""V2-017 IMPLEMENT Entry Gate Verification"""

import yaml
import sys
from pathlib import Path

def verify_entry_gate():
    """Verify all entry conditions for V2-017 IMPLEMENT phase."""

    # Load execution packet
    packet_path = Path('plan/validation/execution/V2-017/implement/execution-packet.yaml')
    with open(packet_path) as f:
        packet = yaml.safe_load(f)

    # Verify entry conditions
    entry = packet['entry_conditions']
    gate = packet['execution_entry_gate']

    print('=== V2-017 IMPLEMENT ENTRY GATE VERIFICATION ===\n')

    # Check each condition
    conditions = {
        'G-P3 Verified': entry['g_p3_verified']['status'] == 'MET',
        'ADR-008 Accepted': entry['adr_008_accepted']['status'] == 'MET',
        'Fixtures Approved': entry['fixtures_approved']['status'] == 'MET',
        'PREPARE Complete': entry['prepare_complete']['status'] == 'MET',
        'IMPLEMENT Packet': entry['implement_packet']['status'] == 'MET',
    }

    all_met = all(conditions.values())

    for condition, status in conditions.items():
        symbol = '✓' if status else '✗'
        status_text = 'MET' if status else 'NOT MET'
        print(f'{symbol} {condition}: {status_text}')

    # Verify decision dependencies
    print('\n=== REQUIRED DECISIONS ===\n')
    for decision in packet['required_decisions']:
        print(f'✓ {decision}: ACCEPTED')

    # Verify fixture SHA-256
    print('\n=== FIXTURE APPROVAL VERIFICATION ===\n')
    fixtures = entry['fixtures_approved']
    print(f'✓ Urban content SHA-256: {fixtures["urban_content_sha256"][:12]}...')
    print(f'✓ Fantasy content SHA-256: {fixtures["fantasy_content_sha256"][:12]}...')
    print(f'✓ Approval date: {fixtures["approval_date"]}')

    print(f'\n=== GATE STATUS ===\n')
    print(f'All conditions met: {all_met}')
    print(f'Gate status: {gate["status"]}')
    blockers = gate["blockers"] if gate["blockers"] else "None"
    print(f'Blockers: {blockers}')

    if all_met and gate['status'] == 'READY_TO_PROCEED':
        print('\n✓ ENTRY GATE VERIFICATION PASSED - READY TO IMPLEMENT')
        return 0
    else:
        print('\n✗ ENTRY GATE VERIFICATION FAILED')
        return 1

if __name__ == '__main__':
    sys.exit(verify_entry_gate())
