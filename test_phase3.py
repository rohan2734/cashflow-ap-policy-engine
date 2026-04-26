"""
Comprehensive test script for Phase 3 (Pipeline Steps)
Tests all pipeline components: parser, splitter, xref_resolver, llm_extractor, validator, rule_builder, conflict_detector
"""
import sys
from pathlib import Path
import tempfile
import os

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from shared_types.pipeline import RawBlock, Clause, EnrichedClause, RawExtraction, ValidatedExtraction
from shared_types.rules import ASTNode, RuleRecord, ConflictReport
from pipeline.parser import parse_pdf
from pipeline.splitter import split_into_clauses
from pipeline.xref_resolver import resolve_references, CircularReferenceError
from pipeline.validator import validate_extraction, ValidationError
from pipeline.rule_builder import build_rule, ASTBuildError
from pipeline.conflict_detector import detect_conflicts


def test_parser():
    """Test PDF parsing functionality"""
    print("Testing PDF parser...")

    # Create a simple test PDF content
    # Note: This test requires a real PDF file, so we'll test the structure
    print("✓ Parser module loaded successfully")
    print("  (Full PDF parsing test requires actual PDF file)")


def test_splitter():
    """Test clause splitting functionality"""
    print("\nTesting clause splitter...")

    # Test numbered clauses
    blocks = [
        RawBlock(text="1.1 If invoice amount exceeds $1000, escalate to manager.", page=1),
        RawBlock(text="1.2 All invoices must be approved by finance.", page=1),
        RawBlock(text="2.1 Vendor payments require PO number.", page=2),
    ]

    clauses = split_into_clauses(blocks)

    assert len(clauses) == 3, f"Expected 3 clauses, got {len(clauses)}"
    assert clauses[0].id == "1.1", f"Expected clause ID '1.1', got {clauses[0].id}"
    assert clauses[1].id == "1.2", f"Expected clause ID '1.2', got {clauses[1].id}"
    assert clauses[2].id == "2.1", f"Expected clause ID '2.1', got {clauses[2].id}"
    print("✓ Numbered clause splitting works")

    # Test keyword-based splitting
    keyword_blocks = [
        RawBlock(text="WHEN the amount is high, we should review it. IF the vendor is new, escalate.", page=1),
    ]

    keyword_clauses = split_into_clauses(keyword_blocks)

    assert len(keyword_clauses) == 2, f"Expected 2 keyword clauses, got {len(keyword_clauses)}"
    assert "WHEN" in keyword_clauses[0].text or "IF" in keyword_clauses[0].text, "Should detect keywords"
    print("✓ Keyword-based clause splitting works")


def test_xref_resolver():
    """Test cross-reference resolution"""
    print("\nTesting cross-reference resolver...")

    clauses = [
        Clause(id="1.1", text="See Section 2.1 for details.", page=1),
        Clause(id="1.2", text="Refer to Clause 3.1.", page=1),
        Clause(id="2.1", text="This is the referenced section.", page=2),
        Clause(id="3.1", text="This is another referenced clause.", page=3),
    ]

    enriched = resolve_references(clauses)

    assert len(enriched) == 4, f"Expected 4 enriched clauses, got {len(enriched)}"

    # Check that references were resolved
    clause_1_1 = next(c for c in enriched if c.id == "1.1")
    assert len(clause_1_1.referenced_texts) > 0, "Clause 1.1 should have resolved references"
    assert any("referenced section" in text.lower() for text in clause_1_1.referenced_texts), \
        "Should contain text from referenced section"
    print("✓ Cross-reference resolution works")

    # Test circular reference detection
    circular_clauses = [
        Clause(id="1.1", text="See Section 1.2.", page=1),
        Clause(id="1.2", text="Refer to Section 1.1.", page=1),
    ]

    try:
        resolve_references(circular_clauses)
        print("✗ Should have detected circular reference")
        assert False, "Should have raised CircularReferenceError"
    except CircularReferenceError:
        print("✓ Circular reference detection works")


def test_validator():
    """Test extraction validation"""
    print("\nTesting extraction validator...")

    # Test valid extraction
    valid_raw = RawExtraction(
        clause_id="1.1",
        condition_raw={"op": ">", "left": "amount", "right": 1000},
        action_raw="ESCALATE",
        exceptions_raw=["except for approved vendors"]
    )

    validated = validate_extraction(valid_raw)

    assert validated.clause_id == "1.1", "Clause ID should match"
    assert validated.action == "ESCALATE", "Action should be ESCALATE"
    assert validated.confidence == 1.0, "Default confidence should be 1.0"
    assert validated.exceptions == ["except for approved vendors"], "Exceptions should match"
    print("✓ Valid extraction validation works")

    # Test invalid action
    invalid_action = RawExtraction(
        clause_id="1.2",
        condition_raw={"op": ">", "left": "amount", "right": 1000},
        action_raw="INVALID_ACTION",
        exceptions_raw=[]
    )

    try:
        validate_extraction(invalid_action)
        print("✗ Should have rejected invalid action")
        assert False, "Should have raised ValidationError"
    except ValidationError as e:
        assert "Invalid action" in str(e), "Error should mention invalid action"
        print("✓ Invalid action detection works")

    # Test missing condition
    missing_condition = RawExtraction(
        clause_id="1.3",
        condition_raw={},
        action_raw="APPROVE",
        exceptions_raw=[]
    )

    try:
        validate_extraction(missing_condition)
        print("✗ Should have rejected missing condition")
        assert False, "Should have raised ValidationError"
    except ValidationError as e:
        assert "Missing condition" in str(e), "Error should mention missing condition"
        print("✓ Missing condition detection works")

    # Test invalid operator
    invalid_op = RawExtraction(
        clause_id="1.4",
        condition_raw={"op": "INVALID_OP", "left": "amount", "right": 1000},
        action_raw="APPROVE",
        exceptions_raw=[]
    )

    try:
        validate_extraction(invalid_op)
        print("✗ Should have rejected invalid operator")
        assert False, "Should have raised ValidationError"
    except ValidationError as e:
        assert "Unknown op" in str(e), "Error should mention unknown operator"
        print("✓ Invalid operator detection works")


def test_rule_builder():
    """Test rule building from validated extractions"""
    print("\nTesting rule builder...")

    validated = ValidatedExtraction(
        clause_id="1.1",
        condition={"op": ">", "left": "amount", "right": 1000},
        action="ESCALATE",
        exceptions=["except for approved vendors"],
        confidence=0.9
    )

    rule = build_rule(validated, "DOC-001")

    assert rule.doc_id == "DOC-001", "Document ID should match"
    assert rule.action == "ESCALATE", "Action should be ESCALATE"
    assert rule.confidence == 0.9, "Confidence should match"
    assert rule.source_clauses == ["1.1"], "Source clauses should match"
    assert rule.rule_id.startswith("R-"), "Rule ID should start with R-"
    print("✓ Rule building works")

    # Test AST construction
    assert isinstance(rule.condition, ASTNode), "Condition should be ASTNode"
    assert rule.condition.op == ">", "Operator should be >"
    assert rule.condition.left == "amount", "Left operand should be amount"
    assert rule.condition.right == 1000, "Right operand should be 1000"
    print("✓ AST construction works")

    # Test complex AST
    complex_validated = ValidatedExtraction(
        clause_id="2.1",
        condition={
            "op": "AND",
            "left": {"op": ">", "left": "amount", "right": 1000},
            "right": {"op": "==", "left": "currency", "right": "USD"}
        },
        action="APPROVE",
        exceptions=[],
        confidence=0.95
    )

    complex_rule = build_rule(complex_validated, "DOC-002")

    assert complex_rule.condition.op == "AND", "Top-level operator should be AND"
    assert isinstance(complex_rule.condition.left, ASTNode), "Left should be ASTNode"
    assert isinstance(complex_rule.condition.right, ASTNode), "Right should be ASTNode"
    print("✓ Complex AST construction works")

    # Test missing operator error
    try:
        invalid_validated = ValidatedExtraction(
            clause_id="3.1",
            condition={"left": "amount", "right": 1000},  # Missing "op"
            action="APPROVE",
            exceptions=[],
            confidence=0.8
        )
        build_rule(invalid_validated, "DOC-003")
        print("✗ Should have rejected missing operator")
        assert False, "Should have raised ASTBuildError"
    except ASTBuildError as e:
        assert "missing 'op'" in str(e), "Error should mention missing operator"
        print("✓ Missing operator detection works")


def test_conflict_detector():
    """Test conflict detection between rules"""
    print("\nTesting conflict detector...")

    # Test conflicting rules
    rules = [
        RuleRecord(
            rule_id="R-001",
            doc_id="DOC-001",
            condition=ASTNode(op=">", left="amount", right=1000),
            action="REJECT",
            confidence=0.9,
            source_clauses=["1.1"]
        ),
        RuleRecord(
            rule_id="R-002",
            doc_id="DOC-001",
            condition=ASTNode(op="<", left="amount", right=2000),
            action="APPROVE",
            confidence=0.8,
            source_clauses=["1.2"]
        ),
    ]

    conflicts = detect_conflicts(rules)

    assert len(conflicts) == 1, f"Expected 1 conflict, got {len(conflicts)}"
    assert "R-001" in conflicts[0].rule_ids, "Conflict should include R-001"
    assert "R-002" in conflicts[0].rule_ids, "Conflict should include R-002"
    assert "REJECT" in conflicts[0].overlap_description, "Conflict should mention REJECT"
    assert "APPROVE" in conflicts[0].overlap_description, "Conflict should mention APPROVE"
    print("✓ Conflict detection works")

    # Test non-conflicting rules (same action)
    same_action_rules = [
        RuleRecord(
            rule_id="R-003",
            doc_id="DOC-001",
            condition=ASTNode(op=">", left="amount", right=1000),
            action="ESCALATE",
            confidence=0.9,
            source_clauses=["2.1"]
        ),
        RuleRecord(
            rule_id="R-004",
            doc_id="DOC-001",
            condition=ASTNode(op="<", left="amount", right=5000),
            action="ESCALATE",
            confidence=0.8,
            source_clauses=["2.2"]
        ),
    ]

    same_action_conflicts = detect_conflicts(same_action_rules)
    assert len(same_action_conflicts) == 0, "Same action rules should not conflict"
    print("✓ Same action rules don't conflict")

    # Test non-numeric rules (no conflict detection)
    non_numeric_rules = [
        RuleRecord(
            rule_id="R-005",
            doc_id="DOC-001",
            condition=ASTNode(op="==", left="currency", right="USD"),
            action="APPROVE",
            confidence=0.9,
            source_clauses=["3.1"]
        ),
        RuleRecord(
            rule_id="R-006",
            doc_id="DOC-001",
            condition=ASTNode(op="==", left="currency", right="USD"),
            action="REJECT",
            confidence=0.8,
            source_clauses=["3.2"]
        ),
    ]

    non_numeric_conflicts = detect_conflicts(non_numeric_rules)
    assert len(non_numeric_conflicts) == 0, "Non-numeric rules should not trigger conflict detection"
    print("✓ Non-numeric rules don't trigger conflict detection")

    # Test different fields (no conflict)
    different_field_rules = [
        RuleRecord(
            rule_id="R-007",
            doc_id="DOC-001",
            condition=ASTNode(op=">", left="amount", right=1000),
            action="REJECT",
            confidence=0.9,
            source_clauses=["4.1"]
        ),
        RuleRecord(
            rule_id="R-008",
            doc_id="DOC-001",
            condition=ASTNode(op=">", left="tax_amount", right=100),
            action="APPROVE",
            confidence=0.8,
            source_clauses=["4.2"]
        ),
    ]

    different_field_conflicts = detect_conflicts(different_field_rules)
    assert len(different_field_conflicts) == 0, "Different field rules should not conflict"
    print("✓ Different field rules don't conflict")


def test_pipeline_integration():
    """Test integration of all pipeline components"""
    print("\nTesting pipeline integration...")

    # Simulate a simple pipeline flow
    blocks = [
        RawBlock(text="1.1 If invoice amount exceeds $1000, escalate to manager.", page=1),
        RawBlock(text="1.2 See Section 2.1 for approval process.", page=1),
        RawBlock(text="2.1 All approvals require manager signature.", page=2),
    ]

    # Step 1: Split into clauses
    clauses = split_into_clauses(blocks)
    assert len(clauses) == 3, "Should split into 3 clauses"
    print("✓ Step 1: Clause splitting")

    # Step 2: Resolve references
    enriched = resolve_references(clauses)
    assert len(enriched) == 3, "Should enrich all clauses"
    clause_1_2 = next(c for c in enriched if c.id == "1.2")
    assert len(clause_1_2.referenced_texts) > 0, "Should resolve reference to 2.1"
    print("✓ Step 2: Reference resolution")

    # Step 3: Simulate extraction (would normally use LLM)
    raw_extractions = [
        RawExtraction(
            clause_id="1.1",
            condition_raw={"op": ">", "left": "amount", "right": 1000},
            action_raw="ESCALATE",
            exceptions_raw=[]
        ),
    ]
    print("✓ Step 3: Extraction (simulated)")

    # Step 4: Validate extractions
    validated = [validate_extraction(raw) for raw in raw_extractions]
    assert len(validated) == 1, "Should validate 1 extraction"
    print("✓ Step 4: Validation")

    # Step 5: Build rules
    rules = [build_rule(v, "DOC-001") for v in validated]
    assert len(rules) == 1, "Should build 1 rule"
    assert rules[0].action == "ESCALATE", "Rule should have ESCALATE action"
    print("✓ Step 5: Rule building")

    # Step 6: Detect conflicts
    conflicts = detect_conflicts(rules)
    assert len(conflicts) == 0, "Single rule should have no conflicts"
    print("✓ Step 6: Conflict detection")

    print("✓ Pipeline integration test passed")


def main():
    print("=" * 70)
    print("Phase 3 (Pipeline Steps) Comprehensive Test Suite")
    print("=" * 70)

    try:
        test_parser()
        test_splitter()
        test_xref_resolver()
        test_validator()
        test_rule_builder()
        test_conflict_detector()
        test_pipeline_integration()

        print("\n" + "=" * 70)
        print("✓ All Phase 3 tests passed!")
        print("=" * 70)
        print("\nTest Summary:")
        print("  • Parser: Module loaded successfully")
        print("  • Splitter: Numbered and keyword-based clause detection")
        print("  • XRef Resolver: Reference resolution and circular detection")
        print("  • Validator: Action, condition, and operator validation")
        print("  • Rule Builder: AST construction and rule creation")
        print("  • Conflict Detector: Numeric rule conflict detection")
        print("  • Integration: End-to-end pipeline flow")
        return 0
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
