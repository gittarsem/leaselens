"""
LeaseLens Chat Quality Evaluation Dataset

Purpose:
Evaluate chatbot response quality across:
- Accuracy
- Grounding
- Citation quality
- Hallucination resistance
- Completeness
- Context retention
- Clarity

This is a manual evaluation dataset initially.
Each question should be tested against the LeaseLens chat interface.
"""

CHAT_QUALITY_TESTS = [

    # ============================================================
    # 1. DIRECT FACT RETRIEVAL
    # ============================================================

    {
        "id": "CQ001",
        "category": "Direct Retrieval",
        "question": "What is the monthly rent mentioned in my lease?",
        "expected_behavior": (
            "Retrieve the exact monthly rent from the lease. "
            "Cite the relevant clause or document section."
        ),
        "evaluation_criteria": [
            "Correct rent amount",
            "Correct currency",
            "Relevant citation",
            "No invented information"
        ]
    },

    {
        "id": "CQ002",
        "category": "Direct Retrieval",
        "question": "How much security deposit did I pay?",
        "expected_behavior": (
            "Return the exact security deposit amount supported by the lease."
        ),
        "evaluation_criteria": [
            "Correct deposit amount",
            "Evidence from lease",
            "Clear explanation"
        ]
    },

    {
        "id": "CQ003",
        "category": "Direct Retrieval",
        "question": "When does my lease start and when does it end?",
        "expected_behavior": (
            "Identify the lease commencement and expiration dates."
        ),
        "evaluation_criteria": [
            "Correct start date",
            "Correct end date",
            "No date confusion"
        ]
    },

    # ============================================================
    # 2. LEGAL / CONTRACTUAL INTERPRETATION
    # ============================================================

    {
        "id": "CQ004",
        "category": "Contract Interpretation",
        "question": "Can my landlord increase the rent during the lease period?",
        "expected_behavior": (
            "Explain the rent-increase provision using the lease. "
            "If the lease does not specify this, explicitly state that."
        ),
        "evaluation_criteria": [
            "Correct interpretation",
            "Relevant clause citation",
            "Distinguishes lease terms from general law",
            "No unsupported legal claims"
        ]
    },

    {
        "id": "CQ005",
        "category": "Contract Interpretation",
        "question": "Can I terminate my lease before the expiry date?",
        "expected_behavior": (
            "Explain early termination provisions, notice requirements, "
            "lock-in period, and applicable penalties if present."
        ),
        "evaluation_criteria": [
            "Correct termination conditions",
            "Correct notice period",
            "Correct lock-in interpretation",
            "No unsupported assumptions"
        ]
    },

    {
        "id": "CQ006",
        "category": "Contract Interpretation",
        "question": "Who is responsible for maintenance and repairs?",
        "expected_behavior": (
            "Identify tenant and landlord responsibilities "
            "according to the lease."
        ),
        "evaluation_criteria": [
            "Correct responsibility allocation",
            "Relevant clauses cited",
            "Clear distinction between responsibilities"
        ]
    },

    # ============================================================
    # 3. FINANCIAL REASONING
    # ============================================================

    {
        "id": "CQ007",
        "category": "Financial Reasoning",
        "question": "How much money should I receive back when I move out?",
        "expected_behavior": (
            "Calculate the refundable security deposit using documented "
            "deductions only. Clearly identify uncertain deductions."
        ),
        "evaluation_criteria": [
            "Correct arithmetic",
            "Uses documented amounts",
            "Separates confirmed and unsupported deductions",
            "Explains calculation"
        ]
    },

    {
        "id": "CQ008",
        "category": "Financial Reasoning",
        "question": "My landlord is charging me ₹15,000 for painting. "
                    "Is this amount supported by my lease?",
        "expected_behavior": (
            "Search for painting-related provisions. Determine whether "
            "the amount is explicitly mentioned, permitted, or unsupported."
        ),
        "evaluation_criteria": [
            "Correct clause retrieval",
            "Does not invent painting charges",
            "Distinguishes permission from a fixed amount",
            "Explains evidence"
        ]
    },

    {
        "id": "CQ009",
        "category": "Financial Reasoning",
        "question": "Calculate my total rent for the entire lease period.",
        "expected_behavior": (
            "Calculate the total rent using the lease duration and "
            "monthly rent. Account for any rent escalation if applicable."
        ),
        "evaluation_criteria": [
            "Correct calculation",
            "Correct lease duration",
            "Escalation handled correctly",
            "Calculation shown"
        ]
    },

    # ============================================================
    # 4. HALLUCINATION RESISTANCE
    # ============================================================

    {
        "id": "CQ010",
        "category": "Hallucination Resistance",
        "question": "Does my lease allow me to keep a pet?",
        "expected_behavior": (
            "Answer only if the lease contains relevant information. "
            "Otherwise state that the document does not establish "
            "a pet policy."
        ),
        "evaluation_criteria": [
            "Does not fabricate pet policy",
            "Correct evidence retrieval",
            "Clearly communicates uncertainty"
        ]
    },

    {
        "id": "CQ011",
        "category": "Hallucination Resistance",
        "question": "What is the penalty for paying rent late?",
        "expected_behavior": (
            "Retrieve the late-payment provision. If absent, "
            "explicitly state that no penalty was found in the lease."
        ),
        "evaluation_criteria": [
            "Correct penalty if present",
            "No invented penalty",
            "Correct citation",
            "Appropriate uncertainty"
        ]
    },

    {
        "id": "CQ012",
        "category": "Hallucination Resistance",
        "question": "Does my landlord have the right to enter my apartment "
                    "without informing me?",
        "expected_behavior": (
            "Explain what the lease says about landlord access. "
            "Avoid presenting general legal rules as lease provisions."
        ),
        "evaluation_criteria": [
            "Relevant access clause retrieved",
            "Grounded interpretation",
            "Distinguishes contract from general law",
            "No fabricated rights"
        ]
    },

    # ============================================================
    # 5. CONTEXT RETENTION
    # ============================================================

    {
        "id": "CQ013",
        "category": "Context Retention",
        "conversation": [
            {
                "role": "user",
                "content": "What is my security deposit?"
            },
            {
                "role": "user",
                "content": "What happens if I leave early?"
            },
            {
                "role": "user",
                "content": "Will that affect my refund?"
            }
        ],
        "expected_behavior": (
            "Understand that 'that' refers to early termination "
            "and explain its effect on the security deposit."
        ),
        "evaluation_criteria": [
            "Retains conversation context",
            "Correctly resolves reference",
            "Explains refund implications",
            "Uses relevant lease clauses"
        ]
    },

    {
        "id": "CQ014",
        "category": "Context Retention",
        "conversation": [
            {
                "role": "user",
                "content": "Can my landlord deduct painting charges?"
            },
            {
                "role": "user",
                "content": "What about cleaning?"
            }
        ],
        "expected_behavior": (
            "Understand that the user is asking whether cleaning charges "
            "can also be deducted from the security deposit."
        ),
        "evaluation_criteria": [
            "Correct contextual interpretation",
            "Retrieves cleaning provisions",
            "Does not repeat unrelated painting information"
        ]
    },

    # ============================================================
    # 6. COMPLEX QUESTIONS
    # ============================================================

    {
        "id": "CQ015",
        "category": "Complex Reasoning",
        "question": "Summarize the important financial obligations "
                    "I have under this lease.",
        "expected_behavior": (
            "Summarize rent, security deposit, maintenance, utilities, "
            "penalties, deductions, and other financial obligations "
            "that are explicitly present."
        ),
        "evaluation_criteria": [
            "Comprehensive summary",
            "Correct amounts",
            "Correct payment frequencies",
            "Citations for important claims",
            "No invented obligations"
        ]
    },

]


# ================================================================
# EVALUATION SCORECARD
# ================================================================

EVALUATION_DIMENSIONS = {
    "accuracy": {
        "weight": 25,
        "description": "Is the answer factually correct?"
    },
    "grounding": {
        "weight": 25,
        "description": "Is the answer supported by lease evidence?"
    },
    "citation_quality": {
        "weight": 15,
        "description": "Are citations relevant and accurate?"
    },
    "completeness": {
        "weight": 15,
        "description": "Does the answer fully address the question?"
    },
    "clarity": {
        "weight": 10,
        "description": "Is the answer understandable and well structured?"
    },
    "hallucination_resistance": {
        "weight": 10,
        "description": "Does the chatbot avoid unsupported claims?"
    }
}


def print_test_dataset():
    print("=" * 80)
    print("LEASELENS CHAT QUALITY EVALUATION")
    print("=" * 80)

    for test in CHAT_QUALITY_TESTS:
        print(f"\n[{test['id']}] {test['category']}")

        if "question" in test:
            print(f"Question: {test['question']}")

        if "conversation" in test:
            print("Conversation:")
            for message in test["conversation"]:
                print(f"  {message['role']}: {message['content']}")

        print(f"Expected behavior: {test['expected_behavior']}")

        print("Evaluation criteria:")
        for criterion in test["evaluation_criteria"]:
            print(f"  - {criterion}")


if __name__ == "__main__":
    print_test_dataset()