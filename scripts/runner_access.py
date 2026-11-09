"""Obtain a short-lived credential for this workflow's callbacks."""
import base64
import json
import urllib.error
import os
import urllib.parse
import urllib.request


def credential():
    if os.environ.get("RUNNER_KEY"):
        return os.environ["RUNNER_KEY"]
    url = os.environ["ACTIONS_ID_TOKEN_REQUEST_URL"]
    audience = os.environ["API_URL"].rstrip("/")
    url += ("&" if "?" in url else "?") + urllib.parse.urlencode({"audience": audience})
    req = urllib.request.Request(url, headers={
        "Authorization": "Bearer " + os.environ["ACTIONS_ID_TOKEN_REQUEST_TOKEN"]})
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.load(response)["value"]


if __name__ == "__main__":
    run = os.environ["GITHUB_RUN_ID"] + "." + os.environ["GITHUB_RUN_ATTEMPT"]
    token = credential()
    if token.count(".") == 2:
        encoded = token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        print("Runner identity:", {key: claims.get(key) for key in (
            "iss", "aud", "repository", "repository_id", "ref", "event_name", "workflow_ref", "run_id", "run_attempt")})
    req = urllib.request.Request(os.environ["API_URL"].rstrip("/") + "/runner",
        data=json.dumps({"event": "next", "run": run}).encode(),
        headers={"User-Agent": "mcm-study-hub/1", "Authorization": "Bearer " + token, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        print("Queue HTTP", exc.code, exc.read(500).decode(errors="replace"))
        raise
    if result.get("task"):
        import uuid
        with open(os.environ["GITHUB_OUTPUT"], "a") as output:
            print("task=" + str(uuid.UUID(result["task"])), file=output)
            print("attempt=" + str(int(result["attempt"])), file=output)
        print("Approved task available.")
    else:
        print("Queue checked. No approved task is waiting.")
