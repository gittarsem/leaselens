import requests
import json
import time
from datetime import datetime
from pathlib import Path

# ============================================================
# LEASELENS AUTOMATED TEST SUITE
# ============================================================

BASE_URL = "http://127.0.0.1:8000"

TENANT_ID = "tenant_36d29328"
LEASE_ID = "lease_a60c78d4"

CHAT_ENDPOINT = f"{BASE_URL}/chat"

QUESTIONS = [

    # ========================================================
    # BASIC FACT EXTRACTION
    # ========================================================

    "What is my monthly rent?",
    "How much security deposit have I paid?",
    "What is the lock-in period?",
    "What is the notice period?",
    "What happens if I leave during the lock-in period?",
    "What is the late rent penalty?",
    "Can the landlord terminate my lease immediately?",
    "When is my rent due?",
    "What are my responsibilities as a tenant?",
    "What are the landlord's responsibilities?",

    # ========================================================
    # CONTRADICTION DETECTION
    # ========================================================

    "Find all contradictions in my lease agreement.",
    "Does my lease mention different rent amounts in different clauses?",
    "Are there conflicting security deposit amounts?",
    "Is the notice period consistent throughout the agreement?",
    "Are there contradictory rules regarding eviction?",
    "Compare the lock-in period and termination conditions across all clauses.",
    "Are there conflicting maintenance responsibilities?",
    "Are there different rules regarding rent payment?",
    "Identify all inconsistencies in the lease.",
    "Give me a complete contradiction analysis of this agreement.",

    # ========================================================
    # DUPLICATE AND OVERLAPPING CLAUSES
    # ========================================================

    "Find duplicate clauses in my lease.",
    "Are there clauses that discuss the same topic but impose different obligations?",
    "Identify overlapping clauses related to security deposit deductions.",
    "Are painting and maintenance obligations repeated in multiple places?",
    "Find clauses that are semantically similar even if their wording differs.",
    "Identify duplicate eviction and termination clauses.",
    "Find repeated penalty provisions.",
    "Identify all overlapping tenant obligations.",
    "Are there duplicate rent-related provisions?",
    "Give me a complete duplicate and overlap analysis.",

    # ========================================================
    # FINANCIAL EXPOSURE
    # ========================================================

    "Calculate my total potential financial exposure under this lease.",
    "What penalties could I face if I terminate the lease early?",
    "How much can my landlord potentially deduct from my security deposit?",
    "What financial risks are associated with this agreement?",
    "Calculate the maximum quantified financial liability mentioned in the lease.",
    "What is the total amount of non-refundable charges?",
    "What penalties apply if I pay rent late?",
    "What financial deductions can be made for painting?",
    "What financial deductions can be made for maintenance?",
    "Summarize all monetary obligations mentioned in the lease.",

    # ========================================================
    # CLAUSE-SPECIFIC ANALYSIS
    # ========================================================

    "Explain Clause 1.1 in simple language.",
    "What does Clause 1.2 say about termination?",
    "Explain Clause 1.3 and its implications.",
    "What does Clause 2.1 say about rent and penalties?",
    "Explain Clause 3.1 regarding the security deposit.",
    "What does Clause 3.2 say about painting charges?",
    "Explain Clause 4.2 regarding maintenance responsibilities.",
    "What does Clause 7.4 say about deductions?",
    "Explain Clause 8.1 regarding painting.",
    "What does Clause 10.1 say about termination and possession?",

    # ========================================================
    # COMPREHENSIVE REVIEW
    # ========================================================

    "Review my lease and identify the top 10 risks for me as a tenant.",
    "Which clauses are unfair or potentially unfavorable to me?",
    "What clauses should I negotiate before signing?",
    "Give me a complete tenant-friendly summary of this lease.",
    "What are the most dangerous clauses in this agreement?",
]


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def format_response(response):
    """Safely parse API response."""

    content_type = response.headers.get("content-type", "")

    if "application/json" in content_type:
        try:
            return response.json()
        except Exception:
            return response.text

    return response.text


def run_test(question, test_number, total_tests):

    print("\n" + "=" * 100)
    print(f"TEST {test_number}/{total_tests}")
    print("=" * 100)

    print(f"\nQUESTION:\n{question}")

    # Correct API payload
    payload = {
        "tenant_id": str(TENANT_ID),
        "lease_id": str(LEASE_ID),
        "message": str(question),
    }

    print("\nDEBUG: OUTGOING PAYLOAD")
    print(json.dumps(payload, indent=2, ensure_ascii=False))

    start_time = time.time()

    try:

        # ----------------------------------------------------
        # Prepare HTTP request explicitly
        # ----------------------------------------------------

        request = requests.Request(
            method="POST",
            url=CHAT_ENDPOINT,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )

        prepared_request = request.prepare()

        # ----------------------------------------------------
        # Debug outgoing request
        # ----------------------------------------------------

        print("\nDEBUG: REQUEST URL")
        print(prepared_request.url)

        print("\nDEBUG: REQUEST HEADERS")
        print(prepared_request.headers)

        print("\nDEBUG: REQUEST BODY")

        if isinstance(prepared_request.body, bytes):
            print(prepared_request.body.decode("utf-8"))
        else:
            print(prepared_request.body)

        # ----------------------------------------------------
        # Send request
        # ----------------------------------------------------

        session = requests.Session()

        response = session.send(
            prepared_request,
            timeout=180,
        )

        duration = round(time.time() - start_time, 2)

        response_data = format_response(response)

        success = response.status_code == 200

        # ----------------------------------------------------
        # Print response
        # ----------------------------------------------------

        print(f"\nHTTP STATUS: {response.status_code}")
        print(f"TIME: {duration}s")

        print("\nRESPONSE:")

        if isinstance(response_data, dict):

            print(
                json.dumps(
                    response_data,
                    indent=2,
                    ensure_ascii=False,
                )
            )

        else:

            print(response_data)

        # ----------------------------------------------------
        # Return test result
        # ----------------------------------------------------

        return {
            "test_number": test_number,
            "question": question,
            "http_status": response.status_code,
            "duration_seconds": duration,
            "success": success,
            "response": response_data,
            "error": None,
        }

    except requests.exceptions.Timeout:

        duration = round(time.time() - start_time, 2)

        print("\nERROR: Request timed out")

        return {
            "test_number": test_number,
            "question": question,
            "http_status": None,
            "duration_seconds": duration,
            "success": False,
            "response": None,
            "error": "Request timeout",
        }

    except requests.exceptions.ConnectionError as e:

        duration = round(time.time() - start_time, 2)

        print("\nERROR: Could not connect to LeaseLens backend")
        print(e)

        return {
            "test_number": test_number,
            "question": question,
            "http_status": None,
            "duration_seconds": duration,
            "success": False,
            "response": None,
            "error": str(e),
        }

    except Exception as e:

        duration = round(time.time() - start_time, 2)

        print(f"\nERROR: {e}")

        return {
            "test_number": test_number,
            "question": question,
            "http_status": None,
            "duration_seconds": duration,
            "success": False,
            "response": None,
            "error": str(e),
        }


# ============================================================
# MAIN EXECUTION
# ============================================================

def main():

    print("\n")
    print("=" * 100)
    print("LEASELENS AUTOMATED TEST SUITE")
    print("=" * 100)

    print(f"Backend: {BASE_URL}")
    print(f"Tenant: {TENANT_ID}")
    print(f"Lease: {LEASE_ID}")
    print(f"Total tests: {len(QUESTIONS)}")

    # --------------------------------------------------------
    # Check backend connectivity
    # --------------------------------------------------------

    print("\nChecking backend connectivity...")

    try:

        health_response = requests.get(
            BASE_URL,
            timeout=5,
        )

        print(
            f"Backend responded with HTTP "
            f"{health_response.status_code}"
        )

    except Exception as e:

        print("WARNING: Could not verify backend health.")
        print("Make sure your FastAPI server is running.")
        print(e)

    # --------------------------------------------------------
    # Run tests
    # --------------------------------------------------------

    results = []

    for index, question in enumerate(QUESTIONS, start=1):

        result = run_test(
            question=question,
            test_number=index,
            total_tests=len(QUESTIONS),
        )

        results.append(result)

        # Prevent overwhelming backend
        time.sleep(1)

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    total_tests = len(results)

    successful_tests = sum(
        1
        for result in results
        if result["success"]
    )

    failed_tests = total_tests - successful_tests

    total_duration = sum(
        result["duration_seconds"]
        for result in results
    )

    average_duration = (
        round(total_duration / total_tests, 2)
        if total_tests > 0
        else 0
    )

    success_rate = (
        round((successful_tests / total_tests) * 100, 2)
        if total_tests > 0
        else 0
    )

    print("\n")
    print("=" * 100)
    print("TEST SUMMARY")
    print("=" * 100)

    print(f"Total tests:      {total_tests}")
    print(f"Successful:       {successful_tests}")
    print(f"Failed:           {failed_tests}")
    print(f"Success rate:     {success_rate}%")
    print(f"Total duration:   {round(total_duration, 2)} seconds")
    print(f"Average duration: {average_duration} seconds")

    # --------------------------------------------------------
    # Failed tests
    # --------------------------------------------------------

    if failed_tests > 0:

        print("\nFAILED TESTS")
        print("-" * 100)

        for result in results:

            if not result["success"]:

                print(
                    f"\nTEST {result['test_number']}: "
                    f"{result['question']}"
                )

                print(
                    f"HTTP STATUS: "
                    f"{result['http_status']}"
                )

                print(
                    f"ERROR: "
                    f"{result['error']}"
                )

    # --------------------------------------------------------
    # Save report
    # --------------------------------------------------------

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    output_file = Path(
        f"leaselens_test_results_{timestamp}.json"
    )

    report = {
        "timestamp": datetime.now().isoformat(),
        "backend": BASE_URL,
        "tenant_id": TENANT_ID,
        "lease_id": LEASE_ID,
        "total_tests": total_tests,
        "successful_tests": successful_tests,
        "failed_tests": failed_tests,
        "success_rate": success_rate,
        "total_duration_seconds": round(
            total_duration,
            2,
        ),
        "average_duration_seconds": average_duration,
        "results": results,
    }

    with open(
        output_file,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            report,
            f,
            indent=2,
            ensure_ascii=False,
        )

    # --------------------------------------------------------
    # Report location
    # --------------------------------------------------------

    print("\n")
    print("=" * 100)
    print("REPORT SAVED")
    print("=" * 100)

    print(f"\nFile: {output_file.absolute()}")

    print("\nTest suite completed.")


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
