"""
Simple test script for Phase 5 (Execution Engine)
Tests rule evaluation and execution logic
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from shared_types.rules import ASTNode, RuleRecord
from shared_types.invoice import InvoiceRecord, ExecutionResult
from engine.evaluator import evaluate_node, EvaluationError
from engine.executor import execute_rules, PRIORITY


def test_simple_evaluation():
    """Test simple rule evaluation"""
    print("Testing simple rule evaluation...")

    # Test numeric comparison
    invoice = InvoiceRecord(
        invoice_id="INV-001",
        fields={"amount": 1500, "currency": "USD"}
    )

    # Test greater than
    node = ASTNode(op=">", left="amount", right=1000)
    result = evaluate_node(node, invoice)
    assert result == True, "1500 > 1000 should be True"
    print("✓ Greater than evaluation works")

    # Test less than
    node = ASTNode(op="<", left="amount", right=2000)
    result = evaluate_node(node, invoice)
    assert result == True, "1500 < 2000 should be True"
    print("✓ Less than evaluation works")

    # Test equality
    node = ASTNode(op=="", left="currency", right="USD")
    result = evaluate_node(node, invoice)
    assert result == True, "currency == USD should be True"
    print("✓ Equality evaluation works")


def test_complex_evaluation():
    """Test complex rule evaluation with AND/OR"""
    print("\nTesting complex rule evaluation...")

    invoice = InvoiceRecord(
        invoice_id="INV-002",
        fields={"amount": 1500, "currency": "USD", "vendor": "ACME"}
    )

    # Test AND
    node = ASTNode(
        op="AND",
        left=ASTNode(op=">", left="amount", right=1000),
        right=ASTNode(op=="", left="currency", right="USD")
    )
    result = evaluate_node(node, invoice)
    assert result == True, "amount > 1000 AND currency == USD should be True"
    print("✓ AND evaluation works")

    # Test OR
    node = ASTNode(
        op="OR",
        left=ASTNode(op="<", left="amount", right=1000),
        right=ASTNode(op=="", left="currency", right="USD")
    )
    result = evaluate_node(node, invoice)
    assert result == True, "amount < 1000 OR currency == USD should be True"
    print("✓ OR evaluation works")

    # Test NOT
    node = ASTNode(
        op="NOT",
        left=ASTNode(op=="", left="currency", right="EUR")
    )
    result = evaluate_node(node, invoice)
    assert result == True, "NOT (currency == EUR) should be True"
    print("✓ NOT evaluation works")


def test_arithmetic_operations():
    """Test arithmetic operations"""
    print("\nTesting arithmetic operations...")

    invoice = InvoiceRecord(
        invoice_id="INV-003",
        fields={"amount": 1000, "tax_rate": 0.1}
    )

    # Test multiplication
    node = ASTNode(
        op="*",
        left="amount",
        right="tax_rate"
    )
    result = evaluate_node(node, invoice)
    assert result == 100.0, "1000 * 0.1 should be 100.0"
    print("✓ Multiplication works")

    # Test addition
    node = ASTNode(
        op="+",
        left="amount",
        right=500
    )
    result = evaluate_node(node, invoice)
    assert result == 1500, "1000 + 500 should be 1500"
    print("✓ Addition works")


def test_rule_execution():
    """Test rule execution with multiple rules"""
    print("\nTesting rule execution...")

    invoice = InvoiceRecord(
        invoice_id="INV-004",
        fields={"amount": 1500, "currency": "USD", "vendor": "ACME"}
    )

    # Create test rules
    rules = [
        RuleRecord(
            rule_id="R-001",
            doc_id="DOC-001",
            condition=ASTNode(op=">", left="amount", right=1000),
            action="ESCALATE",
            confidence=0.9,
            source_clauses=["clause-1"]
        ),
        RuleRecord(
            rule_id="R-002",
            doc_id="DOC-001",
            condition=ASTNode(op="<", left="amount", right=500),
            action="APPROVE",
            confidence=0.95,
            source_clauses=["clause-2"]
        ),
        RuleRecord(
            rule_id="R-003",
            doc_id="DOC-001",
            condition=ASTNode(op=">", left="amount", right=10000),
            action="REJECT",
            confidence=0.8,
            source_clauses=["clause-3"]
        )
    ]

    result = execute_rules(rules, invoice, "DOC-001")

    # Should trigger R-001 (ESCALATE) since 1500 > 1000
    assert result.decision == "ESCALATE", f"Expected ESCALATE, got {result.decision}"
    assert "R-001" in result.triggered_rule_ids, "R-001 should be triggered"
    assert "R-002" not in result.triggered_rule_ids, "R-002 should not be triggered"
    print("✓ Rule execution works correctly")


def test_priority_ordering():
    """Test that REJECT > ESCALATE > APPROVE priority is respected"""
    print("\nTesting priority ordering...")

    invoice = InvoiceRecord(
        invoice_id="INV-005",
        fields={"amount": 1500, "currency": "USD"}
    )

    # Create rules that all trigger but with different priorities
    rules = [
        RuleRecord(
            rule_id="R-APPROVE",
            doc_id="DOC-001",
            condition=ASTNode(op=">", left="amount", right=0),
            action="APPROVE",
            confidence=0.9,
            source_clauses=["clause-1"]
        ),
        RuleRecord(
            rule_id="R-ESCALATE",
            doc_id="DOC-001",
            condition=ASTNode(op=">", left="amount", right=0),
            action="ESCALATE",
            confidence=0.8,
            source_clauses=["clause-2"]
        ),
        RuleRecord(
            rule_id="R-REJECT",
            doc_id="DOC-001",
            condition=ASTNode(op=">", left="amount", right=0),
            action="REJECT",
            confidence=0.7,
            source_clauses=["clause-3"]
        )
    ]

    result = execute_rules(rules, invoice, "DOC-001")

    # REJECT should win due to highest priority
    assert result.decision == "REJECT", f"Expected REJECT, got {result.decision}"
    assert len(result.triggered_rule_ids) == 3, "All 3 rules should be triggered"
    print("✓ Priority ordering works correctly")


def test_no_rules_triggered():
    """Test behavior when no rules are triggered"""
    print("\nTesting no rules triggered scenario...")

    invoice = InvoiceRecord(
        invoice_id="INV-006",
        fields={"amount": 100, "currency": "USD"}
    )

    rules = [
        RuleRecord(
            rule_id="R-001",
            doc_id="DOC-001",
            condition=ASTNode(op=">", left="amount", right=1000),
            action="ESCALATE",
            confidence=0.9,
            source_clauses=["clause-1"]
        )
    ]

    result = execute_rules(rules, invoice, "DOC-001")

    assert result.decision == "APPROVE", "Should default to APPROVE when no rules trigger"
    assert len(result.triggered_rule_ids) == 0, "No rules should be triggered"
    assert "No rules triggered" in result.reasons, "Should explain why no rules triggered"
    print("✓ No rules triggered scenario works correctly")


def test_evaluation_error_handling():
    """Test that evaluation errors are handled gracefully"""
    print("\nTesting evaluation error handling...")

    invoice = InvoiceRecord(
        invoice_id="INV-007",
        fields={"amount": 1000}
    )

    # Test invalid operator
    try:
        node = ASTNode(op="INVALID", left="amount", right=1000)
        result = evaluate_node(node, invoice)
        print("✗ Should have raised EvaluationError for invalid operator")
        assert False, "Should have raised error"
    except EvaluationError:
        print("✓ Invalid operator raises EvaluationError")

    # Test missing field (should return the field name as string)
    node = ASTNode(op=">", left="nonexistent_field", right=1000)
    result = evaluate_node(node, invoice)
    assert result == "nonexistent_field", "Missing field should return field name"
    print("✓ Missing field handling works")


def main():
    print("=" * 60)
    print("Phase 5 (Execution Engine) Test Suite")
    print("=" * 60)

    try:
        test_simple_evaluation()
        test_complex_evaluation()
        test_arithmetic_operations()
        test_rule_execution()
        test_priority_ordering()
        test_no_rules_triggered()
        test_evaluation_error_handling()

        print("\n" + "=" * 60)
        print("✓ All Phase 5 tests passed!")
        print("=" * 60)
        return 0
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())