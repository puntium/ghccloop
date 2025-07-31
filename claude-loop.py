#!/usr/bin/env python3
"""
Claude Manager - Manages Claude instances through GitHub issues workflow
"""

import uuid
import json
import subprocess
import time
from datetime import datetime


class ClaudeSession:
    """Manages Claude session state across multiple invocations."""
    
    def __init__(self):
        self.session_id = None
        self.claude_path = "/home/ken/.claude/local/claude"
    
    def invoke_claude(self, prompt, permission_mode="acceptEdits"):
        """
        Invoke Claude with automatic session management.
        
        Args:
            prompt: The prompt/command to run in Claude
            permission_mode: Permission mode for Claude (default: "acceptEdits")
            
        Returns:
            dict: Response data including result, session_id, etc. or None if error
        """
        try:
            cmd = [
                self.claude_path,
                "-p",
                "--output-format", "json",
                "--permission-mode", permission_mode,
            ]
            
            # Use --resume if we have a session_id, otherwise start fresh
            if self.session_id:
                cmd.extend(["--resume", self.session_id])
                print(f"Resuming Claude session: {self.session_id}")
            else:
                print("Starting new Claude session")
            
            cmd.append(prompt)
            print(f"Running prompt: {prompt}")
            
            # Run Claude command
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                try:
                    response = json.loads(result.stdout)
                    
                    # Update session_id for next invocation
                    if "session_id" in response:
                        self.session_id = response["session_id"]
                        print(f"Session ID updated: {self.session_id}")
                    
                    # Print the result
                    if "result" in response:
                        print("\n--- Claude Output ---")
                        print(response["result"])
                        print("--- End Claude Output ---\n")
                    
                    return response
                    
                except json.JSONDecodeError as e:
                    print(f"Error parsing JSON response: {e}")
                    print(f"Raw output: {result.stdout}")
                    return None
            else:
                print(f"Claude invocation failed with return code: {result.returncode}")
                if result.stderr:
                    print(f"Error: {result.stderr}")
                return None
                
        except subprocess.CalledProcessError as e:
            print(f"Error invoking Claude: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error: {e}")
            return None


def create_session_uuid():
    """Generate a unique UUID for a Claude code session."""
    return str(uuid.uuid4())


def find_next_issue():
    """
    Find the first open issue that doesn't have 'dev-acked', 'dev-ready',
    or 'planning-acked' labels.

    Returns:
        dict: Issue data with number, title, labels, etc. or None if no issue found
    """
    try:
        # Get all open issues with their labels
        cmd = [
            "gh",
            "issue",
            "list",
            "--state",
            "open",
            "--json",
            "number,title,labels,url",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        issues = json.loads(result.stdout)

        excluded_labels = {"dev-acked", "dev-ready", "planning-acked"}

        for issue in issues:
            # Get label names from the issue
            issue_labels = {label["name"] for label in issue.get("labels", [])}

            # Check if issue has any of the excluded labels
            if not issue_labels.intersection(excluded_labels):
                return issue

        return None

    except subprocess.CalledProcessError as e:
        print(f"Error calling gh CLI: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON response: {e}")
        return None


def get_issue_last_updated(issue_number):
    """
    Get the last updated timestamp for a specific issue.
    
    Args:
        issue_number: The GitHub issue number
        
    Returns:
        datetime: The last updated timestamp or None if error
    """
    try:
        cmd = [
            "gh",
            "issue",
            "view",
            str(issue_number),
            "--json",
            "updatedAt",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        data = json.loads(result.stdout)
        updated_at = data.get("updatedAt")
        
        if updated_at:
            # Parse ISO format timestamp
            return datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        
        return None
        
    except subprocess.CalledProcessError as e:
        print(f"Error getting issue update time: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON response: {e}")
        return None


def issue_has_label(issue_number, label_name):
    """
    Check if an issue has a specific label.
    
    Args:
        issue_number: The GitHub issue number
        label_name: The label name to check for
        
    Returns:
        bool: True if issue has the label, False otherwise
    """
    try:
        cmd = [
            "gh",
            "issue",
            "view",
            str(issue_number),
            "--json",
            "labels",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        data = json.loads(result.stdout)
        labels = data.get("labels", [])
        
        # Check if label_name is in the issue's labels
        for label in labels:
            if label.get("name") == label_name:
                return True
        
        return False
        
    except subprocess.CalledProcessError as e:
        print(f"Error checking issue labels: {e}")
        return False
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON response: {e}")
        return False


def get_linked_pr_from_issue(issue_number):
    """
    Get linked pull requests from an issue using GitHub's timeline events.
    
    Args:
        issue_number: The GitHub issue number
        
    Returns:
        int: PR number or None if no linked PR found
    """
    try:
        # Use gh api to get timeline events which include linked PRs
        cmd = [
            "gh",
            "api",
            f"repos/:owner/:repo/issues/{issue_number}/timeline",
            "--paginate",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        events = json.loads(result.stdout)
        
        # Look for cross-referenced events that are pull requests
        for event in events:
            if event.get("event") == "cross-referenced" and event.get("source"):
                source = event["source"]
                if source.get("type") == "issue" and source.get("issue", {}).get("pull_request"):
                    pr_number = source["issue"]["number"]
                    print(f"Found linked PR #{pr_number}")
                    return pr_number
        
        return None
        
    except subprocess.CalledProcessError as e:
        print(f"Error getting linked PR: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON response: {e}")
        return None


def get_pr_last_activity(pr_number):
    """
    Get the most recent activity timestamp from a PR (including comments, reviews, and main conversation).
    
    Args:
        pr_number: The GitHub PR number
        
    Returns:
        datetime: The most recent activity timestamp or None if error
    """
    try:
        latest_timestamp = None
        
        # Get PR basic info including updatedAt
        cmd = [
            "gh",
            "pr",
            "view",
            str(pr_number),
            "--json",
            "updatedAt",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        
        if data.get("updatedAt"):
            latest_timestamp = datetime.fromisoformat(data["updatedAt"].replace("Z", "+00:00"))
        
        # Get PR comments
        cmd = [
            "gh",
            "api",
            f"repos/:owner/:repo/issues/{pr_number}/comments",
            "--paginate",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        comments = json.loads(result.stdout)
        
        for comment in comments:
            if comment.get("updated_at"):
                comment_time = datetime.fromisoformat(comment["updated_at"].replace("Z", "+00:00"))
                if not latest_timestamp or comment_time > latest_timestamp:
                    latest_timestamp = comment_time
        
        # Get PR reviews
        cmd = [
            "gh",
            "api",
            f"repos/:owner/:repo/pulls/{pr_number}/reviews",
            "--paginate",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        reviews = json.loads(result.stdout)
        
        for review in reviews:
            if review.get("submitted_at"):
                review_time = datetime.fromisoformat(review["submitted_at"].replace("Z", "+00:00"))
                if not latest_timestamp or review_time > latest_timestamp:
                    latest_timestamp = review_time
        
        # Get PR review comments
        cmd = [
            "gh",
            "api",
            f"repos/:owner/:repo/pulls/{pr_number}/comments",
            "--paginate",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        review_comments = json.loads(result.stdout)
        
        for comment in review_comments:
            if comment.get("updated_at"):
                comment_time = datetime.fromisoformat(comment["updated_at"].replace("Z", "+00:00"))
                if not latest_timestamp or comment_time > latest_timestamp:
                    latest_timestamp = comment_time
        
        return latest_timestamp
        
    except subprocess.CalledProcessError as e:
        print(f"Error getting PR activity: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON response: {e}")
        return None




def monitor_issue_for_updates(issue_number, claude_session, initial_timestamp):
    """
    Monitor an issue for updates and invoke /gdrevise when changes are detected.
    Exits when the issue has the "dev-ready" label.
    
    Args:
        issue_number: The GitHub issue number to monitor
        claude_session: The ClaudeSession instance
        initial_timestamp: The timestamp to compare against for updates
    """
    print(f"\nMonitoring issue #{issue_number} for updates...")
    print(f"Initial timestamp: {initial_timestamp}")
    print("Checking every 60 seconds. Press Ctrl+C to stop.")
    
    try:
        while True:
            time.sleep(60)  # Wait 1 minute
            
            # Check if issue has "dev-ready" label
            if issue_has_label(issue_number, "dev-ready"):
                print("\nIssue has 'dev-ready' label. Exiting monitoring loop.")
                break
            
            current_timestamp = get_issue_last_updated(issue_number)
            
            if current_timestamp and current_timestamp > initial_timestamp:
                print(f"\nUpdate detected at {current_timestamp}")
                print("Running /gdrevise command...")
                
                prompt = f"/gdrevise {issue_number}"
                response = claude_session.invoke_claude(prompt)
                
                if response and not response.get("is_error", True):
                    print("Successfully processed revision")
                    # Update the timestamp for continued monitoring
                    initial_timestamp = current_timestamp
                else:
                    print("Failed to process revision")
            else:
                print(f"No updates yet. Last check: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                
    except KeyboardInterrupt:
        print("\nMonitoring stopped by user")


def run_development_phase(issue_number):
    """
    Run the development phase after an issue becomes dev-ready.
    Creates a new Claude session, runs /gdev, and monitors for updates.
    
    Args:
        issue_number: The GitHub issue number
    """
    print(f"\n=== Starting Development Phase for Issue #{issue_number} ===")
    
    # Create new Claude session for development
    claude_session = ClaudeSession()
    
    # Run /gdev command to create initial PR
    prompt = f"/gdev {issue_number}"
    print(f"\nRunning initial development command: {prompt}")
    response = claude_session.invoke_claude(prompt)
    
    if not response or response.get("is_error", True):
        print("Failed to start development phase")
        return
    
    # Wait a bit for PR to be created
    print("\nWaiting for PR to be created...")
    time.sleep(10)
    
    # Get the linked PR number
    pr_number = get_linked_pr_from_issue(issue_number)
    if not pr_number:
        print("Warning: Could not find linked PR. Will monitor issue only.")
    
    # Get initial timestamps
    issue_timestamp = get_issue_last_updated(issue_number)
    pr_timestamp = get_pr_last_activity(pr_number) if pr_number else None
    
    # Track the latest timestamp between issue and PR
    latest_timestamp = issue_timestamp
    if pr_timestamp and (not latest_timestamp or pr_timestamp > latest_timestamp):
        latest_timestamp = pr_timestamp
    
    print(f"\nInitial timestamps:")
    print(f"  Issue: {issue_timestamp}")
    if pr_number:
        print(f"  PR #{pr_number}: {pr_timestamp}")
    
    # Monitor for updates until dev-complete
    monitor_development_updates(issue_number, pr_number, claude_session, latest_timestamp)


def monitor_development_updates(issue_number, pr_number, claude_session, initial_timestamp):
    """
    Monitor both issue and PR for updates during development phase.
    Exits when the issue has the "dev-complete" label.
    
    Args:
        issue_number: The GitHub issue number
        pr_number: The GitHub PR number (can be None)
        claude_session: The ClaudeSession instance
        initial_timestamp: The timestamp to compare against for updates
    """
    print(f"\nMonitoring issue #{issue_number} and PR #{pr_number if pr_number else 'N/A'} for updates...")
    print("Checking every 60 seconds. Press Ctrl+C to stop.")
    
    try:
        while True:
            time.sleep(60)  # Wait 1 minute
            
            # Check if issue has "dev-complete" label
            if issue_has_label(issue_number, "dev-complete"):
                print("\nIssue has 'dev-complete' label. Development phase finished!")
                break
            
            # Check for updates on both issue and PR
            issue_timestamp = get_issue_last_updated(issue_number)
            pr_timestamp = get_pr_last_activity(pr_number) if pr_number else None
            
            # Find the most recent update
            latest_timestamp = issue_timestamp
            update_source = "issue"
            
            if pr_timestamp and (not latest_timestamp or pr_timestamp > latest_timestamp):
                latest_timestamp = pr_timestamp
                update_source = "PR"
            
            if latest_timestamp and latest_timestamp > initial_timestamp:
                print(f"\nUpdate detected on {update_source} at {latest_timestamp}")
                print("Running /gdevrevise command...")
                
                prompt = f"/gdevrevise {issue_number}"
                response = claude_session.invoke_claude(prompt)
                
                if response and not response.get("is_error", True):
                    print("Successfully processed revision")
                    # Update the timestamp for continued monitoring
                    initial_timestamp = latest_timestamp
                else:
                    print("Failed to process revision")
            else:
                print(f"No updates yet. Last check: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                
    except KeyboardInterrupt:
        print("\nMonitoring stopped by user")


if __name__ == "__main__":
    # Create Claude session manager for planning phase
    claude_session = ClaudeSession()

    # Find next issue
    next_issue = find_next_issue()
    if next_issue:
        print(f"\nFound issue #{next_issue['number']}: {next_issue['title']}")
        print(f"URL: {next_issue['url']}")

        # === PLANNING PHASE ===
        print("\n=== Starting Planning Phase ===")
        
        # Construct the prompt and invoke Claude
        prompt = f"/gdr {next_issue['number']}"
        response = claude_session.invoke_claude(prompt)

        if response and not response.get("is_error", True):
            # Get initial timestamp after /gdr command
            initial_timestamp = get_issue_last_updated(next_issue['number'])
            
            if initial_timestamp:
                # Start monitoring for updates during planning phase
                monitor_issue_for_updates(next_issue['number'], claude_session, initial_timestamp)
                
                # === DEVELOPMENT PHASE ===
                # After planning phase exits (issue has dev-ready label), start development
                if issue_has_label(next_issue['number'], "dev-ready"):
                    run_development_phase(next_issue['number'])
            else:
                print("Failed to get issue timestamp for monitoring")
        else:
            print("Failed to process issue with Claude")
    else:
        print("\nNo eligible issues found")
