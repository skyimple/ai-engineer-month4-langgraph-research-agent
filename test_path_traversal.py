"""Security test for path traversal attacks against guardrails."""
import sys
sys.path.insert(0, 'src')

from guardrails.rails import check_input_guardrails

PATH_TRAVERSAL_PAYLOADS = [
    "../../../etc/passwd",
    "..\\..\\..\\windows\\system32\\config\\sam",
    "/etc/passwd%00.jpg",
    "....//....//....//etc/passwd",
    "/var/www/html/../../../etc/shadow",
    "php://filter/read=convert.base64-encode/resource=index.php",
    "data://text/plain;base64,PD9waHAgc3lzdGVtKCRfR0VUWydjbWQnXSk7ID8+",
    "file:///etc/passwd",
    "gopher://127.0.0.1:6379/_INFO",
    "sftp://evil.com/etc/passwd",
]

print("=" * 70)
print("Path Traversal Attack Test Results")
print("=" * 70)

vulnerabilities = []

for i, payload in enumerate(PATH_TRAVERSAL_PAYLOADS, 1):
    is_safe, message = check_input_guardrails(payload)

    if is_safe:
        status = "ALLOWED"
        reason = "No blocking pattern detected"
        vulnerabilities.append((i, payload, status, reason))
    else:
        status = "BLOCKED"
        reason = message.strip()

    print(f"\n{i}. Payload: {payload}")
    print(f"   Status: {status}")
    print(f"   Reason: {reason}")

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)

if vulnerabilities:
    print(f"\nSECURITY ISSUE: {len(vulnerabilities)} path traversal attack(s) ALLOWED!\n")
    for i, payload, status, reason in vulnerabilities:
        print(f"  [{i}] {payload}")
else:
    print("\nAll path traversal attacks were BLOCKED.")

print("\n" + "=" * 70)

# Exit with error code if vulnerabilities found
sys.exit(1 if vulnerabilities else 0)