"""批量测试工作流"""
import paramiko, time, json, os, glob

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('connect.nmb1.seetacloud.com', port=21523, username='root', password='kucg0hnB6AmI', timeout=10)

dir = 'D:/claude/ylf_Video/workflows/selfhost'
results = []

for fpath in sorted(glob.glob(f'{dir}/*.json')):
    fname = os.path.basename(fpath)
    try:
        with open(fpath, 'r', encoding='utf-8') as f:
            wf = json.load(f)
    except Exception as e:
        results.append((fname, 'JSON_ERR', str(e)[:80]))
        continue

    # Submit to API
    api = json.dumps({'prompt': wf, 'client_id': f'test_{fname}'})
    # Write to temp file on server to avoid shell escaping issues
    stdin, stdout, stderr = c.exec_command(f'cat > /tmp/test_wf.json')
    stdin.write(api)
    stdin.close()
    time.sleep(0.3)

    stdin2, stdout2, stderr2 = c.exec_command('curl -s -X POST http://127.0.0.1:6006/prompt -d @/tmp/test_wf.json')
    time.sleep(0.5)
    resp = stdout2.read().decode().strip()

    try:
        r = json.loads(resp)
        errs = r.get('node_errors', {})
        if not errs or errs == {}:
            results.append((fname, 'OK', r.get('prompt_id', '')))
        else:
            # Format first error
            first = list(errs.items())[0] if errs else ('?', str(errs))
            results.append((fname, 'NODE_ERR', f'{first[0]}: {str(first[1])[:100]}'))
    except:
        results.append((fname, 'API_ERR', resp[:100]))

c.exec_command('rm -f /tmp/test_wf.json')
c.close()

# Report
print(f'\n=== Results ({len(results)} total) ===')
ok = [r for r in results if r[1] == 'OK']
fail = [r for r in results if r[1] != 'OK']
print(f'OK: {len(ok)} | FAIL: {len(fail)}')
print('\n--- OK ---')
for name, status, detail in ok:
    print(f'  {name:45s} {detail}')
print('\n--- FAIL ---')
for name, status, detail in fail:
    print(f'  {name:45s} {status}: {detail}')
