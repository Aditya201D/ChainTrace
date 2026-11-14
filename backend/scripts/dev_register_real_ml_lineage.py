"""Local Hardhat-only ChainTrace real ML lineage and test-audit integration.
Run from backend/: python -m scripts.dev_register_real_ml_lineage
"""
import hashlib
import json
from pathlib import Path
from urllib.parse import quote, urlparse

import requests
from web3 import Web3

from app.config import RPC_URL, CONTRACT_ADDRESS

BASE = 'http://127.0.0.1:8000'
DATASET = 'dataset:2662054ac5c641f6bce991b5100be574'
TRAINING = 'trainingrun:141e3503286941529357396081f62c22'
MODEL = 'model:8be33ca166d2474ca1e45e3ff1094414'
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'ml_demo' / 'outputs'


def api(method, path, **kwargs):
    response = requests.request(method, BASE + path, timeout=20, **kwargs)
    if not response.ok:
        raise RuntimeError(f'{method} {path}: HTTP {response.status_code}: {response.text}')
    return response.json()


def ident(x):
    return quote(x, safe='')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def send_prepared(w3, prepared, sender):
    if Web3.to_checksum_address(prepared['from']) != sender:
        raise RuntimeError('Prepared transaction has unexpected sender')
    if Web3.to_checksum_address(prepared['to']) != Web3.to_checksum_address(CONTRACT_ADDRESS):
        raise RuntimeError('Prepared transaction targets wrong contract')
    if int(prepared['chain_id']) != w3.eth.chain_id:
        raise RuntimeError('Prepared transaction chain ID mismatch')
    raw_value = prepared['value']
    value = int(raw_value, 16) if isinstance(raw_value, str) else int(raw_value)
    tx = w3.eth.send_transaction({
        'from': sender, 'to': prepared['to'], 'data': prepared['data'],
        'value': value, 'chainId': w3.eth.chain_id,
    })
    tx_hex = Web3.to_hex(tx)
    print('  Submitted:', tx_hex, '(save if confirmation fails)')
    receipt = w3.eth.wait_for_transaction_receipt(tx, timeout=45)
    if receipt['status'] != 1:
        raise RuntimeError(f'Transaction reverted: {tx_hex}')
    return tx_hex


def check_artifacts_and_manifest():
    paths = {
        DATASET: OUT / 'phishing_dataset.csv',
        TRAINING: OUT / 'training_run_manifest.json',
        MODEL: OUT / 'phishing_model.joblib',
    }
    for aid, path in paths.items():
        if not path.is_file():
            raise RuntimeError(f'Missing file: {path}')
        metadata = api('GET', f'/api/v1/artifacts/{ident(aid)}')
        verified = api('GET', f'/api/v1/artifacts/{ident(aid)}/verify')
        if not verified['verification']['overall_verified']:
            raise RuntimeError(f'Artifact failed verification: {aid}: {verified}')
        if digest(path) != metadata['sha256_hex'].lower():
            raise RuntimeError(f'Original output file changed since upload: {path}')
        print('  Verified:', aid)

    manifest = json.loads(paths[TRAINING].read_text(encoding='utf-8'))
    if manifest.get('execution_status') != 'completed':
        raise RuntimeError('Training manifest does not show completed training')
    if manifest.get('dataset_sha256', '').lower() != digest(paths[DATASET]):
        raise RuntimeError('Manifest dataset hash differs from dataset file')
    if manifest.get('model_sha256', '').lower() != digest(paths[MODEL]):
        raise RuntimeError('Manifest model hash differs from model file')
    if not manifest.get('mlflow_run_id'):
        raise RuntimeError('Manifest missing MLflow run ID')
    print('  Manifest hashes match dataset and trained model')
    return manifest


def ensure_link(w3, source, target, relationship, developer):
    path = f'/api/v1/blockchain/provenance/{ident(source)}/{ident(target)}'
    # Existing general read endpoint covers Dataset -> TrainingRun only.
    # The dedicated Model read route covers TrainingRun -> Model.
    if relationship == 'Produced':
        path = f'/api/v1/blockchain/provenance/model/{ident(source)}/{ident(target)}'
    response = requests.get(BASE + path, timeout=15)
    if response.status_code == 200:
        current = response.json()
        expected = 0 if relationship == 'UsedForTraining' else 1
        if current.get('exists') and current.get('relationship_type') == expected:
            print('  Already linked:', relationship)
            return
    elif response.status_code not in (404, 409):
        raise RuntimeError(f'Cannot read existing {relationship} link: {response.status_code}: {response.text}')

    if relationship == 'UsedForTraining':
        prefix = '/api/v1/blockchain/provenance'
        prep_path, confirm_path = prefix + '/prepare-training-link', prefix + '/confirm-training-link'
        payload = {'source_artifact_id': source, 'target_artifact_id': target}
        request = {**payload, 'registrar_address': developer}
    else:
        prefix = '/api/v1/blockchain/provenance'
        prep_path, confirm_path = prefix + '/prepare-model-link', prefix + '/confirm-model-link'
        payload = {'training_run_id': source, 'model_artifact_id': target}
        request = {**payload, 'registrar_address': developer}
    prepared = api('POST', prep_path, json=request)['transaction']
    tx = send_prepared(w3, prepared, developer)
    confirmation = api('POST', confirm_path, json={**payload, 'tx_hash': tx})
    if confirmation.get('relationship') != relationship:
        raise RuntimeError(f'Unexpected {relationship} confirmation: {confirmation}')
    final = api('GET', path)
    if not final.get('exists') or final.get('relationship_type') != (0 if relationship == 'UsedForTraining' else 1):
        raise RuntimeError(f'Link not verified: {final}')
    print('  Confirmed:', relationship)


def ensure_approval(w3, manifest, auditor):
    endpoint = f'/api/v1/blockchain/audit/models/{ident(MODEL)}'
    approval = api('GET', endpoint + '/status')['approval']
    if approval['approved']:
        print('  Model already has an active auditor approval; no new transaction')
        return

    metrics = manifest['metrics']
    confusion = manifest['confusion_matrix']
    # This is a test attestation of observed experimental metrics, not a security certification.
    evidence = {
        'evidence_type': 'development_integration_review',
        'model_artifact_id': MODEL,
        'dataset_artifact_id': DATASET,
        'training_run_artifact_id': TRAINING,
        'mlflow_run_id': manifest['mlflow_run_id'],
        'metrics_as_reported_by_training': metrics,
        'confusion_matrix_as_reported_by_training': confusion,
        'decision': 'approve_for_local_integration_test_only',
        'limitations': [
            'No independent validation or reproducibility audit has been performed.',
            'Historical benchmark does not establish production phishing detection safety.',
            'Blockchain approval represents a simulated authorized auditor attestation.'
        ],
    }
    evidence_file = ROOT / 'ml_demo' / 'real_model_audit_evidence.json'
    evidence_file.write_text(json.dumps(evidence, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    evidence_hash = '0x' + digest(evidence_file)
    prepared = api('POST', endpoint + '/prepare-approval', json={
        'auditor_address': auditor, 'evidence_hash': evidence_hash
    })['transaction']
    tx = send_prepared(w3, prepared, auditor)
    api('POST', endpoint + '/confirm-approval', json={'tx_hash': tx})
    approval = api('GET', endpoint + '/status')['approval']
    if not approval['approved'] or approval['evidence_hash'].lower() != evidence_hash.lower():
        raise RuntimeError('Approval status/evidence hash mismatch')
    print('  Test approval verified. Evidence:', evidence_file)


def main():
    if urlparse(RPC_URL).hostname not in {'localhost', '127.0.0.1', '::1'}:
        raise RuntimeError('Script is restricted to a local RPC')
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected() or w3.eth.chain_id != 31337:
        raise RuntimeError('Expected local Hardhat chain 31337')
    developer = Web3.to_checksum_address(w3.eth.accounts[2])
    auditor = Web3.to_checksum_address(w3.eth.accounts[3])
    print('1. Verifying registered artifacts and training manifest')
    manifest = check_artifacts_and_manifest()
    print('2. Dataset -> TrainingRun')
    ensure_link(w3, DATASET, TRAINING, 'UsedForTraining', developer)
    print('3. TrainingRun -> Model')
    ensure_link(w3, TRAINING, MODEL, 'Produced', developer)
    print('4. Unified model provenance')
    prov = api('GET', f'/api/v1/artifacts/{ident(MODEL)}/provenance')
    if not prov.get('overall_verified'):
        raise RuntimeError(f'Unified provenance verification failed: {prov}')
    print('  Verified entire lineage')
    print('5. Auditor integration-test approval')
    ensure_approval(w3, manifest, auditor)
    print('\nSUCCESS: Genuine ML artifacts linked, lineage verified, and test-approved.')
    print('Remember to snapshot the current blockchain before shutting down.')


if __name__ == '__main__':
    main()
