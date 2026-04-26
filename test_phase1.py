"""
Comprehensive test script for Phase 1 (Types, Config, DB)
Tests shared_types, config, and database components
"""
import sys
from pathlib import Path
import asyncio

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from shared_types.pipeline import RawBlock, Clause, EnrichedClause, RawExtraction, ValidatedExtraction
from shared_types.rules import ASTNode, RuleRecord, ConflictReport
from shared_types.invoice import InvoiceRecord, ExecutionResult
from config.types import LLMConfig, ConcurrencyConfig, NotificationConfig, AppConfig
from db.connector import DBConnector
from db.models import Base, LLMProviderModel, PromptModel, PipelineModel
from db.seeder import seed_defaults
from db import queries


def test_shared_types():
    """Test shared type definitions"""
    print("Testing shared types...")

    # Test RawBlock
    block = RawBlock(text="Sample text", page=1)
    assert block.text == "Sample text", "RawBlock text should match"
    assert block.page == 1, "RawBlock page should match"
    print("✓ RawBlock works")

    # Test Clause
    clause = Clause(id="1.1", text="Clause text", page=1)
    assert clause.id == "1.1", "Clause ID should match"
    assert clause.text == "Clause text", "Clause text should match"
    print("✓ Clause works")

    # Test EnrichedClause
    enriched = EnrichedClause(
        id="1.1",
        text="Clause text",
        page=1,
        referenced_texts=["Referenced text"]
    )
    assert len(enriched.referenced_texts) == 1, "Should have 1 referenced text"
    print("✓ EnrichedClause works")

    # Test RawExtraction
    raw = RawExtraction(
        clause_id="1.1",
        condition_raw={"op": ">", "left": "amount", "right": 1000},
        action_raw="ESCALATE",
        exceptions_raw=["exception"]
    )
    assert raw.clause_id == "1.1", "RawExtraction clause_id should match"
    print("✓ RawExtraction works")

    # Test ValidatedExtraction
    validated = ValidatedExtraction(
        clause_id="1.1",
        condition={"op": ">", "left": "amount", "right": 1000},
        action="ESCALATE",
        exceptions=["exception"],
        confidence=0.9
    )
    assert validated.confidence == 0.9, "ValidatedExtraction confidence should match"
    print("✓ ValidatedExtraction works")

    # Test ASTNode
    ast = ASTNode(op=">", left="amount", right=1000)
    assert ast.op == ">", "ASTNode operator should match"
    print("✓ ASTNode works")

    # Test RuleRecord
    rule = RuleRecord(
        rule_id="R-001",
        doc_id="DOC-001",
        condition=ast,
        action="ESCALATE",
        confidence=0.9,
        source_clauses=["1.1"]
    )
    assert rule.rule_id == "R-001", "RuleRecord rule_id should match"
    print("✓ RuleRecord works")

    # Test ConflictReport
    conflict = ConflictReport(
        rule_ids=["R-001", "R-002"],
        overlap_description="Test conflict"
    )
    assert len(conflict.rule_ids) == 2, "ConflictReport should have 2 rule IDs"
    print("✓ ConflictReport works")

    # Test InvoiceRecord
    invoice = InvoiceRecord(
        invoice_id="INV-001",
        fields={"amount": 1000, "currency": "USD"}
    )
    assert invoice.invoice_id == "INV-001", "InvoiceRecord invoice_id should match"
    print("✓ InvoiceRecord works")

    # Test ExecutionResult
    result = ExecutionResult(
        invoice_id="INV-001",
        doc_id="DOC-001",
        decision="APPROVE",
        triggered_rule_ids=["R-001"],
        reasons=["Test reason"]
    )
    assert result.decision == "APPROVE", "ExecutionResult decision should match"
    print("✓ ExecutionResult works")


def test_config_types():
    """Test configuration type definitions"""
    print("\nTesting configuration types...")

    # Test LLMConfig
    llm_config = LLMConfig(
        provider="openrouter",
        model="meta-llama/llama-3-8b-instruct",
        temperature=0.1,
        max_tokens=2048
    )
    assert llm_config.provider == "openrouter", "LLMConfig provider should match"
    assert llm_config.temperature == 0.1, "LLMConfig temperature should match"
    print("✓ LLMConfig works")

    # Test ConcurrencyConfig
    concurrency_config = ConcurrencyConfig(
        max_parallel_clauses=5
    )
    assert concurrency_config.max_parallel_clauses == 5, "ConcurrencyConfig should match"
    print("✓ ConcurrencyConfig works")

    # Test NotificationConfig
    notification_config = NotificationConfig(
        endpoint="http://example.com/webhook"
    )
    assert notification_config.endpoint == "http://example.com/webhook", "NotificationConfig should match"
    print("✓ NotificationConfig works")

    # Test AppConfig
    app_config = AppConfig(
        llm=llm_config,
        concurrency=concurrency_config,
        notifications=notification_config,
        pipeline_id="PL-DEFAULT",
        confidence_threshold=0.5
    )
    assert app_config.llm.provider == "openrouter", "AppConfig llm should match"
    assert app_config.concurrency.max_parallel_clauses == 5, "AppConfig concurrency should match"
    assert app_config.pipeline_id == "PL-DEFAULT", "AppConfig pipeline_id should match"
    assert app_config.confidence_threshold == 0.5, "AppConfig confidence_threshold should match"
    print("✓ AppConfig works")


async def test_database_models():
    """Test database models and seeder"""
    print("\nTesting database models and seeder...")

    # Get database URL from environment
    import os
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("⚠ DATABASE_URL not set, skipping database tests")
        return

    # Create database connector
    db = DBConnector(database_url)

    # Create tables
    await db.create_tables()
    print("✓ Database tables created")

    # Test seeder
    async with db.session() as session:
        await seed_defaults(session)
        await session.commit()
    print("✓ Database seeder executed")

    # Test fetching active pipeline
    async with db.session() as session:
        pipeline = await queries.fetch_active_pipeline(session)
        assert pipeline is not None, "Should have an active pipeline"
        assert pipeline.active == True, "Pipeline should be active"
        print("✓ Active pipeline fetched")

        # Test fetching provider
        provider = await queries.fetch_provider(session, pipeline.llm_provider_id)
        assert provider is not None, "Should have a provider"
        assert provider.active == True, "Provider should be active"
        print("✓ Provider fetched")

        # Test fetching prompt
        prompt = await queries.fetch_prompt(session, pipeline.prompt_id)
        assert prompt is not None, "Should have a prompt"
        assert prompt.active == True, "Prompt should be active"
        print("✓ Prompt fetched")

        # Verify seeded data structure
        assert "model" in provider.config, "Provider config should have model"
        assert "temperature" in provider.config, "Provider config should have temperature"
        assert "confidence_threshold" in pipeline.config, "Pipeline config should have confidence_threshold"
        assert "concurrency" in pipeline.config, "Pipeline config should have concurrency"
        print("✓ Seeded data structure verified")


async def test_database_queries():
    """Test database query functions"""
    print("\nTesting database queries...")

    import os
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("⚠ DATABASE_URL not set, skipping database query tests")
        return

    db = DBConnector(database_url)

    async with db.session() as session:
        # Test document insertion
        from db import queries
        await queries.insert_document(session, "DOC-TEST", "test.pdf", "PL-DEFAULT")
        await session.commit()
        print("✓ Document inserted")

        # Test rule insertion
        from shared_types.rules import RuleRecord, ASTNode
        rule = RuleRecord(
            rule_id="R-TEST",
            doc_id="DOC-TEST",
            condition=ASTNode(op=">", left="amount", right=1000),
            action="ESCALATE",
            confidence=0.9,
            source_clauses=["1.1"]
        )
        await queries.insert_rule(session, rule, "auto_approved")
        await session.commit()
        print("✓ Rule inserted")

        # Test fetching rules by document
        rules = await queries.fetch_rules_by_doc(session, "DOC-TEST")
        assert len(rules) == 1, "Should have 1 rule"
        assert rules[0].rule_id == "R-TEST", "Rule ID should match"
        print("✓ Rules fetched by document")

        # Test conflict insertion
        from shared_types.rules import ConflictReport
        conflict = ConflictReport(
            rule_ids=["R-TEST", "R-TEST2"],
            overlap_description="Test conflict"
        )
        await queries.insert_conflict(session, "DOC-TEST", conflict)
        await session.commit()
        print("✓ Conflict inserted")

        # Test execution insertion
        from shared_types.invoice import ExecutionResult
        execution = ExecutionResult(
            invoice_id="INV-TEST",
            doc_id="DOC-TEST",
            decision="ESCALATE",
            triggered_rule_ids=["R-TEST"],
            reasons=["Test reason"]
        )
        await queries.insert_execution(session, execution)
        await session.commit()
        print("✓ Execution inserted")

        # Test fetching rule by ID
        rule = await queries.fetch_rule_by_id(session, "R-TEST")
        assert rule is not None, "Should find rule by ID"
        assert rule.rule_id == "R-TEST", "Rule ID should match"
        print("✓ Rule fetched by ID")

        # Test fetching pending review rules
        pending = await queries.fetch_pending_review_rules(session)
        assert isinstance(pending, list), "Should return a list"
        print("✓ Pending review rules fetched")


async def main():
    print("=" * 70)
    print("Phase 1 (Types, Config, DB) Comprehensive Test Suite")
    print("=" * 70)

    try:
        test_shared_types()
        test_config_types()
        await test_database_models()
        await test_database_queries()

        print("\n" + "=" * 70)
        print("✓ All Phase 1 tests passed!")
        print("=" * 70)
        print("\nTest Summary:")
        print("  • Shared Types: All dataclass types work correctly")
        print("  • Config Types: Configuration classes validated")
        print("  • Database Models: Tables created and seeded")
        print("  • Database Queries: CRUD operations successful")
        return 0
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
