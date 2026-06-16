"""
批量上传本地工作流到 ComfyUI 服务器并逐个测试
"""
import paramiko, time, json, os, glob

SERVER = 'connect.nmb1.seetacloud.com'
PORT = 21523
USER = 'root'
PASS = 'kucg0hnB6AmI'
REMOTE_DIR = '/root/autodl-tmp/ComfyUI/user/default/workflows/pixelle'
LOCAL_DIR = 'D:/claude/ylf_Video/workflows/selfhost'

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(SERVER, port=PORT, username=USER, password=PASS, timeout=10)

# Create remote dir
stdin, stdout, stderr = c.exec_command(f'mkdir -p {REMOTE_DIR}')
time.sleep(0.5)

# Upload all .json files
files = sorted(glob.glob(f'{LOCAL_DIR}/*.json'))
print(f'Uploading {len(files)} workflows...')

results = []
for fpath in files:
    fname = os.path.basename(fpath)
    with open(fpath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Validate JSON
    try:
        wf = json.loads(content)
    except json.JSONDecodeError as e:
        results.append((fname, 'SKIP', f'Invalid JSON: {e}'))
        continue

    # Upload
    stdin, stdout, stderr = c.exec_command(f'cat > {REMOTE_DIR}/{fname}')
    stdin.write(content)
    stdin.close()
    time.sleep(0.2)

    # Test via API
    api_json = json.dumps({'prompt': wf, 'client_id': f'test_{fname}'})
    stdin, stdout, stderr = c.exec_command(
        f"curl -s -X POST http://127.0.0.1:6006/prompt -d '{api_json}'"
    )
    time.sleep(1)
    resp = stdout.read().decode().strip()

    try:
        r = json.loads(resp)
        if 'node_errors' in r and (not r['node_errors'] or r['node_errors'] == {}):
            results.append((fname, 'OK', f'prompt_id={r.get("prompt_id", "?")}'))
        else:
            errors = r.get('node_errors', r.get('error', str(r)))
            results.append((fname, 'FAIL', str(errors)[:150]))
    except:
        results.append((fname, 'FAIL', resp[:150]))

    print(f'  {fname[:50]:50s} {results[-1][1]}')

c.close()

# Summary
print(f'\n=== Results ({len(files)} total) ===')
ok = [r for r in results if r[1] == 'OK']
fail = [r for r in results if r[1] == 'FAIL']
skip = [r for r in results if r[1] == 'SKIP']
print(f'OK: {len(ok)} | FAIL: {len(fail)} | SKIP: {len(skip)}')
if fail:
    print('\nFailed:')
    for fname, _, err in fail:
        print(f'  {fname}: {err[:100]}')
