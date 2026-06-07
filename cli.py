import argparse
import json
import time
import sys
import urllib.request
import urllib.error

# ANSI Color codes
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
UNDERLINE = "\033[4m"
END = "\033[0m"


def request_api(url, method="GET", headers=None, data=None):
    if headers is None:
        headers = {}
    req = urllib.request.Request(url, headers=headers, method=method)
    if data is not None:
        req.data = json.dumps(data).encode("utf-8")
        req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req) as res:
            return res.status, json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            err_body = json.loads(e.read().decode("utf-8"))
            detail = err_body.get("detail", str(e))
        except Exception:
            detail = str(e)
        print(f"{RED}{BOLD}API Error ({e.code}):{END} {detail}")
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"{RED}{BOLD}Connection Error:{END} {e.reason}")
        sys.exit(1)


def submit_job(base_url, api_key, query, max_rounds, provider=None, base_url_override=None, model=None):
    url = f"{base_url.rstrip('/')}/v1/research"
    headers = {"Authorization": f"Bearer {api_key}"}
    data = {"query": query, "max_rounds": max_rounds}
    if provider:
        data["provider"] = provider
    if base_url_override:
        data["base_url"] = base_url_override
    if model:
        data["model"] = model

    print(f"\n{BLUE}{BOLD}Submitting research job...{END}")
    status, response = request_api(url, method="POST", headers=headers, data=data)
    if status == 202:
        job_id = response.get("id")
        print(f"{GREEN}✔ Job submitted successfully!{END} Job ID: {BOLD}{job_id}{END}")
        return job_id
    else:
        print(f"{RED}Submission failed with status {status}{END}")
        sys.exit(1)


def poll_job(base_url, api_key, job_id):
    url = f"{base_url.rstrip('/')}/v1/research/{job_id}"
    headers = {"Authorization": f"Bearer {api_key}"}

    print(f"\n{BLUE}{BOLD}Tracking research progress...{END}")
    spinner = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    idx = 0

    while True:
        status, response = request_api(url, method="GET", headers=headers)
        job_status = response.get("status")

        if job_status == "completed":
            print(f"\r{GREEN}✔ Research completed successfully!{END}              ")
            return response
        elif job_status == "failed":
            print(f"\r{RED}✘ Research job failed!{END}                      ")
            print(f"{RED}Error:{END} {response.get('error')}")
            sys.exit(1)
        elif job_status == "cancelled":
            print(f"\r{YELLOW}⚠ Research job was cancelled.{END}             ")
            sys.exit(0)

        # Print progress
        sys.stdout.write(f"\r{YELLOW}{spinner[idx]} Status: {BOLD}{job_status}{END}...{END}")
        sys.stdout.flush()
        idx = (idx + 1) % len(spinner)
        time.sleep(1)


def main():
    parser = argparse.ArgumentParser(description="Deep Research API Developer CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    submit_parser = subparsers.add_parser("submit", help="Submit a new research job")
    submit_parser.add_argument("query", type=str, help="The research question/query")
    submit_parser.add_argument("--max-rounds", type=int, default=3, help="Max iterations of research (1-5)")
    submit_parser.add_argument("--api-key", type=str, required=True, help="API Key for authorization")
    submit_parser.add_argument("--api-url", type=str, default="http://localhost:8000", help="Base URL of the Deep Research API")
    submit_parser.add_argument("--output", type=str, default=None, help="Save the output markdown report to a file")
    submit_parser.add_argument("--provider", type=str, default=None, help="Optional LLM provider override")
    submit_parser.add_argument("--base-url", type=str, default=None, help="Optional LLM base URL override")
    submit_parser.add_argument("--model", type=str, default=None, help="Optional LLM model override")

    args = parser.parse_args()

    if args.command == "submit":
        job_id = submit_job(
            args.api_url,
            args.api_key,
            args.query,
            args.max_rounds,
            provider=args.provider,
            base_url_override=args.base_url,
            model=args.model
        )
        result = poll_job(args.api_url, args.api_key, job_id)

        report = result.get("report", {})
        summary = report.get("summary", "")
        body_md = report.get("body_md", "")
        citations = report.get("citations", [])

        print(f"\n{BOLD}{UNDERLINE}SUMMARY:{END}\n{summary}\n")
        print(f"{BOLD}{UNDERLINE}REPORT OUTLINE:{END}\n")

        for line in body_md.splitlines():
            if line.startswith("#"):
                print(f"{BLUE}{BOLD}{line}{END}")
            elif line.startswith("-") or line.startswith("*"):
                print(f"  {line}")
            else:
                print(line)

        if citations:
            print(f"\n{BOLD}{UNDERLINE}CITED SOURCES:{END}")
            for idx, cit in enumerate(citations, 1):
                print(f"[{idx}] {GREEN}{cit}{END}")

        if args.output:
            try:
                with open(args.output, "w", encoding="utf-8") as f:
                    f.write(body_md)
                print(f"\n{GREEN}✔ Report saved to {args.output}{END}")
            except Exception as e:
                print(f"{RED}Error saving report: {e}{END}")


if __name__ == "__main__":
    main()
