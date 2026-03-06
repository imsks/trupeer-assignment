#!/usr/bin/env python3
"""
Demo: Submit an overlay job (burn subtitles into video).

Usage:
    python -m scripts.demo_submit_overlay --video sample.mp4 --subtitle sample.srt
"""

import argparse
import time

import httpx

GATEWAY = "http://localhost:8000"


def main():
    parser = argparse.ArgumentParser(description="Submit overlay job")
    parser.add_argument("--video", required=True, help="Path to video file")
    parser.add_argument("--subtitle", required=True, help="Path to .srt file")
    args = parser.parse_args()

    print(f"Submitting overlay job: video={args.video}, subtitle={args.subtitle}")

    with open(args.video, "rb") as vf, open(args.subtitle, "rb") as sf:
        resp = httpx.post(
            f"{GATEWAY}/api/v1/jobs",
            data={"job_type": "overlay"},
            files={"video": vf, "subtitle": sf},
            timeout=30,
        )

    resp.raise_for_status()
    job = resp.json()
    job_id = job["id"]
    print(f"Job created: {job_id} (status: {job['status']})")

    print("Polling for completion...")
    while True:
        r = httpx.get(f"{GATEWAY}/api/v1/jobs/{job_id}", timeout=10)
        data = r.json()
        status = data["status"]
        progress = data["progress"]
        print(f"  [{status}] progress={progress}%")
        if status in ("completed", "failed", "dead_letter"):
            break
        time.sleep(3)

    if status == "completed":
        r = httpx.get(f"{GATEWAY}/api/v1/jobs/{job_id}/output", timeout=10)
        print(f"Download URL: {r.json()['download_url']}")
    else:
        print(f"Job failed: {data.get('error', 'unknown')}")


if __name__ == "__main__":
    main()
