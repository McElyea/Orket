async def orchestrate(
    epic_name: str,
    workspace: Path,
    department: str = "core",
    task_override: Optional[str] = None,
    extra_references: List[str] = None,
    session_id: str = None,
    build_id: str = None,
    model_override: str = None,
    interactive_conductor: bool = False,
    driver_steered: bool = False,
    target_issue_id: str = None
) -> Any:
    workspace.mkdir(parents=True, exist_ok=True)
    loader = ConfigLoader(Path("model").resolve(), department)
    epic = loader.load_asset("epics", epic_name, EpicConfig)
    team = loader.load_asset("teams", epic.team, TeamConfig)
    
    # Allow model override
    env = loader.load_asset("environments", epic.environment, EnvironmentConfig)
    if model_override:
        env.model = model_override
    
    final_task = task_override or epic.example_task or "No objective."
    all_refs = epic.references + (extra_references or [])
    
    # Unique Session for Audit, Stable Build for Reuse
    run_id = session_id or str(uuid.uuid4())[:8]
    active_build = build_id or f"build-{sanitize_name(epic_name)}"

    # --- POPULATE BACKLOG ---
    from orket.persistence import PersistenceManager
    db = PersistenceManager()
    current_sprint = get_eos_sprint()
    
    # Check for existing issues in this build
    existing = db.get_build_issues(active_build)
    if len(existing) > 0:
        print(f"  [REUSE] Build '{active_build}' found. Flipping {len(existing)} tasks back to READY.")
        db.reset_build_issues(active_build)
    
    # Ensure epic issues are registered to the build
    for i in epic.issues:
        if not any(ex["summary"] == i.summary for ex in existing):
            db.add_issue(run_id, i.seat, i.summary, i.type, i.priority, current_sprint, i.note, build_id=active_build)

    log_event("session_start", {"epic": epic.name, "run_id": run_id, "build_id": active_build}, workspace=workspace)
    
    policy = create_session_policy(str(workspace), all_refs)
    toolbox = ToolBox(policy, str(workspace), all_refs)
    tool_map = get_tool_map(toolbox)
    provider = LocalModelProvider(
        model=env.model, 
        temperature=env.temperature, 
        seed=env.seed,
        timeout=env.timeout
    )

    transcript = []

    # --- TRACTION LOOP ---
    while True:
        # Get issues specifically for this build
        backlog = db.get_build_issues(active_build)
        ready = [i for i in backlog if i["status"] == "ready"]
        
        # --- STANDALONE CARD FILTER ---
        if target_issue_id:
            ready = [i for i in ready if i["id"] == target_issue_id]

        if not ready: break
            
        issue = ready[0]
        issue_id, seat_name = issue["id"], issue["seat"]
        
        # --- DRIVER STEERING ---
        prompt_patch = None
        if driver_steered:
            print(f"  [STEERING] Consulting Driver for turn {len(transcript)}...")
            from orket.driver import OrketDriver
            driver = OrketDriver()
            
            steering_msg = f"Current state of epic '{epic_name}': {len(transcript)} steps completed. Next planned member is '{seat_name}'. Task: '{issue['summary']}'. Provide a tactical directive or prompt patch for this turn."
            steering_res = await driver.process_request(steering_msg)
            
            log_event("driver_steering", {"insight": steering_res}, workspace, role="DRIVER")
            prompt_patch = f"DRIVER DIRECTIVE: {steering_res}"

        db.update_issue_status(issue_id, "in_progress", assignee=seat_name)
        
        seat = team.seats.get(sanitize_name(seat_name))
        if not seat:
            db.update_issue_status(issue_id, "blocked")
            continue

        desc = f"Seat: {seat_name}.
ISSUE: {issue['summary']}
"
        desc += "MANDATORY: Use 'write_file' to persist work. One Issue, One Member.
"
        
        # --- WARM HANDOFF PEAK ---
        next_member = None
        if len(ready) > 1:
            next_member = ready[1]["seat"]

        tools = {}
        for r_name in seat.roles:
            role = team.roles.get(r_name)
            if role:
                desc += f"
Role {role.name}: {role.description}
"
                for tn in role.tools:
                    if tn in tool_map: tools[tn] = tool_map[tn]

        print(f"  [TRACTION] {seat_name} -> {issue_id}")
        agent = Agent(seat_name, desc, tools, provider, next_member=next_member, prompt_patch=prompt_patch)
        
        # Manual Conduct Mode
        if interactive_conductor:
            print(f"
[CONDUCTOR] Issue {issue_id} starting. Press Enter to proceed or 's' to skip...")
            cmd = input().strip().lower()
            if cmd == 's':
                db.update_issue_status(issue_id, "blocked")
                continue

        response = await agent.run(
            task={"description": f"{final_task}

Task: {issue['summary']}"},
            context={"session_id": run_id, "issue_id": issue_id, "workspace": str(workspace), "role": seat_name, "step_index": len(transcript)},
            workspace=workspace,
            transcript=transcript
        )
        
        # --- RECORD CREDITS ---
        usage = getattr(response, "usage", {})
        total_tokens = usage.get("total_tokens") or 0
        if total_tokens > 0:
            credits_to_add = (total_tokens / 1000.0) * 0.01
            db.add_credits(issue_id, credits_to_add)
            log_event("credit_charge", {"issue": issue_id, "tokens": total_tokens, "credits": credits_to_add}, workspace, role="SYS")

        # Check current status in DB before auto-finalizing
        current_issue = [i for i in db.get_session_issues(run_id) if i["id"] == issue_id][0]
        if current_issue["status"] == "in_progress":
            db.update_issue_status(issue_id, "done")
            
        transcript.append({
            "step_index": len(transcript),
            "role": seat_name, 
            "issue": issue_id, 
            "summary": response.content
        })

        # --- HANDSHAKE ROUND (Q&A) ---
        if epic.handshake_enabled and next_member and next_member != seat_name:
            print(f"  [HANDSHAKE] {next_member} reviewing work from {seat_name}...")
            
            # 1. Next Agent asks questions
            next_agent = Agent(next_member, f"Handoff Reviewer from {seat_name}", {}, provider)
            
            interrogation_task = {
                "description": f"You are receiving a handoff from {seat_name}. Review their final response and memo. Do you have any clarifying questions before you begin your task? If yes, list them clearly. If no, respond exactly with 'READY'."
            }
            
            questions = await next_agent.run(
                task=interrogation_task,
                context={"session_id": run_id, "role": next_member, "handoff_from": seat_name},
                workspace=workspace,
                transcript=transcript
            )
            
            if "READY" not in questions.content.upper():
                log_event("handshake_query", {"from": next_member, "to": seat_name, "questions": questions.content}, workspace, role="SYS")
                
                # 2. Original Agent answers
                print(f"  [HANDSHAKE] {seat_name} answering clarifications for {next_member}...")
                clarification_task = {
                    "description": f"The '{next_member}' has the following questions about your handoff: {questions.content}

Please provide a concise clarification to ensure they can proceed."
                }
                
                answers = await agent.run(
                    task=clarification_task,
                    context={"session_id": run_id, "role": seat_name, "handoff_to": next_member},
                    workspace=workspace,
                    transcript=transcript
                )
                
                log_event("handshake_clarified", {"from": seat_name, "to": next_member, "answers": answers.content}, workspace, role="SYS")
                
                transcript.append({
                    "step_index": f"{len(transcript)-1}.1",
                    "role": "HANDSHAKE",
                    "summary": f"Q: {questions.content}
A: {answers.content}"
                })

    log_event("session_end", {"run_id": run_id}, workspace=workspace)
    return transcript
