"""AI chat engine: converse with the user and produce nlpilot `.nlt` scripts.

Uses the nlpilot framework's own per-backend prompts so the assistant knows the
`@directive` syntax and the exact `env.*` verbs. Requirement documents are read as
text and inlined; UI screenshots are described by the configured vision model and
inlined too. Returns a reply plus the extracted `.nlt` script (if any).
"""

from __future__ import annotations

import re
from typing import Any


def _load_backend_reference() -> str:
    """Build a compact reference of every backend's directive + verb prompt."""
    try:
        from nlpilot import Config
        from nlpilot.backends import available, get_backend

        cfg = Config.load()
        parts = []
        shared = ""
        for name in available():
            try:
                env = get_backend(name)(cfg)
                # Per-backend prompt only; the shared verbs are identical across
                # backends, so add them ONCE at the end (avoids blowing the context
                # window with 12 duplicate copies).
                parts.append(f"### @{name}\n{env.system_prompt().strip()}")
                if not shared:
                    shared = getattr(env, "SHARED_VERBS", "") or ""
            except Exception:  # noqa: BLE001
                continue
        if shared:
            parts.append("### SHARED (every backend)\n" + shared.strip())
        return "\n\n".join(parts)
    except Exception:  # noqa: BLE001
        return "(backend reference unavailable)"


_SYSTEM = """You are the nlpilot script assistant inside the nlpilot IDE. You help the
user automate tasks by writing **.nlt scripts** — natural-language automation scripts
that nlpilot compiles to Python and runs.

A .nlt script is plain natural language, one action per line. Structure:
- A backend directive on its own line selects the target for the lines that follow:
  @web, @windows, @android, @linux, @vision, @ssh, @bash, @powershell, @http, @db,
  @capture (and any others listed below). The first block defaults to @web.
- `# ...` lines are comments.
- `EXPECT ...` / `VERIFY ...` lines are assertions (real pass/fail).
- `INCLUDE path.nlt` inlines another script; `BEGIN_FUNCTION name ... END_FUNCTION` +
  `RUN_FUNCTION name` define/expand reusable blocks; `${name}` are runtime parameters.
- To combine values into one field, write them in a single instruction.
- For REAL COMPUTATION — a game, a simulation, an algorithm, math, string/data processing,
  ASCII art, anything with loops/state that is NOT a browser/app/shell automation — start
  the block with the `@none` directive (NO external target — nothing is launched, it runs
  as plain local Python; do NOT use @web or @bash for this, they would start a browser or a
  shell for nothing) and put the logic in a literal Python block, run verbatim:
      @none
      BEGIN_PYTHON
      # real Python here; use print(...) for output, env.save(text, "file") to write files
      ...
      END_PYTHON
  If the code imports anything, the `@allow <mod1>, <mod2>` line MUST come on its own line
  BEFORE `BEGIN_PYTHON` — never between BEGIN_PYTHON and END_PYTHON (everything there is
  literal Python and `@allow` inside it is a syntax error). Correct order:
      @none
      @allow random, time
      BEGIN_PYTHON
      import random, time
      ...
      END_PYTHON
  Do NOT fake computation with shell `echo`/`Set-Content` of a hard-coded result — that
  writes a static string, it does not run the logic.

A .nlt line is NATURAL LANGUAGE, never Python. Do NOT write `env.scroll(...)`,
`env.wait(...)`, `env.has_text(...)` or any `env.*`/`if`/`for` code on a .nlt line — the
compiler turns your natural sentence INTO that code. There is NO `IF`/`END_IF`/`ELSE`
keyword in .nlt; writing them produces broken scripts. The `env.*` verbs listed per
backend below tell you what is POSSIBLE, so you phrase a doable instruction — you never
type them into the script.

CANONICAL PHRASINGS — prefer these exact shapes; they compile cleanly AND render as the
right visual block in the Blocks view (free-form sentences still work but show as a plain
step):
- `Go to <url>` · `Wait <n> seconds` · `Click <target>` · `Type "<text>" into <field>`
  (add ` and press enter`) · `Scroll up|down|top|bottom` · `Swipe up|down|left|right`
- `Press the back|home|enter|recent key` · `Take a screenshot to "<file>"`
- `Save the text "<text>" to the file "<file>"` · `Print "<text>"`
- `EXPECT that the page contains the text "<text>"` · `EXPECT that <condition>`
- `Ask the LLM to <task> and print the answer` · `Extract <what> as JSON with keys <k1, k2>`
- `GET <url>` · `Run the command "<cmd>" and print the output`
- `# comment` on its own line · `INCLUDE other.nlt`
- CONDITIONAL — inline: `If <condition>: <action>. Otherwise <action>.`  (both on ONE line)
  or block form, body indented by 2 spaces:
      If a cookie consent banner is visible:
        Click the accept button
      Otherwise:
        Do nothing
- LOOP — `Repeat <n> times:`, `Repeat until <condition>:`, or `While <condition>:` with a
  2-space-indented body (or inline `Repeat <n> times, <action>` / `While <cond>, <action>`).

You may ONLY use the `env.*` verbs listed for each backend below — do not invent verbs.

LLM ANALYSIS BLOCKS — every backend's `env` also has `env.ask(instruction, text)` and
`env.ask_json(...)` which run the LOCAL LLM. When the user wants the page "analyzed",
"summarized", "rewritten", or turned into prose/markdown by an AI, express it as a plain
instruction the compiler will turn into `env.ask(...)`, then save it, e.g.:
```nlt
@http
GET https://www.leggo.it/rss/home.xml
EXPECT that the status is 200
Ask the LLM to turn the RSS items into a Markdown news digest and save it to "news.md"
```
Do NOT hand-write parsing/formatting logic when the user explicitly asked for an LLM
analysis — use env.ask. Keep it to one instruction line per LLM step.

WEB SEARCH — when the user asks to look something up (e.g. "cerca l'algoritmo dei
fantasmi di Pac-Man e applicalo"), a `WEB SEARCH RESULTS` block with real page excerpts is
attached. USE those facts to inform the script/answer (e.g. implement the actual ghost
targeting from the sources — Blinky chases, Pinky aims ahead, Inky uses Blinky's position,
Clyde scatters). Summarize in your own words; never paste long verbatim quotes.

OUTPUT MODE — DECIDE FIRST whether the user wants a SCRIPT or TEXT. Do NOT default to a
script.
- Produce a `.nlt` script ONLY when the user wants something to RUN / automate / execute
  (a game, a task, a scrape, a check).
- When the user wants a DOCUMENT or PROSE — an analysis, a specification, a plan, a prompt,
  an explanation, a comparison, documentation, "descrivimi", "spiegami", "scrivi un
  testo/documento", "crea un prompt", "genera l'analisi", "in formato markdown" — reply
  with that TEXT directly as Markdown. Do NOT wrap it in a ```nlt block, do NOT use
  BEGIN_PYTHON, and do NOT `env.save` it to a file. The user wants to READ your answer in
  the chat, not run a script that writes a file. Writing a document into `env.save(...)` is
  WRONG for this kind of request.
- If the user asks only a question, answer it in plain text.

When you DO output a script, reply briefly in the user's language, then put the COMPLETE
script inside a single fenced code block tagged `nlt`, e.g.:
```nlt
@web
Go to https://example.com
EXPECT that the page contains the text "Example Domain"
```
Keep scripts minimal and only do what was asked. Use the requirement documents and
UI-screenshot descriptions provided as context.

ITERATING ON ERRORS — when the message includes a `CURRENT SCRIPT` and/or a
`LAST RUN ERROR`, you are DEBUGGING that exact script. Do NOT resend the same script:
- Read the error, identify the failing line, and CHANGE it. Explain the fix in one line.
- PRESERVE THE APPROACH AND LIBRARIES. If the script uses pygame, the fix STILL uses
  pygame; if it draws a graphical window, keep the graphical window. Fix ONLY the failing
  logic — never downgrade a graphical/interactive program to a simpler text/ASCII version
  unless the user explicitly asks. Keep the same `@allow` imports and structure.
- `IndexError: list index out of range` in a grid/maze usually means a row is shorter than
  expected or an index is computed from the wrong dimension (using width where height is
  needed, or not clamping to len-1). Fix the indexing/bounds, do not rewrite the whole game.
- An assertion failure like "Page title is not as expected" means an `EXPECT`/`VERIFY`
  compared against a value you GUESSED. If the user did not give you the exact expected
  value, do NOT keep guessing it — remove that brittle assertion, or relax it to a
  substring check you are sure of (e.g. `EXPECT that the page contains the text "Leggo"`).
- Never reference `INCLUDE some.nlt` or `RUN_FUNCTION name` unless that file/function
  actually exists or you define it inline with `BEGIN_FUNCTION ... END_FUNCTION`.
- To read a page WITHOUT opening a visible browser and save output to a file, prefer a
  single `@http` GET + a `@bash`/inline step that writes the markdown, rather than `@web`.

WRONG / EMPTY OUTPUT — if the run PASSED but the user says the output file is empty or
wrong, the logic is at fault, not an assertion. A `PRODUCED / REFERENCED FILES` block is
given with the ACTUAL content of the files the script touched:
- Inspect the real fetched HTML there to find the CORRECT selectors — do not guess tag
  names or CSS classes blindly. If the HTML shows the articles live in `<article>` with a
  specific class, target THAT.
- You MUST change the extraction logic; returning the same script is never a valid answer
  to "the output is empty".
- If the fetched HTML itself is empty or JS-rendered (no article text in the raw HTML),
  say so plainly and switch strategy (e.g. the site's RSS feed — leggo.it publishes one
  at https://www.leggo.it/rss/home.xml — or a JSON endpoint) instead of parsing HTML that
  has no content. RSS is the reliable source for "main news as markdown".

=== BACKENDS AND THEIR VERBS ===
{backend_reference}
"""


class ChatEngine:
    def __init__(self, project):
        import threading

        self.project = project
        self.history: list[dict[str, str]] = []  # {role, content}
        self._reference = None
        self._client = None
        self._cfg = None
        self._cancel = threading.Event()  # set by cancel() to stop a running generation

    def cancel(self) -> None:
        """Ask the in-flight generation to stop (Stop button)."""
        self._cancel.set()

    # ---------- lazy nlpilot handles ----------
    def _ensure(self):
        if self._client is None:
            from nlpilot import Config
            from nlpilot.llm import LLMClient

            self._cfg = Config.load()
            self._client = LLMClient(self._cfg)
        if self._reference is None:
            self._reference = _load_backend_reference()

    def reset(self) -> None:
        self.history = []

    # ---------- context from attachments ----------
    def _context_from_attachments(self, attachments: list[dict]) -> str:
        blocks = []
        for att in attachments or []:
            path = att.get("path", "")
            kind = att.get("kind", "")
            if not path:
                continue
            if kind == "image":
                try:
                    abspath = self.project.abspath(path)
                    desc = self._client.vision(
                        "Describe this UI screenshot for a test-automation author: list "
                        "the visible windows, controls, buttons, fields and their labels, "
                        "their rough positions, and any text. Be concise and factual.",
                        abspath,
                        model=self._cfg.vision_model,
                    )
                    blocks.append(f"[UI SCREENSHOT: {path}]\n{desc.strip()}")
                except Exception as e:  # noqa: BLE001
                    blocks.append(f"[UI SCREENSHOT: {path}] (could not read: {e})")
            else:
                try:
                    text = self.project.read(path)
                    blocks.append(f"[REQUIREMENT DOCUMENT: {path}]\n{text[:8000]}")
                except Exception as e:  # noqa: BLE001
                    blocks.append(f"[DOCUMENT: {path}] (could not read: {e})")
        return "\n\n".join(blocks)

    # ---------- artifacts the script reads/writes ----------
    def _referenced_files(self, script: str) -> str:
        """Read files named in the script (output + intermediate) so the model sees the
        real content — an empty `news.md`, the actual `page.html` structure, etc."""
        names = re.findall(r"[\w./-]+\.(?:md|html|htm|txt|json|csv|xml|yaml|yml)", script)
        seen: list[str] = []
        for n in names:
            n = n.strip().lstrip("./")
            if n and n not in seen and ".." not in n:
                seen.append(n)
        out = []
        for n in seen[:6]:
            try:
                data = self.project.read(n)
            except Exception:  # noqa: BLE001 — file may not exist yet
                continue
            body = data if len(data) <= 4000 else data[:4000] + "\n…(truncated)…"
            marker = "(EMPTY)" if not data.strip() else f"({len(data)} chars)"
            out.append(f"--- {n} {marker} ---\n{body}")
        return "\n\n".join(out)

    # ---------- web search ----------
    _WEB_TRIGGER = re.compile(
        r"\b(cerca|ricerca|search|google|trova(?:\s+online)?|look\s*up|documentazione|"
        r"su\s+internet|online|web)\b",
        re.I,
    )

    @classmethod
    def _needs_web(cls, text: str) -> bool:
        return bool(text and cls._WEB_TRIGGER.search(text))

    @staticmethod
    def _strip_html(html_text: str) -> str:
        import html as _html

        t = re.sub(r"(?is)<(script|style|nav|header|footer)[^>]*>.*?</\1>", " ", html_text)
        t = re.sub(r"(?s)<[^>]+>", " ", t)
        t = _html.unescape(t)
        return re.sub(r"\s+", " ", t).strip()

    def _web_search(self, query: str, k: int = 3) -> str:
        """DuckDuckGo search + read the top pages, returned as a compact context block.
        Best-effort: any failure yields an empty string (chat still answers)."""
        import urllib.parse as _url

        import requests

        try:
            r = requests.post(
                "https://html.duckduckgo.com/html/",
                data={"q": query},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=20,
            )
            r.raise_for_status()
        except Exception:  # noqa: BLE001 — offline / blocked
            return ""
        # result anchors: class="result__a" href="...(maybe /l/?uddg=<encoded>)"
        hits = re.findall(
            r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', r.text, re.S
        )
        seen: set[str] = set()
        results = []
        for href, title in hits:
            if "uddg=" in href:  # DDG redirect → decode real url
                q = _url.parse_qs(_url.urlparse(href).query).get("uddg", [""])[0]
                href = _url.unquote(q) or href
            if not href.startswith("http") or href in seen:
                continue
            seen.add(href)
            results.append((href, self._strip_html(title)))
            if len(results) >= k:
                break
        if not results:
            return ""
        blocks = []
        for href, title in results:
            body = ""
            try:
                pg = requests.get(href, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
                if pg.ok:
                    body = self._strip_html(pg.text)[:2500]
            except Exception:  # noqa: BLE001
                body = "(could not fetch)"
            blocks.append(f"[{title}]\n{href}\n{body}")
        return "\n\n".join(blocks)

    def _fetch_urls(self, urls: list[str]) -> str:
        """Fetch the given URLs and return their readable text (for pasted links)."""
        import requests

        blocks = []
        for u in urls[:3]:
            try:
                pg = requests.get(u, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
                body = self._strip_html(pg.text)[:3000] if pg.ok else f"(HTTP {pg.status_code})"
            except Exception as e:  # noqa: BLE001
                body = f"(could not fetch: {e})"
            blocks.append(f"{u}\n{body}")
        return "\n\n".join(blocks)

    # ---------- main turn ----------
    def send(
        self,
        text: str,
        attachments: list[dict] | None = None,
        editor: dict | None = None,
        run_error: str | None = None,
        web: bool = False,
    ) -> dict[str, Any]:
        self._ensure()
        self._cancel.clear()  # fresh turn — clear any prior Stop
        context = self._context_from_attachments(attachments or [])
        user_content = text or ""
        # The script currently open in the editor — so the model debugs THAT, not a guess.
        script = ""
        if editor and (editor.get("content") or "").strip():
            path = editor.get("path") or "current.nlt"
            script = editor["content"].strip()
            user_content += f"\n\n=== CURRENT SCRIPT ({path}) ===\n{script}"
            # Feed back the ACTUAL artifacts the script reads/writes (e.g. the fetched
            # HTML and the empty output file) so the model can see WHY output is wrong
            # instead of re-guessing selectors.
            produced = self._referenced_files(script)
            if produced:
                user_content += "\n\n=== PRODUCED / REFERENCED FILES ===\n" + produced
        # The most recent run failure(s), fed back so the model can fix the real error.
        if run_error and run_error.strip():
            user_content += "\n\n=== LAST RUN ERROR ===\n" + run_error.strip()
        if context:
            user_content += "\n\n=== ATTACHED CONTEXT ===\n" + context
        # Pasted URLs → fetch them directly and inline their text.
        urls = re.findall(r'https?://[^\s)>\]"\']+', text or "")
        if urls:
            fetched = self._fetch_urls(urls)
            if fetched:
                user_content += "\n\n=== FETCHED PAGES (pasted links) ===\n" + fetched
        # Web search when the 🌐 toggle is on, or the user asks to look something up.
        if web or self._needs_web(text or ""):
            results = self._web_search(text)
            if results:
                user_content += (
                    "\n\n=== WEB SEARCH RESULTS (use these facts; cite nothing verbatim, "
                    "summarize) ===\n" + results
                )
        self.history.append({"role": "user", "content": user_content})

        system = _SYSTEM.replace("{backend_reference}", self._reference)
        prompt = system + "\n\n"
        for m in self.history[-24:]:
            tag = "USER" if m["role"] == "user" else "ASSISTANT"
            prompt += f"{tag}: {m['content']}\n\n"
        prompt += "ASSISTANT:"

        # Call Ollama directly (raw): LLMClient.complete() strips ``` fences, which
        # would destroy the .nlt code block we need to keep and extract.
        reply, truncated, cancelled = self._complete_raw(prompt)
        reply = reply.strip()
        if cancelled:
            # User pressed Stop — don't pollute history with the partial answer.
            return {"reply": "⏹ Richiesta interrotta.", "nlt": "", "stopped": True}
        self.history.append({"role": "assistant", "content": reply})
        nlt = self._extract_nlt(reply)
        if truncated:
            reply += (
                "\n\n⚠ Output troncato al limite di token — lo script potrebbe essere "
                "incompleto. Scrivi \"continua\" per farmi generare il resto."
            )
        return {"reply": reply, "nlt": nlt}

    def _complete_raw(self, prompt: str) -> tuple[str, bool, bool]:
        """Return (text, truncated, cancelled). Streams so Stop can abort mid-answer."""
        import json as _json
        import re as _re

        import requests

        cfg = self._cfg
        payload = {
            "model": cfg.model_for_responses,
            "prompt": prompt,
            "stream": True,
            # num_ctx must hold the whole system prompt + backend reference + history,
            # otherwise Ollama silently truncates from the FRONT and the model replies
            # with garbage (e.g. a bare ```). The reference alone is ~5-6k tokens.
            # num_predict is the OUTPUT cap: too small truncates a big script mid-line
            # (the ```nlt fence never closes) and it looks like a hang — keep it high.
            "options": {"temperature": 0.2, "num_predict": 16384, "num_ctx": 40960},
        }
        parts: list[str] = []
        truncated = False
        with requests.post(
            cfg.llm_generate_url(), json=payload, stream=True,
            timeout=cfg.request_timeout_s,
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if self._cancel.is_set():
                    # Leaving the context closes the connection → Ollama stops generating.
                    return "".join(parts), False, True
                if not line:
                    continue
                try:
                    d = _json.loads(line)
                except Exception:  # noqa: BLE001
                    continue
                parts.append(d.get("response", "") or "")
                if d.get("done"):
                    truncated = d.get("done_reason") == "length"
        text = "".join(parts)
        return _re.sub(r"<think>.*?</think>", "", text, flags=_re.DOTALL), truncated, False

    #: an untagged fenced block is only a SCRIPT if it starts like one (a @directive or
    #: BEGIN_PYTHON) — otherwise it is prose/markdown the user wanted to read, not run.
    _LOOKS_LIKE_SCRIPT = re.compile(r"^\s*(@\w+|BEGIN_PYTHON|INCLUDE\b)", re.I)

    @classmethod
    def _extract_nlt(cls, reply: str) -> str:
        # Explicit ```nlt fence — always a script.
        m = re.search(r"```nlt\s*\n(.*?)```", reply, re.S)
        if m:
            return cls._sanitize_nlt(m.group(1).strip())
        m = re.search(r"```nlt\s*\n(.*)$", reply, re.S)  # truncated ```nlt
        if m and m.group(1).strip():
            return cls._sanitize_nlt(m.group(1).strip())
        # Untagged / other-language fence: only treat as a script if the content
        # actually looks like one (starts with @directive or BEGIN_PYTHON). A Markdown
        # document in a bare ``` block is NOT a script.
        for body in re.findall(r"```[^\n]*\n(.*?)```", reply, re.S):
            if cls._LOOKS_LIKE_SCRIPT.match(body):
                return cls._sanitize_nlt(body.strip())
        return ""

    @staticmethod
    def _sanitize_nlt(text: str) -> str:
        """Fix common model mistakes around BEGIN_PYTHON blocks: an `@allow` line
        placed INSIDE the block (a Python syntax error) is hoisted to just before it,
        and a duplicated `BEGIN_PYTHON` opener is dropped. Everything else untouched."""
        src = text.split("\n")
        out: list[str] = []
        i, n = 0, len(src)
        while i < n:
            line = src[i]
            if line.strip() == "BEGIN_PYTHON":
                body: list[str] = []
                allows: list[str] = []
                j = i + 1
                while j < n and src[j].strip() != "END_PYTHON":
                    s = src[j].strip()
                    if s.startswith("@allow"):
                        allows.append(s)
                    elif s == "BEGIN_PYTHON":
                        pass  # drop a duplicate opener the model emitted
                    else:
                        body.append(src[j])
                    j += 1
                for a in allows:                      # hoist allows before the block
                    if a not in out[-3:]:
                        out.append(a)
                out.append("BEGIN_PYTHON")
                out.extend(body)
                out.append("END_PYTHON")
                i = j + 1                              # skip the END_PYTHON we re-added
                continue
            out.append(line)
            i += 1
        return "\n".join(out)
