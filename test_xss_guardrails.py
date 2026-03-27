"""XSS Attack Vector Test Script for Guardrails System"""

import sys
sys.path.insert(0, 'src')

from guardrails.rails import check_input_guardrails

XSS_PAYLOADS = [
    "<script>alert('XSS')</script>",
    "<img src=x onerror=alert(1)>",
    "<svg onload=alert('XSS')>",
    "<body onload=alert('XSS')>",
    "<input onfocus=alert('XSS') autofocus>",
    "javascript:alert('XSS')",
    "vbscript:msgbox('XSS')",
    "data:text/html,<script>alert('XSS')</script>",
    "<script>document.cookie</script>",
    "{{constructor.constructor('alert(1)')()}}",
]

def test_xss_payloads():
    print("=" * 70)
    print("XSS ATTACK VECTOR TEST RESULTS")
    print("=" * 70)

    failures = []

    for i, payload in enumerate(XSS_PAYLOADS, 1):
        is_safe, message = check_input_guardrails(payload)

        if is_safe:
            status = "ALLOWED"
            result = "FAIL - Should be blocked!"
            failures.append((i, payload, "No dangerous pattern detected"))
        else:
            status = "BLOCKED"
            result = "PASS"

        print(f"\n[{i}] Payload: {payload}")
        print(f"    Status: {status}")
        print(f"    Result: {result}")

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    if failures:
        print(f"\n!!! SECURITY ISSUE: {len(failures)} XSS payloads were ALLOWED !!!\n")
        for i, payload, reason in failures:
            print(f"  [{i}] {payload}")
            print(f"      Reason: {reason}")
        return False
    else:
        print("\nAll XSS payloads were blocked successfully.")
        return True

if __name__ == "__main__":
    success = test_xss_payloads()
    sys.exit(0 if success else 1)
