# Orket Development Roadmap (v0.3.8 → v1.0)

**Last Updated**: 2026-02-09
**Current Version**: v0.3.8 "The Diagnostic Intelligence"
**Goal**: Reach v1.0 "Production Ready" for UI revamp

---

## 🎯 Vision: Three Stages of Maturity

### Stage 1: **Functioning** (v0.4.0 - Target: 4 weeks)
Backend works end-to-end with manual oversight. Agents can complete simple projects with human guidance.

### Stage 2: **Fully Functioning** (v0.5.0 - Target: 8 weeks)
Backend runs autonomously. Agents complete projects, deploy to sandboxes, iterate on feedback without human intervention.

### Stage 3: **Production Ready** (v1.0 - Target: 12 weeks)
System is battle-tested, documented, and ready for UI. Can onboard new users, handle errors gracefully, scale to multiple concurrent projects.

---

## 📊 Current State: v0.3.8

### ✅ What Works
- State Machine with WaitReason enforcement
- Tool Gating (pre-execution validation)
- Priority-based scheduling
- 49 tests passing
- Gitea running (Git + CI/CD infrastructure)
- PR review policy with loop prevention
- Credential management
- Backup system (local only)

### ⚠️ What's Incomplete
- Sandbox Orchestrator (designed but not integrated)
- Bug Fix Phase Manager (designed but not integrated)
- Gitea webhook handler (built but not wired up)
- ExecutionPipeline integration hooks (missing)
- No actual sandbox deployments happening
- No automated testing of generated code
- No UI for monitoring/control

### ❌ What's Broken/Missing
- Sandboxes don't auto-create on PR merge
- No actual Docker Compose generation happening
- Tech stack detection doesn't exist yet
- Gitea Actions not configured
- No webhook endpoint in Orket
- No connection between Orket ↔ Gitea
- Bug Fix Phase never starts
- Requirements Issue creation doesn't work
- No architect escalation actually happening

---

## 🚧 Phase 3: Elegant Failure & Recovery (IN PROGRESS)

**Goal**: Backend can recover from failures, sandbox lifecycle works, agents can iterate on feedback.

### 3.1 - Sandbox Orchestrator Integration (CRITICAL)
**Status**: 🟡 Designed, not integrated
**Blockers**: None
**Time**: 2-3 days

**Work Needed**:
- [ ] Add SandboxOrchestrator to ExecutionPipeline.__init__
- [ ] Hook sandbox creation in _handle_code_review_approval()
- [ ] Implement tech stack detection from workspace files
- [ ] Test Docker Compose generation with real FastAPI+React project
- [ ] Verify port allocation works (test with 3 simultaneous sandboxes)
- [ ] Add sandbox health monitoring to traction loop
- [ ] Create "sandbox status" tool for agents to inspect
- [ ] Add sandbox cleanup on Bug Fix Phase end

**Code Files**:
- `orket/orket.py` (ExecutionPipeline)
- `orket/services/sandbox_orchestrator.py`
- `orket/domain/sandbox.py`

---

### 3.2 - Bug Fix Phase Manager Integration
**Status**: 🟡 Designed, not integrated
**Blockers**: Sandbox Orchestrator must work first
**Time**: 1-2 days

**Work Needed**:
- [ ] Add BugFixPhaseManager to ExecutionPipeline.__init__
- [ ] Hook phase start on Rock → DONE
- [ ] Implement daily bug discovery monitoring (background task)
- [ ] Add bug rate calculation (bugs per day)
- [ ] Implement auto-extension logic (up to 4 weeks)
- [ ] Trigger sandbox cleanup when phase ends
- [ ] Create Phase 2 Rock with migrated bugs
- [ ] Add organizational thresholds to organization.json

**Code Files**:
- `orket/orket.py` (ExecutionPipeline)
- `orket/domain/bug_fix_phase.py`
- `config/organization.json`

---

### 3.3 - Gitea Webhook Integration
**Status**: 🟡 Handler built, not connected
**Blockers**: Need Flask/FastAPI endpoint
**Time**: 1 day

**Work Needed**:
- [ ] Create Flask app for webhook endpoint (`orket/webhook_server.py`)
- [ ] Route POST /webhook/gitea to GiteaWebhookHandler
- [ ] Validate webhook signatures (HMAC)
- [ ] Store review cycle count in SQLite (not in-memory)
- [ ] Test PR review flow end-to-end
- [ ] Configure Gitea webhook in test repo
- [ ] Handle all event types (review, merge, push)

**Code Files**:
- `orket/webhook_server.py` (NEW)
- `orket/services/gitea_webhook_handler.py`
- `orket/infrastructure/sqlite_repositories.py` (add PR tracking)

---

### 3.4 - Gitea Actions Configuration
**Status**: 🔴 Not started
**Blockers**: Webhook integration
**Time**: 2 days

**Work Needed**:
- [ ] Create `.gitea/workflows/deploy-sandbox.yml` template
- [ ] Configure Gitea Actions runner (Docker socket access)
- [ ] Test workflow triggers on PR merge
- [ ] Add workflow to call Orket API for sandbox deployment
- [ ] Handle workflow failures (retry logic)
- [ ] Add status badges to PRs

**Code Files**:
- `.gitea/workflows/` templates
- Gitea Actions runner config

---

### 3.5 - Empirical Verification (FIT Integration)
**Status**: 🟡 Basic verification exists, needs expansion
**Blockers**: Sandboxes must be running
**Time**: 3 days

**Work Needed**:
- [ ] Expand VerificationEngine to test running sandboxes
- [ ] Add API endpoint testing (pytest + requests)
- [ ] Add E2E frontend testing (Playwright)
- [ ] Run tests BEFORE marking Issue as DONE
- [ ] If tests fail → back to CODE_REVIEW with logs
- [ ] Add test result attachments to PRs
- [ ] Create test report in Gitea

**Code Files**:
- `orket/domain/verification.py`
- `orket/orchestration/engine.py`

---

### 3.6 - Memory Hygiene & Restart Mechanism
**Status**: 🔴 Not started
**Blockers**: None
**Time**: 2 days

**Work Needed**:
- [ ] Clear LLM context between sessions
- [ ] Implement session checkpointing (save after each Issue)
- [ ] Add `resume_session(session_id, from_issue_id)` method
- [ ] Test crash recovery (kill mid-session, resume)
- [ ] Add session history viewer
- [ ] Prevent hallucination drift on long sessions

**Code Files**:
- `orket/session.py`
- `orket/orchestration/engine.py`

---

### 3.7 - Error Handling & Policy Violation Reports
**Status**: 🔴 Not started
**Blockers**: None
**Time**: 2 days

**Work Needed**:
- [ ] Create PolicyViolationReport class
- [ ] Catch StateMachineError → generate report
- [ ] Catch ToolGateViolation → generate report
- [ ] Include: what was attempted, why it failed, how to fix
- [ ] Save reports to database
- [ ] Show reports in UI/CLI
- [ ] Add "Policy Violation" label to Issues

**Code Files**:
- `orket/domain/policy_violation.py` (NEW)
- `orket/domain/state_machine.py`
- `orket/services/tool_gate.py`

---

## 🎯 Phase 4: UI Preparation (v0.4.0)

**Goal**: Backend stable enough for UI revamp. All core loops working.

### 4.1 - API Layer for UI
**Status**: 🔴 Not started
**Blockers**: Phase 3 must be complete
**Time**: 1 week

**Work Needed**:
- [ ] Create FastAPI app (`orket/api/`)
- [ ] Endpoints:
  - `GET /api/board` - Card hierarchy
  - `GET /api/cards/{id}` - Card details
  - `POST /api/cards/{id}/execute` - Run card
  - `GET /api/sessions` - List sessions
  - `GET /api/sessions/{id}` - Session transcript
  - `GET /api/sandboxes` - List running sandboxes
  - `GET /api/sandboxes/{id}/logs` - Sandbox logs
  - `POST /api/sandboxes/{id}/stop` - Stop sandbox
- [ ] WebSocket for live transcript streaming
- [ ] Authentication (API keys)
- [ ] Rate limiting
- [ ] CORS configuration

**Code Files**:
- `orket/api/` (NEW directory)
- `orket/api/main.py`
- `orket/api/routes/`
- `orket/api/middleware/`

---

### 4.2 - Monitoring & Observability
**Status**: 🔴 Not started
**Blockers**: None
**Time**: 1 week

**Work Needed**:
- [ ] Metrics collection (Prometheus format)
  - Cards executed per day
  - Average execution time
  - Tool call success rate
  - State machine violations
  - Sandbox uptime
- [ ] Health check endpoint (`/health`)
- [ ] Add structured logging (JSON format)
- [ ] Log aggregation (all agents → central log)
- [ ] Performance profiling (slow queries, bottlenecks)

**Code Files**:
- `orket/monitoring/` (NEW directory)
- `orket/logging.py` (enhance)

---

### 4.3 - Documentation for UI Developers
**Status**: 🟡 Partial (needs expansion)
**Blockers**: API must be built first
**Time**: 3 days

**Work Needed**:
- [ ] API documentation (OpenAPI/Swagger)
- [ ] WebSocket protocol documentation
- [ ] State machine flow diagrams
- [ ] Example UI workflows
- [ ] Authentication guide
- [ ] Deployment guide
- [ ] Troubleshooting guide

**Code Files**:
- `docs/API.md` (NEW)
- `docs/UI_INTEGRATION.md` (NEW)

---

## 🚀 Phase 5: Production Readiness (v1.0)

**Goal**: System is production-grade, documented, tested, and scalable.

### 5.1 - Comprehensive Testing
**Status**: 🟡 Basic tests exist (49), need more
**Blockers**: Phase 3 + 4 complete
**Time**: 1 week

**Work Needed**:
- [ ] Integration tests for all Phase 3 features
- [ ] End-to-end tests (full Rock → Sandbox → Bug Phase → Cleanup)
- [ ] Performance tests (10 concurrent Rocks)
- [ ] Chaos testing (random failures, network issues)
- [ ] Load testing (100+ Issues)
- [ ] Security testing (injection attacks, privilege escalation)
- [ ] Reach 80%+ code coverage

**Target**: 150+ tests

---

### 5.2 - User Onboarding
**Status**: 🔴 Not started
**Blockers**: None
**Time**: 3 days

**Work Needed**:
- [ ] Setup wizard (`orket init`)
- [ ] Interactive configuration
- [ ] Sample projects (templates)
- [ ] Guided tutorials
- [ ] Video walkthroughs
- [ ] FAQ documentation

**Code Files**:
- `orket/cli/setup_wizard.py` (NEW)
- `docs/GETTING_STARTED.md` (NEW)

---

### 5.3 - Multi-User Support
**Status**: 🔴 Not started
**Blockers**: API layer
**Time**: 1 week

**Work Needed**:
- [ ] User authentication (JWT)
- [ ] Role-based access control (admin, developer, viewer)
- [ ] Workspace isolation (user → workspace mapping)
- [ ] Shared workspaces (team collaboration)
- [ ] Audit logging (who did what)
- [ ] User management UI

**Code Files**:
- `orket/auth/` (NEW directory)
- `orket/api/middleware/auth.py`

---

### 5.4 - Deployment Options
**Status**: 🔴 Not started
**Blockers**: None
**Time**: 3 days

**Work Needed**:
- [ ] Docker Compose for full stack (Orket + Gitea + UI)
- [ ] Kubernetes manifests (optional)
- [ ] Systemd service files (Linux)
- [ ] Windows Service installer
- [ ] Automated updates (version checking)
- [ ] Migration scripts (database schema changes)

**Code Files**:
- `deploy/` (NEW directory)
- `deploy/docker-compose.full-stack.yml`
- `deploy/systemd/`

---

### 5.5 - Enterprise Features (Optional)
**Status**: 🔴 Not started
**Blockers**: v1.0 core complete
**Time**: 2 weeks

**Work Needed**:
- [ ] LDAP/SSO integration
- [ ] High availability (multi-instance)
- [ ] Database replication
- [ ] Backup encryption
- [ ] Compliance logging (SOC2, ISO27001)
- [ ] Custom branding

---

## 📋 Critical Path: v0.3.8 → v0.4.0 (Functioning)

**Must-have for v0.4.0**:
1. ✅ Sandbox Orchestrator integration (3.1)
2. ✅ Bug Fix Phase integration (3.2)
3. ✅ Gitea webhook working (3.3)
4. ✅ End-to-end test: Issue → PR → Review → Merge → Sandbox → UAT
5. ✅ Error handling (3.7)

**Estimated time**: 2-3 weeks

---

## 📋 Critical Path: v0.4.0 → v0.5.0 (Fully Functioning)

**Must-have for v0.5.0**:
1. ✅ Gitea Actions configured (3.4)
2. ✅ Empirical verification working (3.5)
3. ✅ Memory hygiene (3.6)
4. ✅ Architect escalation actually happening
5. ✅ Requirements Issue auto-creation working
6. ✅ 100+ tests passing

**Estimated time**: 4 weeks from v0.4.0

---

## 📋 Critical Path: v0.5.0 → v1.0 (Production Ready)

**Must-have for v1.0**:
1. ✅ API layer complete (4.1)
2. ✅ Monitoring & metrics (4.2)
3. ✅ API documentation (4.3)
4. ✅ Comprehensive testing (5.1)
5. ✅ User onboarding (5.2)
6. ✅ Deployment automation (5.4)

**Estimated time**: 4 weeks from v0.5.0

---

## 🎯 Total Timeline to v1.0

**Conservative estimate**: 12 weeks (3 months)
**Aggressive estimate**: 8 weeks (2 months)
**Realistic estimate**: 10 weeks

**Current date**: 2026-02-09
**Target v1.0 date**: 2026-04-20 (10 weeks)

---

## 🔥 Immediate Next Steps (This Week)

### Priority 1 (Critical)
1. Fix `configure_gitea_privacy.sh` and run it
2. Set up local-only automated backups (Windows Task Scheduler)
3. Integrate Sandbox Orchestrator into ExecutionPipeline
4. Test Docker Compose generation with sample project

### Priority 2 (Important)
5. Add webhook endpoint to Orket
6. Connect Gitea webhook to handler
7. Test PR review cycle end-to-end

### Priority 3 (Nice to have)
8. Add tech stack detection
9. Implement sandbox health monitoring
10. Create sandbox status tool for agents

---

## 📊 Success Metrics

### v0.4.0 "Functioning"
- [ ] Can generate FastAPI + React project
- [ ] Can deploy to sandbox automatically
- [ ] Can run basic tests
- [ ] Can iterate on PR feedback
- [ ] Sandboxes auto-cleanup after Bug Fix Phase
- [ ] 75+ tests passing

### v0.5.0 "Fully Functioning"
- [ ] Runs autonomously for 8+ hours without intervention
- [ ] Completes 5+ projects end-to-end
- [ ] Handles errors gracefully (no crashes)
- [ ] Bug Fix Phase works as designed
- [ ] Architect escalation prevents infinite loops
- [ ] 125+ tests passing

### v1.0 "Production Ready"
- [ ] 10+ users can onboard without help
- [ ] Handles 10 concurrent projects
- [ ] API stable and documented
- [ ] UI can be built against API
- [ ] Deployment takes < 10 minutes
- [ ] 150+ tests passing
- [ ] Zero known critical bugs

---

## 🛠️ Known Issues & Technical Debt

### High Priority
1. **ExecutionPipeline is too large** (400+ lines) - needs refactoring
2. **No connection pooling** for database (SQLite → PostgreSQL?)
3. **In-memory review cycle tracking** - should be in DB
4. **No graceful shutdown** - can lose in-progress work
5. **No concurrent execution** - only 1 Rock at a time
6. **Hard-coded paths** - need dynamic workspace management

### Medium Priority
7. **Logging not structured** - hard to parse/analyze
8. **No rate limiting** on tool calls - can spam APIs
9. **No timeout on agent turns** - can hang forever
10. **Secret management** - .env is good but not encrypted
11. **No model switching** - stuck with one LLM per session
12. **Poor error messages** - hard to debug for users

### Low Priority (Post v1.0)
13. **No plugin system** - can't extend easily
14. **No A/B testing** - can't compare agent strategies
15. **No analytics** - don't know what works
16. **No cost tracking** - don't know LLM costs
17. **No team features** - single-user only

---

## 📚 Documentation Gaps

### Missing Docs
- [ ] Architecture deep dive (how everything connects)
- [ ] Agent development guide (how to add new roles)
- [ ] Tool development guide (how to add new tools)
- [ ] State machine guide (valid transitions, when to use what)
- [ ] Troubleshooting guide (common errors + solutions)
- [ ] Performance tuning guide
- [ ] Security hardening guide

### Outdated Docs
- [ ] ARCHITECTURE.md (doesn't mention sandboxes)
- [ ] examples.md (old syntax)
- [ ] Some references to "Skills" (merged into Roles)

---

## 🎯 Post-UI Revamp (v1.1+)

**Features for later**:
- Multi-model support (switch LLM mid-session)
- Cost optimization (use cheaper models for simple tasks)
- Agent learning (save successful patterns)
- Template marketplace (share project templates)
- Cloud deployment (deploy sandboxes to VPS/cloud)
- Real-time collaboration (multiple users watching same session)
- Mobile app (monitor projects on phone)

---

## 📖 References

- [PROJECT.md](PROJECT.md) - Project overview
- [CHANGELOG.md](../CHANGELOG.md) - Version history
- [PHASE3_INTEGRATION.md](PHASE3_INTEGRATION.md) - Phase 3 details
- [ARCHITECTURE.md](ARCHITECTURE.md) - System design
- [PR_REVIEW_POLICY.md](PR_REVIEW_POLICY.md) - Review workflow
