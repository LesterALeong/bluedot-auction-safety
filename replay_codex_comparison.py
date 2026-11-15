"""Recompute the Codex follow-up from the publication's normalized judgments."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

from codex_comparison_design import MODELS, output_schema, schedule, summarize
from study import decode, encode


def verify_and_score(path):
    evidence = decode(path.read_bytes())
    frozen = evidence['manifest']
    cases = schedule()
    if frozen['models'] != list(MODELS) or frozen['effort'] != 'low':
        raise ValueError('model or effort mismatch')
    if sha256(encode(cases)).hexdigest() != frozen['schedule_sha256']:
        raise ValueError('frozen schedule mismatch')
    requests = {case['id']: sha256(encode({
        'model': case['model'], 'effort': frozen['effort'],
        'input': case['prompt'], 'schema': output_schema(case['variant']),
    })).hexdigest() for case in cases}
    records = evidence['judgments']
    if requests != frozen['requests'] or not records.keys() <= requests.keys():
        raise ValueError('unknown or drifted request')
    for case_id, row in records.items():
        if row['request_sha256'] != requests[case_id]:
            raise ValueError(f'request mismatch for {case_id}')
        if row['status'] == 'valid':
            if row['answer'] is None or sha256(encode(row['answer'])).hexdigest() != row['answer_sha256']:
                raise ValueError(f'answer mismatch for {case_id}')
        elif row['answer'] is not None or row['answer_sha256'] is not None:
            raise ValueError(f'unexpected answer for {case_id}')
    return summarize(cases, records)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file', type=Path)
    args = parser.parse_args()
    print(json.dumps(verify_and_score(args.file), indent=2))


if __name__ == '__main__':
    main()
