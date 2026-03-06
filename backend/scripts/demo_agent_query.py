#!/usr/bin/env python3
"""
Demo: Use the agentic endpoint to submit a natural language media processing request.

Usage:
    python -m scripts.demo_agent_query --instruction "downscale to 480p then extract audio" --video sample.mp4
"""

import argparse
import time

import httpx

GATEWAY = "http://localhost:8000"


def main():
    parser = argparse.ArgumentParser(description="Demo agent-driven pipeline")
    parser.add_argument("--instruction", required=True, help="Natural language instruction")
    parser.add_argument("--video", required=True, help="Path to video file")
    parser.add_argument("--subtitle", default=None, help="Optional .srt file")
    parser.add_argument("--plan-only", action="store_true", help="Only show the plan, don't execute")
    args = parser.parse_args()

    if args.plan_only:
        print(f"Planning: '{args.instruction}'")
        resp = httpx.post(
            f"{GATEWAY}/api/v1/agent/plan",
            json={"instruction": args.instruction},
            timeout=30,
        )
        resp.raise_for_status()
        plan = resp.json()
        print(f"\nExecution Plan ({len(plan['steps'])} steps):")
        for step in plan["steps"]:
            dep = f" (depends on step {step['depends_on']})" if step.get("depends_on") is not None else ""
            print(f"  Step {step['step_index']}: {step['job_type']}{dep}")
        print(f"\nEstimated duration: ~{plan.get('estimated_duration_seconds', '?')}s")
        return

    print(f"Executing: '{args.instruction}'")

    files = {"video": open(args.video, "rb")}
    if args.subtitle:
        files["subtitle"] = open(args.subtitle, "rb")

    resp = httpx.post(
        f"{GATEWAY}/api/v1/agent/execute",
        data={"instruction": args.instruction},
        files=files,
        timeout=60,
    )

    for f in files.values():
        f.close()

    resp.raise_for_status()
    result = resp.json()
    pipeline_id = result["pipeline_id"]
    print(f"Pipeline created: {pipeline_id}")
    print(f"Jobs: {result['job_ids']}")

    print("\nPolling pipeline jobs...")
    for job_id in result["job_ids"]:
        while True:
            r = httpx.get(f"{GATEWAY}/api/v1/jobs/{job_id}", timeout=10)
            data = r.json()
            status = data["status"]
            step = data.get("pipeline_step", "?")
            print(f"  Step {step} [{status}] progress={data['progress']}%")
            if status in ("completed", "failed", "dead_letter"):
                break
            time.sleep(3)

    last_job_id = result["job_ids"][-1]
    r = httpx.get(f"{GATEWAY}/api/v1/jobs/{last_job_id}", timeout=10)
    if r.json()["status"] == "completed":
        out = httpx.get(f"{GATEWAY}/api/v1/jobs/{last_job_id}/output", timeout=10)
        print(f"\nFinal output: {out.json()['download_url']}")
    else:
        print(f"\nPipeline did not complete successfully.")


if __name__ == "__main__":
    main()
