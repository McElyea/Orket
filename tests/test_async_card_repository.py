import pytest
import asyncio
import aiosqlite
from orket.infrastructure.async_card_repository import AsyncCardRepository
from orket.schema import CardStatus, CardType
from orket.domain.records import IssueRecord

@pytest.fixture
async def repo(db_path):
    return AsyncCardRepository(db_path)

@pytest.mark.asyncio
async def test_repo_initialization(repo):
    """Verify that tables are created upon first use."""
    # Initialization happens inside get_by_id or other async methods
    result = await repo.get_by_id("non-existent")
    assert result is None
    # If it didn't crash, initialization worked

@pytest.mark.asyncio
async def test_save_and_get_issue(repo):
    """Basic CRUD: Save an issue and retrieve it."""
    issue = IssueRecord(
        id="ISSUE-01",
        summary="Test Issue",
        status=CardStatus.READY,
        seat="lead_architect"
    )
    await repo.save(issue)
    
    retrieved = await repo.get_by_id("ISSUE-01")
    assert retrieved is not None
    assert retrieved.id == "ISSUE-01"
    assert retrieved.summary == "Test Issue"
    assert retrieved.status == CardStatus.READY

@pytest.mark.asyncio
async def test_update_status(repo):
    """Test updating card status and assignee."""
    issue = IssueRecord(id="ISSUE-02", summary="Update Me", seat="standard")
    await repo.save(issue)
    
    await repo.update_status("ISSUE-02", CardStatus.IN_PROGRESS, assignee="agent-007")
    
    retrieved = await repo.get_by_id("ISSUE-02")
    assert retrieved.status == CardStatus.IN_PROGRESS
    assert retrieved.assignee == "agent-007"

@pytest.mark.asyncio
async def test_get_by_build(repo):
    """Test filtering issues by build_id."""
    await repo.save(IssueRecord(id="I1", summary="B1-1", build_id="B1", seat="standard"))
    await repo.save(IssueRecord(id="I2", summary="B1-2", build_id="B1", seat="standard"))
    await repo.save(IssueRecord(id="I3", summary="B2-1", build_id="B2", seat="standard"))
    
    b1_issues = await repo.get_by_build("B1")
    assert len(b1_issues) == 2
    assert {i.id for i in b1_issues} == {"I1", "I2"}

@pytest.mark.asyncio
async def test_transactions(repo):
    """Test manual transaction logging and history retrieval."""
    await repo.save(IssueRecord(id="T1", summary="Tx Test", seat="standard"))
    await repo.add_transaction("T1", "system", "First Action")
    await repo.add_transaction("T1", "developer", "Second Action")
    
    history = await repo.get_card_history("T1")
    assert len(history) >= 2 # update_status also adds transactions
    assert any("First Action" in h for h in history)
    assert any("Second Action" in h for h in history)

@pytest.mark.asyncio
async def test_comments(repo):
    """Test adding and retrieving comments."""
    await repo.save(IssueRecord(id="C1", summary="Comment Test", seat="standard"))
    await repo.add_comment("C1", "author1", "Hello world")
    await repo.add_comment("C1", "author2", "Follow up")
    
    comments = await repo.get_comments("C1")
    assert len(comments) == 2
    assert comments[0]["author"] == "author1"
    assert comments[0]["content"] == "Hello world"

@pytest.mark.asyncio
async def test_reset_build(repo):
    """Verify that reset_build sets all issues in a build back to READY."""
    await repo.save(IssueRecord(id="R1", summary="R1", build_id="BR", status=CardStatus.DONE, seat="standard"))
    await repo.save(IssueRecord(id="R2", summary="R2", build_id="BR", status=CardStatus.IN_PROGRESS, seat="standard"))
    
    await repo.reset_build("BR")
    
    issues = await repo.get_by_build("BR")
    assert all(i.status == CardStatus.READY for i in issues)

@pytest.mark.asyncio
async def test_independent_ready_issues(repo):
    """Test dependency-aware issue selection."""
    # I1: No deps, READY
    await repo.save(IssueRecord(id="I1", summary="I1", build_id="DAG", status=CardStatus.READY, seat="standard"))
    # I2: Deps on I1, READY
    await repo.save(IssueRecord(id="I2", summary="I2", build_id="DAG", status=CardStatus.READY, depends_on=["I1"], seat="standard"))
    # I3: No deps, DONE
    await repo.save(IssueRecord(id="I3", summary="I3", build_id="DAG", status=CardStatus.DONE, seat="standard"))
    # I4: Deps on I3, READY
    await repo.save(IssueRecord(id="I4", summary="I4", build_id="DAG", status=CardStatus.READY, depends_on=["I3"], seat="standard"))
    
    ready = await repo.get_independent_ready_issues("DAG")
    # I1 is ready (no deps). I4 is ready (dep I3 is DONE). 
    # I2 is NOT ready (dep I1 is READY, not DONE).
    ready_ids = {i.id for i in ready}
    assert ready_ids == {"I1", "I4"}

@pytest.mark.asyncio
async def test_concurrency_stress(repo):
    """Stress test with concurrent saves to ensure locking works."""
    tasks = []
    for i in range(20):
        issue = IssueRecord(id=f"CONC-{i}", summary=f"Stress {i}", seat="standard")
        tasks.append(repo.save(issue))
    
    await asyncio.gather(*tasks)
    
    for i in range(20):
        retrieved = await repo.get_by_id(f"CONC-{i}")
        assert retrieved is not None
        assert retrieved.id == f"CONC-{i}"

@pytest.mark.asyncio
async def test_serialization_edge_cases(repo):
    """Test handling of empty or malformed JSON in extended fields."""
    # Manually insert malformed JSON via direct sqlite if needed, 
    # but here we test the _deserialize_row through normal flow
    issue = IssueRecord(id="EDGE", summary="Edge Case", seat="standard")
    await repo.save(issue)
    
    retrieved = await repo.get_by_id("EDGE")
    assert retrieved.depends_on == []
    assert retrieved.verification == {}

@pytest.mark.asyncio
async def test_update_status_transaction_logging(repo):
    """Verify that update_status automatically logs a transaction."""
    issue = IssueRecord(id="TX-LOG", summary="Tx Log Test", seat="standard")
    await repo.save(issue)
    
    await repo.update_status("TX-LOG", CardStatus.IN_PROGRESS, assignee="agent-x")
    
    history = await repo.get_card_history("TX-LOG")
    assert any("Set Status to 'in_progress'" in h for h in history)
    assert any("agent-x" in h for h in history)

@pytest.mark.asyncio
async def test_deserialize_corrupted_json(repo):
    """Test _deserialize_row with actual corrupted JSON string in DB."""
    async with repo._lock:
        async with aiosqlite.connect(repo.db_path) as conn:
            await repo._ensure_initialized(conn)
            await conn.execute(
                "INSERT INTO issues (id, seat, summary, type, priority, status, depends_on_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("CORRUPT", "standard", "Corrupt Test", "issue", 2.0, "ready", "{invalid json")
            )
            await conn.commit()
            
    retrieved = await repo.get_by_id("CORRUPT")
    assert retrieved.depends_on == [] # Should fallback to empty list
