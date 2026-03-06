#!/usr/bin/env python3
"""
Demo: Submit a transcode job (downscale to 480p).

Usage:
    python -m scripts.demo_submit_transcode --video sample.mp4
"""

import argparse
import time

import httpx

GATEWAY = "http://localhost:8000"


def main():
    parser = argparse.ArgumentParser(description="Submit transcode job")
    parser.add_argument("--video", required=True, help="Path to video file")
    args = parser.parse_args()

    print(f"Submitting transcode job: video={args.video}")

    with open(args.video, "rb") as vf:
        resp = httpx.post(
            f"{GATEWAY}/api/v1/jobs",
            data={"job_type": "transcode"},
            files={"video": vf},
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
