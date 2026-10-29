# Naukri Automation Tools

This project contains two independent scripts:

- [`naukri-open.py`](./naukri-open.py) updates a Naukri profile display name.
- [`job-finder.py`](./job-finder.py) opens public job searches based on resume
  role keywords and experience level.

## Naukri profile updater

The updater opens your Naukri profile in Microsoft Edge and alternates the
displayed profile name between **Chayan Sehgal** and **Chayan S** every 30
minutes. After each successful change, it prints the last update time and the
next scheduled update time in your computer's local time.

> **Use responsibly:** This script edits your Naukri profile repeatedly. Make
> sure the changes comply with Naukri's terms and any applicable rules. You are
> responsible for reviewing the profile changes and stopping the script when
> you no longer want them.

### Requirements

- Windows
- Python 3.10 or later
- Microsoft Edge
- A Naukri account you can sign into
- The `selenium` Python package

### Quick start

Open PowerShell in this project folder and run:

```powershell
uv run --no-project --with selenium python naukri-open.py
```

If you don't have [uv](https://docs.astral.sh/uv/) installed, install Selenium
into your Python environment and run the script directly:

```powershell
python -m pip install selenium
python naukri-open.py
```

The script launches Edge with a **separate browser profile** so it doesn't use
or interfere with your normal Edge profile. When the browser opens, sign into
Naukri in that window if prompted. The script waits up to five minutes for a
recognized profile name to appear.

The first name change happens as soon as the profile is ready. Further changes
are made 30 minutes after each successful update. To stop the script, press
**Ctrl+C** in the PowerShell window.

### Configuration

The script can be configured with these optional environment variables:

| Variable | Purpose | Default |
| --- | --- | --- |
| `EDGE_EXECUTABLE` | Full path to `msedge.exe` if Edge isn't found automatically. | Automatically searches common Windows install locations and `PATH`. |
| `NAUKRI_EDGE_USER_DATA_DIR` | Directory for the dedicated Edge profile and its saved sign-in session. | `%LOCALAPPDATA%\Jobhunt\NaukriEdgeProfile` |

Example for the current PowerShell session:

```powershell
$env:EDGE_EXECUTABLE = 'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
$env:NAUKRI_EDGE_USER_DATA_DIR = "$env:LOCALAPPDATA\Jobhunt\NaukriEdgeProfile"
python naukri-open.py
```

The automation uses local debugging port `9222`. Close other Edge windows
using this dedicated profile before starting the script; another process
already using the port or profile can prevent startup.

### What the script does

1. Starts Edge using the dedicated profile and opens your Naukri profile page.
2. Detects which of the two supported names is currently displayed.
3. Opens the profile editor, updates the name, saves, and verifies the result.
4. Prints the updated name and the local timestamps for the last and next
   update, then waits 30 minutes before repeating.

If Edge is closed while the script is running, it attempts to reopen the
automation browser and continue.

### Troubleshooting

- **Selenium is required:** Run the `uv` quick-start command or install Selenium
  with `python -m pip install selenium`.
- **Edge cannot be found:** Set `EDGE_EXECUTABLE` to the full path of
  `msedge.exe`.
- **Sign-in or profile name not detected:** Sign into Naukri in the dedicated
  Edge window and make sure the profile page shows exactly one of the supported
  names: `Chayan Sehgal` or `Chayan S`. Restart the script after signing in.
- **Edge debugging endpoint does not start:** Close other Edge instances using
  the dedicated profile and check that local port `9222` is available.
- **Profile editor controls cannot be found:** Naukri may have changed its
  profile page. The script stops rather than submitting a change when it
  cannot identify the name field or a unique Save/Update button.

## Resume-based job finder

The job finder reads one or more PDF, DOCX, TXT, or Markdown resumes on your
computer and creates `latest-job-links.html`, a clickable local page with
separate searches for LinkedIn public posts and job listings, Naukri,
Wellfound, and company career boards. Each resume is handled separately so its
role terms are not mixed with another resume. Searches match **any** extracted
role title or skill, include common experience phrases from fresher through
two years, and cover results Google dates within the past three days, newest
first. Experience matching depends on wording in the listing, so confirm that
the role does not require more than two years. By default, your resume text
stays local unless `--use-ai` is selected.

It does not scrape or rank search results, sign in to job platforms, bypass
access controls, apply, or message recruiters. Search results can be incomplete
or stale; LinkedIn may require sign-in, posts that are not publicly indexed
will not appear, and the same opening may be reposted by multiple people.
Review each listing and its requirements before applying.

Run it from PowerShell:

```powershell
py -3.12 job-finder.py --resume "C:\Users\asus\Documents\resume.pdf" --experience-years 1.5
```

PDF text extraction requires the optional `pypdf` package:

```powershell
py -3.12 -m pip install pypdf
```

DOCX, TXT, and Markdown resumes use Python's standard library. Local role
inference uses common role titles; use `--use-ai` for AI to extract more
resume-specific titles and skills from each resume independently. You can
provide multiple resumes, select sources, and set a location:

```powershell
py -3.12 job-finder.py --resume ".\Backend_Resume_Chayan.pdf" `
  --resume ".\Chayan_Sehgal_GenAI_Engineer.pdf" `
  --resume ".\Fullstack_Chayan_Resume.pdf" `
  --experience-years 1.5 --location "Bengaluru" --use-ai
```

The generated HTML page opens automatically; use its source links to open the
live search results. Add `--no-open` to create the file without opening it.
Use `--output "C:\path\to\links.html"` to choose another file path.
The date window is calculated each time the script runs, and the HTML file is
overwritten with fresh search links. Rerun this command each day to refresh it:

```powershell
py -3.12 job-finder.py --resume ".\Backend_Resume_Chayan.pdf" `
  --resume ".\Chayan_Sehgal_GenAI_Engineer.pdf" `
  --resume ".\Fullstack_Chayan_Resume.pdf" `
  --experience-years 1.5 --use-ai
```

`--experience-years` supplies your actual experience to the AI extractor; it
does not change the search's fresher-to-two-years experience phrases. Google
uses indexed dates, which may differ from the actual job posting date. The
existing profile updater remains a separate script and is not changed by the
job finder.

### Optional AI extraction with Groq

The optional `--use-ai` mode uses Groq's OpenAI-compatible Chat Completions API
to extract target roles and skills from each resume separately, then creates
the clickable search page. It does **not** fetch or rank individual job posts.
Using this mode sends the full resume text to Groq; use it only if you accept
the provider's data-handling terms. Requests are subject to your Groq account's
usage limits and any applicable charges.

Keep the API key in the ignored local `.env` file (never commit or share it):

```text
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=openai/gpt-oss-120b
```

The repository includes [`.env.example`](./.env.example) as a template. Add
those settings to your existing `.env` without overwriting it, then run:

```powershell
py -3.12 job-finder.py --resume "C:\Users\asus\Documents\resume.pdf" --experience-years 1.5 --use-ai
```

Without `--use-ai`, no resume content is sent to Groq. `GROQ_MODEL` is optional
and defaults to `openai/gpt-oss-120b`.

## Project files

- [`naukri-open.py`](./naukri-open.py) — Naukri profile updater.
- [`job-finder.py`](./job-finder.py) — resume-based public job search.
- [`.env.example`](./.env.example) — Groq environment variable template.
