# Orket

Orket is a local‑first, multi‑agent automation platform for engineering work. It uses a musical metaphor to make complex orchestration explicit, inspectable, and contributor‑friendly.

Orket is not a chatbot wrapper. It is a conductor for deterministic, config‑driven workflows.

## The Orket Model

Orket organizes work using a musical architecture:

Orket (the conductor)  
→ Venue (the environment)  
→ Band (the performers)  
→ Score (the composition)  
→ Prelude (optional warm‑up)  
→ Session (the performance)

### Venue  
Defines the environment: filesystem policy, tempo, Band, Score.

### Band  
Defines the agents: roles, prompts, allowed tools.

### Score  
Defines orchestration: dependencies, sequencing, completion rules.

### Prelude  
Optional warm‑up stage before the Session.

### Session  
A structured record of a single run.

## Quickstart

Install dependencies:

pip install -r requirements.txt

Run Orket:

python main.py --venue standard

You will be prompted for a task. Orket will load the Venue, assemble the Band, follow the Score, optionally run a Prelude, and execute a Session.

## CLI Options

--venue <name>       Select a venue (default: standard)  
--max-rounds <n>     Limit orchestration rounds (default: 20)  
--no-prelude         Disable the Prelude stage  

Example:

python main.py --venue standard --max-rounds 30

## Documentation

Architecture: ARCHITECTURE.md  
Security Model: SECURITY.md  
Contributing: CONTRIBUTING.md  
Project Roadmap: PROJECT.md

## Philosophy

Orket is built around:

- determinism  
- explicit configuration  
- local‑first execution  
- strong separation of concerns  
- contributor‑friendly design  

Every config, role, and flow is meant to be readable, copy‑pasteable, and auditable.