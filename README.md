# 🛠️ AI Coding Agent — Groq + Streamlit

An end-to-end AI Coding Agent that accepts a developer request in natural language, inspects a codebase, identifies relevant files, creates an implementation plan, proposes and applies code changes in a temporary workspace, validates the result with automated tests, attempts bounded repairs when needed, and presents the final changes and diff to the developer.

The application is built with **Python, Streamlit, and Groq**.

---

# 1. Project Overview

The goal of this project is to build a small but complete AI Coding Agent rather than a simple chatbot.

A developer can provide a request such as:

> Add input validation to `divide()` so that dividing by zero raises a clear `ValueError`, and add a meaningful test for that behavior.

The agent then performs the following workflow:


Natural-language task
        ↓
Task classification
        ↓
Repository discovery
        ↓
Baseline test collection
        ↓
LLM-based planning
        ↓
Relevant-file selection
        ↓
LLM-based implementation
        ↓
Safety checks
        ↓
Apply changes to temporary workspace
        ↓
Run tests / validation
        ↓
Repair failing changes if required
        ↓
Final safety validation
        ↓
Diff + explanation + modified project ZIP
```

The application does not directly modify the user's original project.

Uploaded projects and the bundled sample are processed inside a temporary workspace. The modified project can then be downloaded as a ZIP file.

---

# 2. Assignment Requirements Covered

This project is designed to cover the core requirements of the coding-agent assignment.

| Requirement | Implementation |
|---|---|
| Web UI or CLI | Streamlit web UI |
| Natural-language coding task | Developer enters task in a text area |
| Show agent plan | Planning stage displays summary, steps, relevant files, validation strategy and risks |
| Read multiple files | Repository discovery and file inspection |
| Identify relevant files | LLM planner selects relevant files from repository manifest |
| Understand coding request | Groq LLM interprets the developer task |
| Suggest/make code changes | LLM generates changes and the agent applies them |
| Explain changes | UI shows rationale and changed files |
| Show diff | Final unified diff is displayed |
| Validation | Pytest or compile validation |
| Meaningful test support | Agent can add/update tests when required |
| Local run instructions | Included in this README |
| Deployment | Streamlit Community Cloud supported |
| Assumptions | Documented below |
| Limitations | Documented below |

---

# 3. Main Features

## Natural-language coding requests

The developer does not need to provide a rigid command format.

Examples:


Add input validation to divide() and write a test for zero division.


Refactor the pricing function to improve readability without changing behavior.


Add a test covering 100% discount.


Inspect this repository and explain its architecture. Do not modify anything.


The natural-language request is passed to the Groq LLM and converted into a structured coding plan.

---

## Repository analysis

The agent can work with:

1. A bundled sample project
2. A user-uploaded ZIP project

The repository is indexed before the coding workflow begins.

The agent uses the repository manifest to understand:

- available files
- project structure
- implementation files
- test files
- configuration files
- dependencies
- relationships between files

---

## LLM-based planning

The planning stage does not immediately edit files.

The Groq model first creates a structured plan containing:

- task summary
- ordered implementation steps
- relevant existing files
- allowed new files
- test strategy
- risks

This makes the agent's reasoning process visible to the developer.

---

## Controlled implementation

The implementation stage receives:

- original developer request
- implementation plan
- selected relevant files
- current file contents
- baseline test information

The LLM then returns structured file changes.

The application validates the proposed changes before writing them.

---

## Automated validation

The agent validates the project after implementing the change.

When pytest-style tests exist, the agent runs:

```bash
python -m pytest -q
```

When pytest tests are not available, the agent falls back to:

```bash
python -m compileall -q .
```

The application also performs test-collection checks before and after the change.

---

## Bounded repair loop

A coding agent should not stop immediately after the first failed test.

When validation fails, the agent can attempt a limited repair cycle.

The current implementation allows:


Maximum repair rounds: 2

Each repair uses the actual validation output as feedback.

The agent is instructed to fix the root cause rather than guess.

---

## Diff generation

The application compares the modified temporary workspace against the original project state.

The final UI shows:

- changed files
- additions
- deletions
- unified diff
- validation output
- repair count
- final status

---

## Download modified project

After the workflow completes, the developer can download:


coding-agent-result.zip


The downloaded ZIP contains the modified project.

---

# 4. Architecture

The application follows a staged agent architecture.


                    ┌───────────────────────┐
                    │    Streamlit UI       │
                    │                       │
                    │ • Select project      │
                    │ • Enter task          │
                    │ • Run agent           │
                    └───────────┬───────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │   Task Classification │
                    │                       │
                    │ • Normal coding task  │
                    │ • Read-only request   │
                    │ • Dependency safety  │
                    │ • Intentional failure │
                    └───────────┬───────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │ Repository Discovery  │
                    │                       │
                    │ • Index files         │
                    │ • Ignore irrelevant  │
                    │   directories/files  │
                    └───────────┬───────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │ Baseline Validation  │
                    │                       │
                    │ • Collect tests      │
                    │ • Record baseline    │
                    └───────────┬───────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │   Groq LLM Planner    │
                    │                       │
                    │ • Understand task    │
                    │ • Select files       │
                    │ • Create steps       │
                    │ • Test strategy      │
                    └───────────┬───────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │ Groq Implementation   │
                    │                       │
                    │ • Read relevant files│
                    │ • Generate changes   │
                    │ • Generate tests     │
                    └───────────┬───────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │    Safety Gates       │
                    │                       │
                    │ • Approved paths     │
                    │ • Secret protection  │
                    │ • Fake package check │
                    │ • Destructive change │
                    │ • Test protection    │
                    └───────────┬───────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │ Apply to Temp Project │
                    └───────────┬───────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │ Validation / Tests    │
                    │                       │
                    │ • pytest              │
                    │ • compileall          │
                    └───────────┬───────────┘
                                │
                      ┌─────────┴─────────┐
                      │                   │
                   Passed              Failed
                      │                   │
                      │                   ▼
                      │         ┌─────────────────┐
                      │         │ Repair Loop     │
                      │         │ Max 2 attempts  │
                      │         └────────┬────────┘
                      │                  │
                      └──────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │ Final Safety Checks    │
                    │                       │
                    │ • Test count          │
                    │ • Collection status   │
                    │ • Final validation    │
                    └───────────┬───────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │ Final Result          │
                    │                       │
                    │ • Changes             │
                    │ • Validation          │
                    │ • Diff                │
                    │ • Status              │
                    │ • ZIP download        │
                    └───────────────────────┘


---

# 5. How Natural Language Processing Works

This project does not use a separate traditional NLP pipeline such as tokenization, stemming, or a custom classifier.

Instead, natural-language understanding is performed by the Groq-hosted LLM.

The flow is:

Developer writes natural language request
                ↓
       Task is normalized
                ↓
    Repository manifest is created
                ↓
   Task + repository context
                ↓
          Groq LLM
                ↓
       Structured JSON plan
                ↓
Relevant files + implementation steps
                ↓
       Implementation LLM call
                ↓
      Structured code changes


For example, the developer writes:


Add input validation to divide() so that b=0 raises a clear
ValueError, and add a meaningful test for that behavior.


The agent does not simply send that text directly to a file-writing function.

The LLM first interprets the intent and produces a structured plan such as:

json
{
  "summary": "Add zero-division validation to divide() and test the new behavior.",
  "steps": [
    "Inspect divide() implementation.",
    "Add explicit validation for b == 0.",
    "Raise a clear ValueError.",
    "Add a regression test.",
    "Run the full test suite."
  ],
  "relevant_files": [
    "app.py",
    "test_app.py"
  ],
  "allowed_new_files": [],
  "test_strategy": "python -m pytest -q",
  "risks": [
    "Preserve existing divide() behavior for valid inputs."
  ]
}


The application then uses that structured result rather than allowing the LLM to arbitrarily choose any project file.

---

# 6. Agent Workflow in Detail

## Step 1 — Select a project

The UI supports:


Bundled sample


or

Upload ZIP


The bundled project is intentionally small so that the complete flow is easy to demonstrate.

An uploaded ZIP is extracted into a temporary workspace.

Unsafe paths such as:

../../file


are rejected to prevent ZIP path traversal.

---

## Step 2 — Enter a developer request

The developer enters a request such as:

Add input validation to divide() so that b=0 raises a clear
ValueError, and add a meaningful test for that behavior.

The task is passed to the agent.

---

## Step 3 — Task classification

Before performing a normal code modification workflow, the application checks for special task types.

### Read-only requests

For example:


Inspect this repository and explain the architecture.
Do not modify or create any files.

The application recognizes this as an inspection-only request.

The agent then:

- inspects the repository
- explains the architecture
- identifies files
- explains tests
- lists dependencies
- reports confirmed issues
- reports possible environment issues

No project files are modified.

---

### Dependency safety

If the task explicitly requests a dependency that is not declared by the project, the agent does not silently replace that dependency with another implementation.

For example:

Add fake_validation and use it for request validation.


If `fake_validation` is not declared in the project, the agent blocks the request and explains that the dependency needs to be properly added and approved.

This prevents the LLM from creating fake local packages with the same import name.

---

### Intentional failure workflow

The application also supports a controlled validation scenario where a temporary test is created to intentionally fail.

The agent:

1. Creates the temporary assertion.
2. Runs the test.
3. Shows the expected failure.
4. Removes the temporary test.
5. Runs the final test suite again.
6. Confirms that the final diff is clean.

This demonstrates that the agent can distinguish an expected test failure from an actual implementation failure.

---

## Step 4 — Repository discovery

The application scans the repository and creates a file manifest.

The agent avoids irrelevant directories such as:


.git
.venv
venv
env
node_modules
__pycache__
.pytest_cache


It also avoids sensitive files such as:

.env
credentials.json
service-account.json
secrets.json


The objective is to keep the context relevant and reduce accidental exposure of secrets.

---

## Step 5 — Baseline test collection

Before the implementation begins, the application checks the existing test suite.

The purpose is to establish a baseline.

For example:

Baseline test collection: 3 tests

This is important because a coding agent should not claim success merely because a tiny replacement test suite passes.

The final validation later compares the baseline and final state.

---

## Step 6 — Planning

The task and repository information are passed to the Groq planner.

The planner returns:

Summary
Steps
Relevant files
Allowed new files
Validation strategy
Risks

Example:

Summary:
Add zero-division validation to divide().

Relevant files:
app.py
test_app.py

Validation:
python -m pytest -q

The plan is shown in the Streamlit UI before the implementation result is displayed.

---

## Step 7 — Relevant file selection

The planner is instructed to select files from the actual repository manifest.

It cannot simply invent arbitrary absolute paths.

The planner is also instructed to include relevant:

- implementation files
- configuration files
- tests

Only planned files are allowed during implementation.

---

## Step 8 — Read relevant file contents

The implementation stage receives the relevant file contents.

For example:

app.py
test_app.py

The agent uses those files as the implementation context.

This prevents the implementation model from operating only on the filename.

---

## Step 9 — Generate changes

The implementation LLM returns structured changes.

Conceptually:

json
{
  "changes": [
    {
      "path": "app.py",
      "content": "...updated file...",
      "rationale": "Add explicit validation for zero divisor."
    },
    {
      "path": "test_app.py",
      "content": "...updated test...",
      "rationale": "Add regression coverage for zero division."
    }
  ]
}

The application then validates these changes before writing them.

---

# 7. Safety and Guardrails

The agent intentionally includes safety checks because LLM-generated code can otherwise make unrelated or destructive changes.

## Approved file scope

The implementation can only modify:

relevant_files


or explicitly approved:

allowed_new_files

Any attempted modification outside that scope is rejected.

---

## Secret protection

The application does not intentionally modify secret-like files such as:

.env
credentials.json
service-account.json
secrets.json

---

## Fake dependency protection

The agent refuses to create dependency-shadowing files such as:

docx.py
groq.py
openai.py
requests.py
pytest.py

and other local fake third-party packages.

The purpose is to prevent a coding agent from "fixing" a missing dependency by creating a fake module.

---

## Destructive rewrite protection

Large unexpected rewrites are rejected.

For an existing implementation file, a substantial reduction in file size is treated as suspicious.

Existing tests have an even stricter reduction check to prevent the agent from deleting tests simply to make the suite pass.

---

## Retrieval stub protection

A suspicious replacement such as:

def retrieve(...):
    return []

where the original implementation performed real retrieval is rejected by a specific guard.

This prevents the model from bypassing functionality instead of implementing the requested fix.

---

## Baseline/final test safety

The application checks:

baseline test collection

and:

final test collection

If the final collection unexpectedly drops below the baseline collection, the final result is not treated as safe success.

The application also prevents claiming a successful full suite when test collection itself failed.

---

# 8. Validation Strategy

The agent uses the following validation strategy.

## Projects with pytest tests

Command:

```bash
python -m pytest -q
```

## Projects without pytest-style tests

Command:

```bash
python -m compileall -q .
```

The application displays the actual command and the actual output.

It does not simply display a hard-coded "tests passed" message.

---

# 9. Repair Loop

When validation fails, the agent can attempt a bounded repair.

Example:

Implementation
     ↓
pytest
     ↓
FAILED
     ↓
Repair attempt 1
     ↓
pytest
     ↓
FAILED
     ↓
Repair attempt 2
     ↓
pytest
     ↓
PASSED

The current limit is:

2 repair rounds


The failing test output is passed back to the implementation stage.

The model is instructed to fix the root cause using the actual test output.

---

# 10. Bundled Sample Project

The application creates a small sample project at runtime.

Its structure is:

sample project/
├── app.py
├── calculator.py
├── test_app.py
└── README.md

### app.py

Contains the core calculator functions:

python
divide()
format_result()

### calculator.py

Uses the `divide()` function as part of a higher-level operation.

### test_app.py

Contains tests for the existing behavior.

### README.md

Contains basic information about the sample project.

The project is intentionally small so the evaluator can quickly observe the complete coding-agent flow.

---

# 11. Example End-to-End Demo

A recommended demo task is:

Add input validation to divide() so that b=0 raises a clear
ValueError, and add a meaningful test for that behavior.


Expected workflow:

1. Repository indexed
2. Baseline tests collected
3. Task planned
4. app.py identified as implementation file
5. test_app.py identified as test file
6. Code change generated
7. Test change generated
8. Safety checks applied
9. Tests executed
10. Validation result displayed
11. Diff displayed
12. Modified project available for download

---

# 12. Example Read-Only Demo

Use:

Inspect this repository and explain its architecture,
tests, dependencies, and possible issues. Do not modify
or create any files.

Expected result:

Read-only repository analysis

The UI displays:

- architecture summary
- relevant files
- test information
- dependencies
- confirmed issues
- possible environment issues

No files are modified.

---

# 13. Example Intentional-Failure Demo

A controlled validation request can be used to demonstrate expected test failure handling.

The workflow is:

Create temporary failing test
        ↓
Run test
        ↓
Expected failure observed
        ↓
Remove temporary test
        ↓
Run final suite
        ↓
Final diff clean


The final UI explicitly separates the temporary failure from the final project state.

---

# 14. User Interface

The Streamlit application provides:

## Project selection

Bundled sample
Upload ZIP

## Developer task

A text area for entering the natural-language coding request.

## Agent progress

The UI shows progress such as:

Indexing repository
Running baseline test collection
Planning task
Relevant files: app.py, test_app.py
Implementing changes
Running validation
Repairing validation failure

## Results

The UI contains:

1. Plan
2. Changes
3. Validation
4. Diff
5. Final status

A modified project ZIP can be downloaded at the end.

---

# 15. Project Structure

The repository can be kept small:

coding-agent/
│
├── app.py
├── requirements.txt
├── README.md
└── .env.example

The bundled sample project is generated by `app.py` in a temporary workspace.

User-uploaded repositories are also extracted into temporary workspaces.

---

# 16. Technology Stack

## Frontend / UI

Streamlit

Used to provide:

- project selection
- ZIP upload
- task input
- progress updates
- plan display
- validation display
- diff display
- ZIP download

## Backend / Application Logic

Python

Responsible for:

- repository discovery
- file reading
- workspace management
- safety checks
- test execution
- diff generation
- ZIP handling
- workflow orchestration

## LLM

Groq


Default model:
openai/gpt-oss-120b

The LLM is used for:

- task understanding
- planning
- relevant file selection
- implementation generation
- repair reasoning

## Validation

pytest
compileall

---

# 17. Installation

## Prerequisites

Recommended environment:
Python 3.10+

Check your Python version:

python --version

---

# 18. Create Virtual Environment

### Windows

python -m venv .venv

Activate:


.venv\Scripts\activate

### macOS / Linux

python3 -m venv .venv

Activate:

source .venv/bin/activate

---

# 19. Install Dependencies

Install the required packages:

pip install -r requirements.txt

The `requirements.txt` should contain:

streamlit
python-dotenv
groq
pytest

---

# 20. Configure Groq API Key

Create a `.env` file in the project root:


GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=openai/gpt-oss-120b

---

# 21. Run Locally

Start the Streamlit application:

streamlit run app.py


The terminal will display a local URL similar to:

http://localhost:8501

Open that URL in the browser.

---

# 22. Running the Application

Once the UI opens:

### Step 1

Choose:

Bundled sample

### Step 2

Enter a task such as:

Add input validation to divide() so that b=0 raises a clear
ValueError, and add a meaningful test for that behavior.


### Step 3

Click:
Run coding agent


### Step 4

Observe:
repository discovery
baseline validation
planning
relevant file selection
implementation
safety checks
validation
repair if necessary

### Step 5

Review:
Plan
Changes
Validation
Diff
Final status

### Step 6

Download:
coding-agent-result.zip

---

# 23. Uploading Another Project

The application also supports user projects.

Create a ZIP:

my-project.zip


Then:

1. Select `Upload ZIP`
2. Upload the project ZIP
3. Enter the coding request
4. Run the coding agent

Example:

Refactor the pricing function to make the discount
calculation easier to read and add a regression test.

The uploaded project is processed in a temporary workspace.

---

# 24. Deployment — Streamlit Community Cloud

The application can be deployed using Streamlit Community Cloud.

## Step 1 — Push code to GitHub

Create a GitHub repository.

Example:

coding-agent

Push:

app.py
requirements.txt
README.md

Do not push:

.env
API keys
secrets
credentials

---

## Step 2 — Open Streamlit Community Cloud

Create a new Streamlit application.

Select:

Repository: your GitHub repository
Branch: main
Main file: app.py

---

## Step 3 — Add Streamlit Secrets

Open the application's secrets settings and add:

```toml
GROQ_API_KEY = "YOUR_GROQ_API_KEY"
GROQ_MODEL = "openai/gpt-oss-120b"
```

---

## Step 4 — Deploy

After deployment, Streamlit provides a public application URL similar to:

https://your-app-name.streamlit.app


Add the final deployed URL to the submission information section below.

---

# 25. Environment Variables

## Local

`.env`

GROQ_API_KEY=your_key
GROQ_MODEL=openai/gpt-oss-120b


## Streamlit Cloud

Use Streamlit Secrets:

```toml
GROQ_API_KEY = "your_key"
GROQ_MODEL = "openai/gpt-oss-120b"
```

---

# 26. Error Handling

The application handles common failures such as:

- missing Groq API key
- invalid ZIP uploads
- unsafe ZIP paths
- invalid model output
- invalid implementation paths
- test failures
- test collection failures
- missing dependencies
- unsafe dependency shadowing
- destructive rewrites
- suspicious retrieval stubs
- validation failures

The application reports actual validation output rather than hiding errors behind a generic success message.

---

# 27. Important Safety Design

The application uses a temporary workspace for coding operations.

The original input project is not modified directly.

This gives the workflow the following structure:

Original project
       │
       ▼
Temporary workspace
       │
       ├── inspect
       ├── plan
       ├── modify
       ├── test
       ├── repair
       └── diff
       │
       ▼
Downloadable modified ZIP

This is especially useful when evaluating LLM-generated changes.

---

# 28. Agentic Design

Although the application does not depend on a large autonomous framework, it follows an agent-style workflow.

The system separates the task into multiple stages:

Understand
    ↓
Inspect
    ↓
Plan
    ↓
Select
    ↓
Implement
    ↓
Validate
    ↓
Repair
    ↓
Explain

Each stage has a specific responsibility.

This is preferable to sending the entire project to one LLM call and asking the model to "fix everything".

---

# 29. Why the Planner and Implementation Stages Are Separate

The planner and implementation stages are intentionally separated.

### Planner

The planner answers:

What needs to change?
Which files are relevant?
What tests should be updated?
What risks exist?

### Implementation

The implementation stage answers:

How should the selected files be changed?

This separation provides better control over the generated changes and makes the agent's workflow visible to the developer.

---

# 30. Why Baseline Testing Is Important

Without a baseline, an AI coding agent could accidentally remove existing functionality or tests and then report success because a smaller test suite passes.

The application therefore records the baseline state first.

Example:

Before:
5 tests collected

After:
2 tests collected

A reduction like this is treated as suspicious.

The final validation checks that the agent did not simply eliminate the existing test coverage.

---

# 31. Why Temporary Workspaces Are Used

The coding agent performs operations such as:

read files
write files
execute tests

These operations happen in a temporary workspace instead of the original project.

Benefits include:

- original project remains untouched
- changes can be reviewed
- final diff can be generated
- modified ZIP can be downloaded
- unsafe changes can be rejected before producing the final result

---

# 32. Testing the Coding Agent

Recommended manual scenarios:

## Scenario 1 — Normal code change

Request:

Add input validation to divide() so b=0 raises ValueError
and add a test for it.

Expected:

Plan generated
Files selected
Code changed
Test added
Tests pass
Diff displayed

---

## Scenario 2 — Refactoring

Request:

Refactor the calculation logic to make it easier to read
without changing its behavior.


Expected:
Implementation changes are limited to relevant files
Existing behavior remains valid
Tests pass

---

## Scenario 3 — Read-only request

Request:
Inspect this repository and explain its architecture.
Do not modify or create any files.

Expected:

Repository analysis shown
No files modified

---

## Scenario 4 — Intentional failure

Use the intentional-failure workflow to verify that the application can:

create temporary failing test
→ observe failure
→ remove temporary test
→ restore clean state
→ verify final suite

---

## Scenario 5 — Missing dependency

Request a dependency that is not declared.

Expected:
Dependency review
No fake local package created
No project modification

---

# 33. Assumptions

The project makes the following assumptions:

1. The coding target is primarily a Python project.
2. Pytest is the preferred validation framework when tests exist.
3. The repository contains source code that can be represented as text.
4. The project can be processed inside a temporary local or hosted workspace.
5. A valid Groq API key is available for live LLM execution.
6. The model can return structured JSON according to the prompts provided by the application.

---

# 34. Limitations

## LLM dependency

The agent depends on Groq for live task understanding, planning, and implementation.

If the API is unavailable or rate-limited, the coding workflow may not complete.

---

## Not a full security sandbox

Project tests are executed as subprocesses in the application's environment.

The temporary workspace protects the original project from direct modification, but this application is not intended to be a fully isolated security sandbox for arbitrary untrusted code.

---

## Python-focused validation

The built-in validation flow is primarily designed around:

pytest
compileall

Other programming languages may require additional validation commands.

---

## No persistent project storage

Uploaded projects are handled in temporary workspaces.

The application does not act as a permanent source-code repository.

---

## No Git commit workflow

The application generates the modified project and diff but does not automatically create Git commits or pull requests.

---

## Limited repair rounds

The repair loop is intentionally bounded to:

2 repair rounds

This prevents an endless LLM/test feedback loop.

---

## Context limits

The application limits the amount of repository and file content passed into the LLM to keep requests bounded.

Large repositories may require additional indexing or retrieval strategies in a production version.

---

# 35. Future Improvements

Possible improvements for a production-grade version include:

- AST-based code understanding
- semantic code search
- vector-based repository retrieval
- language-specific parsers
- native tool-calling models
- Git branch creation
- pull-request generation
- human approval before applying changes
- persistent task history
- authentication
- isolated container execution
- support for JavaScript, Java, Go and other languages
- richer test intelligence
- code quality checks using linters
- static analysis integration
- multi-file patch application instead of complete-file replacement
- repository-level dependency graph generation

---

# 36. Design Principles

The project follows several principles:

### Keep the scope small

The assignment requires a complete end-to-end workflow rather than a huge unfinished system.

### Make the LLM useful

The LLM is responsible for semantic tasks such as:

understanding
planning
file selection
implementation
repair

### Keep execution deterministic where possible

Repository inspection, file validation, safety checks and test execution are handled by application code.

### Never trust generated changes blindly

Generated modifications are checked before they are applied.

### Show the work

The developer can see:

Plan
Relevant files
Changes
Validation
Diff
Final status

---

# 37. End-to-End Example

A complete example looks like this:

Developer
   │
   │ "Add validation to divide() and add a test"
   ▼
Streamlit UI
   │
   ▼
Task Classification
   │
   ▼
Repository Discovery
   │
   ▼
Baseline Test Collection
   │
   ▼
Groq Planner
   │
   ├── Relevant files
   ├── Implementation steps
   ├── Test strategy
   └── Risks
   │
   ▼
Groq Implementation
   │
   ├── app.py change
   └── test_app.py change
   │
   ▼
Safety Validation
   │
   ├── approved paths
   ├── fake dependency protection
   ├── destructive rewrite protection
   └── test protection
   │
   ▼
Temporary Workspace
   │
   ▼
pytest
   │
   ├── PASS → finish
   │
   └── FAIL
          │
          ▼
     Repair attempt
          │
          ▼
        pytest
   │
   ▼
Final Safety Validation
   │
   ▼
Diff + Final Result
   │
   ▼
Download modified ZIP

---

## Deployed Application

[<YOUR_STREAMLIT_DEPLOYED_URL>](https://basic-coding-agent.streamlit.app/)

## GitHub Repository

[<YOUR_GITHUB_REPOSITORY_URL>](https://github.com/sayali-kumbhar/coding-agent)

---

# 38. Brief Approach Explanation

The application uses a staged LLM-driven coding workflow.

A natural-language developer request is first classified and the repository is indexed. Existing tests are collected to establish a baseline. The request and repository manifest are then sent to the Groq LLM planner, which identifies the relevant files, creates an implementation plan, defines the test strategy and records risks.

The implementation stage receives the selected files and plan and generates structured changes. Before applying those changes, the application verifies that only approved paths are modified and rejects unsafe patterns such as fake dependency packages, secret-file modifications, destructive rewrites and suspicious test reductions.

Changes are applied inside a temporary workspace and validated using pytest or compileall. When validation fails, the agent receives the real failure output and can perform up to two bounded repair attempts.

Finally, the application performs additional safety checks, generates a diff, displays the implementation and validation results, and provides the modified project as a downloadable ZIP.

This architecture keeps the project small while demonstrating a complete coding-agent flow from natural-language understanding through implementation, validation and result presentation.

---

## 🧪 Try the Agent with a Sample Project

Download the tested sample project:

[Download Mini Shop Test Project](https://github.com/sayali-kumbhar/coding-agent/blob/main/sample_project/mini-shop-coding-agent-test.zip)

After downloading:

1. Open the deployed AI Coding Agent.
2. Select **Upload ZIP**.
3. Upload `mini_shop_test.zip`.
4. Try a coding task such as:

> Add a test for the 100% discount case and make sure all existing tests continue to pass.

The agent will inspect the project, create a plan, make the requested change, run validation, and display the resulting diff.
## 🧪 Example Scenarios

### 1. Add a New Feature

**Task:**
> Add a test for the 100% discount case and make sure all existing tests continue to pass.

**Agent demonstrates:**
- Understands the request
- Identifies relevant files
- Creates a plan
- Updates the implementation/tests
- Runs validation
- Shows the final diff

---

### 2. Refactoring

**Task:**
> Refactor the pricing calculation to improve readability without changing its behavior.

**Agent demonstrates:**
- Identifies the relevant implementation file
- Makes a focused code change
- Preserves existing behavior
- Runs the existing test suite
- Shows changed files and diff

---

### 3. Read-Only Repository Analysis

**Task:**
> Inspect this repository and explain its architecture, tests, dependencies, and possible issues. Do not modify or create any files.

**Agent demonstrates:**
- Repository inspection
- Multi-file analysis
- Architecture explanation
- Test/dependency review
- No project modifications

---

### 4. Validation Failure and Repair

**Task:**
> Make the requested change and ensure the test suite passes.

When the generated change causes a test failure, the agent uses the actual test output to attempt a bounded repair and then runs validation again.

**Agent demonstrates:**
- Test-driven validation
- Failure detection
- Repair loop
- Final verification

---

### 5. Dependency Safety

**Task:**
> Add and use a dependency that is not currently declared in the project.

The agent identifies that the dependency is not declared instead of creating a fake local package or silently replacing it.

**Agent demonstrates:**
- Dependency awareness
- Safe handling of missing dependencies
- Protection against fake package creation
- No unsafe project modification

