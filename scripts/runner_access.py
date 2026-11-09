"""Obtain a short-lived credential for this workflow's callbacks."""
import json
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
    req = urllib.request.Request(os.environ["API_URL"].rstrip("/") + "/runner",
        data=json.dumps({"event": "next", "run": run}).encode(),
        headers={"Authorization": "Bearer " + credential(), "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as response:
        result = json.load(response)
    if result.get("task"):
        import uuid
        with open(os.environ["GITHUB_OUTPUT"], "a") as output:
            print("task=" + str(uuid.UUID(result["task"])), file=output)
            print("attempt=" + str(int(result["attempt"])), file=output)
        print("Approved task available.")
    else:
        print("Queue checked. No approved task is waiting.")
