# Security and privacy

## Reporting a vulnerability

Use GitHub's private vulnerability-reporting function for this repository. Do not open a public
issue containing vulnerability details, credentials, transcripts or application content.

## Secrets

OpenAI API keys are read from the `OPENAI_API_KEY` environment variable or the macOS Keychain.
They must never be committed, logged or placed in application configuration files.

The macOS application bundle contains only version-controlled code, the Python runtime and static
interface assets and redistributed licence notices. It must not contain API keys, OAuth caches,
transcripts, generated records,
application settings or runtime logs. Those remain in the macOS Keychain or their existing private
per-user locations and are resolved only when the installed application runs.

## Controlled dependency setup

The first-run assistant performs local path, version and authorisation-status checks only. It does
not read connected-application content. Homebrew is never installed automatically. Where Homebrew
already exists, Node.js and uv may be installed through fixed argument lists. The PLAUD CLI and
experimental `mcp-remote` bridge are installed only at the reviewed versions named in the
application. Commands run without a shell, and downloaded installation scripts are never executed.

Each installation requires a separate confirmation that shows its purpose, source and exact fixed
command or steps. API-key entry, OAuth sign-in and macOS application permissions remain manual.
The bundled OmniFocus adapter is copied to a private per-user directory with restrictive
permissions and exposes only two read-only tools: aggregate status and bounded task metadata.
System health is the post-authorisation verification boundary.
The complete content-free health check runs automatically at every application start until every
required component reports `OK`. Closing the setup assistant or saving only the API key does not
set the local completion marker. Failed and partial results remain unresolved and are checked again
at the next start; a complete result is stored locally for the current health-check version.

## Content boundary

OpenAI processing is limited to non-sensitive or anonymised content. People, recruitment, welfare,
health, disciplinary, appeal, licensing and formal performance material remains excluded until a
specific organisational privacy and compliance decision authorises processing.

API requests use `store=false`, a bounded output and one request per minutes run. This does not
remove the provider's default abuse-monitoring retention. Transcripts and generated records remain
subject to human verification.

## External systems

DEVONthink writes use only the signed local MCP executable. The application verifies the visible
database boundary, selected target, source reference, content fingerprint and duplicate status
before presenting a final confirmation. It repeats the duplicate check immediately before the
write, creates one Markdown record and reads back its metadata and content. It does not overwrite,
merge, move or delete an existing record automatically.

The public configuration allows writes only to the DEVONthink database named `Inbox`. A database
named `Restricted` is explicitly rejected, and its unexpected visibility stops all DEVONthink
writes. DEVONthink database packages must never be modified through the filesystem.

PLAUD, Agenda and remarkdown are source systems. The application must use their supported MCP or
API boundaries and must not access application databases directly.

PLAUD access uses the official `@plaud-ai/cli` in read-only mode. OAuth credentials remain under
the CLI's local credential management and are never read, displayed or copied by this application.
The app lists recording metadata only on request and retrieves the raw transcript selected by the
user. For that same recording it may retrieve PLAUD's derived summary as a visibly separate,
secondary source for resolving speaker labels, names and evident transcript ambiguity. It does not
request audio URLs or polished transcripts. Retrieved material is held in memory for review and is
not written to project files or logs.

ChatGPT personal Memory is not available through the OpenAI API. The app therefore performs no
automatic Memory read. A user may explicitly load a reviewed `.txt` or `.md` context export up to
1 MB. That context may clarify established names, roles and acronyms but is not evidence of
attendance, speech, decisions, commitments or action ownership.

Agenda access uses the application's built-in local MCP endpoint at `127.0.0.1`. The PEA app calls
only `agenda_list_projects`, `agenda_search_notes` and `agenda_get_note`. Project metadata is listed
first. Note metadata may then be limited to one selected project or filtered locally to entries
edited during the last seven days across the active projects. Full Markdown is retrieved only for
one highlighted note or for an explicit checklist selection of no more than ten notes for the
Weekly Summary. Agenda write and open-note tools are not called. Retrieved note content is held in
memory for review and is not written to project files or logs.

remarkdown access uses the official Streamable HTTP MCP endpoint through `mcp-remote`. Its OAuth
cache is isolated under `~/Library/Application Support/Personal Executive Assistant/mcp-auth/`;
directories are restricted to mode `0700` and files to `0600`. OAuth material is never read into
the UI, copied to Git or written to the runtime log. The bridge filters out `push_markdown`,
`refresh_documents`, `fetch_page_chunks` and `email_remarkdown_support` before exposing tools to
the app. The reader lists only metadata for documents modified within 30 days, retrieves only the
explicitly selected document, passes `force=false`, and permits only content already marked as
typed or transcribed. Documents outside the transcription window are blocked locally, so the PEA
app does not initiate or spend credits on transcription. Retrieved text remains in memory and
transcribed handwriting is identified as derived content requiring review. OAuth recovery may
terminate only a `mcp-remote` child process whose parent is the running PEA process and whose
command targets the fixed official remarkdown MCP URL.

Period summaries query only the selected authorised DEVONthink database for records tagged both
`minutes` and `pea-import` and filed within the selected day or ISO week. Metadata is filtered
before the matching record bodies are retrieved; the result is capped at 100 records.
Agenda and reMarkable content remains explicitly selected. Work-related chats must be pasted by
the user, and email content must be dropped as a local `.eml`, `.txt` or `.md` export with a 5 MB
combined limit; the app has no mailbox access. The app sends the resulting approved sources in one
bounded OpenAI request with storage disabled. Each weekly summary uses the stable `weekly:YYYY-Www` source
reference, a week-numbered title and the DEVONthink tag `weekly-summary`; duplicate and read-back
controls are identical to the Minutes workflow.

The Workflows page composes these existing controls without widening their permissions. Workflow
checkpoints exist only in process memory and are discarded when the application closes. A workflow
may retrieve its stated source and make one OpenAI request before presenting the combined preview,
but it cannot write to DEVONthink until the user presses the single final confirmation button.
Resuming a failed workflow reuses only completed in-memory stages. The final import still performs
the DEVONthink duplicate recheck and post-write content verification.

OmniFocus reads use the separately installed controlled local MCP adapter and its reviewed static
Omni Automation dispatcher. The app exposes aggregate status and bounded task views; it offers no
arbitrary OmniJS execution. Task-view responses are reduced to title, project, effective status,
dates and flag state. Existing notes, attachments and tags are discarded and no OmniFocus content
is sent to OpenAI.

Inbox capture uses a second fixed, app-local dispatcher that accepts only review, create, verify and
retract operations. Every proposal requires a single-line title and stable source reference. The
source reference and normalised title form a SHA-256 fingerprint stored in a bounded provenance
marker in the new task note. Review exposes counts only. Creation repeats the duplicate check in
the same Omni Automation execution, writes exactly one unassigned Inbox task and then performs an
independent read-back. Retraction requires the exact task identifier, title and fingerprint and is
limited to reversible completion; it cannot delete or alter another task. Controlled testing covers
creation, verification and retraction with a non-operational task. Other OmniFocus writes,
project assignment, tag assignment and arbitrary scripting remain unavailable.

Minutes action-item handoff remains an in-memory proposal step. Each source reference is derived
from the Minutes source plus the action wording, recorded owner and due date, so regenerating the
same action yields the same duplicate key. The UI displays owner and due date for review but sends
neither to an automatic assignment mechanism. Selecting an item only fills the existing capture
form; the separate duplicate review and final confirmation remain mandatory for every task.

## Diagnostics and local operational metadata

The health check validates the OpenAI key and model endpoint, Node.js, PLAUD authorisation,
aggregate OmniFocus status, remarkdown sign-in and pairing, and the advertised Agenda and
DEVONthink MCP tools. It reads only
remarkdown account, credit and synchronisation status—not document metadata or content. MCP tool
discovery does not read application content and the OpenAI check retrieves model metadata without
running an inference. The normal project API key is not reused as, or replaced by, a
higher-privilege OpenAI Admin key.

Successful PEA API requests contribute only aggregate request, input-token and output-token counts
to the application's local settings. These counters begin with version 0.6.0, are not
organisation-wide billing evidence and are never committed.

The runtime log is stored under `~/Library/Logs/personal-executive-assistant/`, rotates at 1 MB with
three backups, and uses private directory and file permissions. Log events may contain operation
names, aggregate counts, model identifiers and exception class names. API keys, OAuth material,
transcripts, prompts, generated minutes, Agenda content, DEVONthink content, document titles and
source-system identifiers must not be logged.
