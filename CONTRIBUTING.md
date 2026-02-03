# Contributing to Orket

Thank you for your interest in contributing. This document explains how to work on the project.

## Development Setup

Clone the repository:

git clone <repo-url>

Install dependencies:

pip install -r requirements.txt

Run Orket:

python main.py --venue standard

## Adding a New Band

1. Create a file in bands/  
2. Define roles, prompts, and tools_allowed  
3. Ensure role names match Score references  

## Adding a New Score

1. Create a file in scores/  
2. Define included_roles  
3. Define dependencies  
4. Define completion rules  

## Adding a New Venue

1. Create a file in venues/  
2. Reference a Band  
3. Reference a Score  
4. Configure filesystem policy  

## Adding a New Tool

1. Implement the tool  
2. Register it in the dispatcher  
3. Add it to tools_allowed for relevant roles  

## Coding Standards

- explicit imports  
- no hidden behavior  
- deterministic orchestration  
- copy‑paste‑friendly Markdown  
- no duplication across docs  

## Documentation Standards

- each file has a single purpose  
- no overlap  

## Pull Requests

PRs should include:

- clear description  
- tests if applicable  
- updated docs if needed  
- no unrelated changes  