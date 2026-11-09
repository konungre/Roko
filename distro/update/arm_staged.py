"""Connect authenticated staging to the userspace trial journal, without booting."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from stage_release import inspect
from boot_trial import Journal


def arm(directory, staged_directory, public_key, expected_revision):
    journal = Journal(directory)
    try:
        current = journal.read()
        if type(expected_revision) is not int or current['revision'] != expected_revision:
            raise ValueError('Stale journal revision')
        if current['trial'] is not None:
            raise ValueError('Trial already pending')
        # The current confirmed sequence supplies the floor, never the candidate.
        receipt = inspect(staged_directory, public_key, current['good']['sequence'] + 1)
        if receipt.get('state') != 'authenticated-staging':
            raise ValueError('Candidate staging is incomplete')
        candidate = {'slot': 'B' if current['good']['slot'] == 'A' else 'A',
                     'sequence': receipt['sequence'], 'sha256': receipt['sha256']}
        result = journal.transition('arm', expected_revision, candidate=candidate)
        result['signature_verified'] = receipt['signature_verified']
        result['key_sha256'] = receipt['key_sha256']
        result['slot_written'] = False
        return result
    finally:
        journal.close()
