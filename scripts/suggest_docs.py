import os
import subprocess
import argparse
from pathlib import Path
from google import genai
from google.genai import types

# === CONFIG ===
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
DOCS_REPO_URL = os.environ["DOCS_REPO_URL"]
BRANCH_NAME = "doc-update-from-pr"

def get_diff():
    result = subprocess.run(["git", "diff", "origin/main...HEAD"], capture_output=True, text=True)
    return result.stdout.strip()

def clone_docs_repo():
    subprocess.run(["git", "clone", DOCS_REPO_URL, "docs_repo"])
    os.chdir("docs_repo")

    # Try to check out the branch if it already exists
    result = subprocess.run(["git", "ls-remote", "--heads", "origin", BRANCH_NAME], capture_output=True, text=True)
    if result.stdout.strip():
        print(f"Reusing existing branch: {BRANCH_NAME}")
        subprocess.run(["git", "fetch", "origin", BRANCH_NAME])
        subprocess.run(["git", "checkout", BRANCH_NAME])
        subprocess.run(["git", "pull", "origin", BRANCH_NAME])
    else:
        print(f"Creating new branch: {BRANCH_NAME}")
        subprocess.run(["git", "checkout", "-b", BRANCH_NAME])


def get_file_previews():
    previews = []
    adoc_files = list(Path(".").rglob("*.adoc"))
    for path in adoc_files:
        try:
            with open(path, encoding="utf-8") as f:
                lines = f.readlines()[:10]  # Get first 10 lines (or fewer if file is short)
                first_lines = "".join(lines)
                previews.append((str(path), first_lines.strip()))
        except Exception as e:
            print(f"Skipping file {path}: {e}")
    return previews

def ask_gemini_for_relevant_files(diff, file_previews):
    context = "\n\n".join(
        [f"File: {fname}\nPreview:\n{preview}" for fname, preview in file_previews]
    )

    prompt = f"""
You are a documentation assistant.

A code change was made in this PR (Git diff):
{diff}

Below is a list of .adoc documentation files and a preview of their content:

{context}

Based on the diff, which files from this list should be updated? Return only the file paths (one per line). No explanations or extra formatting.
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_budget=0)
        ),
    )
    return [line.strip() for line in response.text.strip().splitlines() if line.strip()]

def load_full_content(file_path):
    try:
        return Path(file_path).read_text(encoding="utf-8")
    except Exception as e:
        print(f"Failed to read {file_path}: {e}")
        return ""

def ask_gemini_for_updated_content(diff, file_path, current_content):
    prompt = f"""
You are a documentation assistant.

CRITICAL FORMATTING REQUIREMENTS FOR ASCIIDOC FILES:
- NEVER use markdown code fences like ```adoc or ``` anywhere in the file
- AsciiDoc files start directly with content (comments, headers, or text)  
- Use ONLY AsciiDoc syntax: ==== for headers, |=== for tables, ---- for code blocks
- Do NOT mix markdown and AsciiDoc syntax
- Maintain proper table structures with matching |=== opening and closing
- Keep all cross-references (xref) intact and properly formatted
- Ensure consistent indentation and spacing

A developer made the following code changes:
{diff}

Here is the full content of the current documentation file `{file_path}`:
--------------------
{current_content}
--------------------

Analyze the diff and check whether **new, important information** is introduced that is not already covered in this file.

- If the file already includes everything important, return exactly: `NO_UPDATE_NEEDED`
- If the file is missing key information, return the **full updated file content**, modifying only what is necessary. in valid AsciiDoc format

VALIDATION CHECKLIST - Before responding, verify:
1. No markdown code fences (```) anywhere in the content
2. All tables have matching |=== opening and closing
3. All section headers use correct ==== syntax  
4. All cross-references are properly formatted
5. No broken formatting or incomplete structures

Do not explain or summarize — only return either:
- `NO_UPDATE_NEEDED` (if nothing is missing), or
- The full updated AsciiDoc file content with perfect syntax (NO markdown!)
"""


    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_budget=0)
        ),
    )
    return response.text.strip()

def overwrite_file(file_path, new_content):
    try:
        Path(file_path).write_text(new_content, encoding="utf-8")
        return True
    except Exception as e:
        print(f"Failed to write {file_path}: {e}")
        return False

def push_and_open_pr(modified_files):
    subprocess.run(["git", "add"] + modified_files)
    subprocess.run([
        "git", "commit",
        "-m", "Auto-generated doc updates from code PR\n\nAssisted-by: Gemini"
    ])
    # Add remote with token auth
    gh_token = os.environ["GH_TOKEN"]
    docs_repo_url = DOCS_REPO_URL.replace("https://", f"https://{gh_token}@")

    subprocess.run(["git", "remote", "set-url", "origin", docs_repo_url])
    subprocess.run(["git", "push", "--set-upstream", "origin", BRANCH_NAME, "--force"])

    subprocess.run([
        "gh", "pr", "create",
        "--title", "Auto-Generated Doc Updates from Code PR",
        "--body", f"This PR updates the following documentation files based on the code changes:\n\n" +
                  "\n".join([f"- `{f}`" for f in modified_files]),
        "--base", "main",
        "--head", BRANCH_NAME
    ])

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Simulate changes without writing files or pushing PR")
    args = parser.parse_args()

    diff = get_diff()
    if not diff:
        print("No changes detected.")
        return

    clone_docs_repo()
    previews = get_file_previews()

    print("Asking Gemini for relevant files...")
    relevant_files = ask_gemini_for_relevant_files(diff, previews)
    if not relevant_files:
        print("Gemini did not suggest any files.")
        return

    print("Files selected by Gemini:", relevant_files)

    modified_files = []
    for file_path in relevant_files:
        current = load_full_content(file_path)
        if not current:
            continue

        print(f"Checking if {file_path} needs an update...")
        updated = ask_gemini_for_updated_content(diff, file_path, current)

        if updated.strip() == "NO_UPDATE_NEEDED":
            print(f"No update needed for {file_path}")
            continue

        if args.dry_run:
            print(f"[Dry Run] Would update {file_path} with:\n{updated}\n")
        else:
            print(f"Updating {file_path}...")
            if overwrite_file(file_path, updated):
                modified_files.append(file_path)

    if modified_files:
        if args.dry_run:
            print("[Dry Run] Would push and open PR for the following files:")
            for f in modified_files:
                print(f"- {f}")
        else:
            push_and_open_pr(modified_files)
    else:
        print("All documentation is already up to date — no PR created.")

if __name__ == "__main__":
    main()
