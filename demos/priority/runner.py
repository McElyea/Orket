#!/usr/bin/env python3
"""
Priority Demo Runner
Executes the decomposed priority scenarios.
"""
from demos.priority.scenarios import run_basic_scenario, run_dependency_scenario

def main():
    print("\n" + "="*60)
    print("  >> Orket Priority System Test Drive")
    print("="*60)

    run_basic_scenario()
    run_dependency_scenario()

    print("\n" + "="*60)
    print("  >> Test Drive Complete!")
    print("="*60)

if __name__ == "__main__":
    main()
