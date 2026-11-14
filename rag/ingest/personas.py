"""Generate the synthetic persona corpus (data/personas/<persona_id>/) from scripts/persona_specs.yaml.

Outputs per persona: profile.json, cv.md, cv.pdf, case_studies/*.md, repos/<repo>/..., reviews.jsonl,
index.jsonl (catalogue of every evidence item; proposals are appended later by label_proposals.py).
"""
from __future__ import annotations

import ast
import json
import re
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import yaml

from rag.ingest.common import (GEN_MODELS, PERSONAS_DIR, generator, load_specs, stable_int,
                               word_count, write_jsonl)
from rag.ingest.llm import chat_fallback, chat_json, parse_json, print_session_usage

PV = "persona_v1"
SYSTEM = ("You write realistic portfolio material for a freelancer. This is SYNTHETIC data for a "
          "university project about retrieval-augmented proposal writing. Invent plausible detail, "
          "but never contradict the facts you are given, never invent other employers, and keep every "
          "date, client name and number exactly as given. Reply with a single JSON object only.")


def persona_brief(p: dict) -> str:
    emp = "; ".join(f"{e['role']} at {e['name']} ({e['start']} to {e['end']})" for e in p["employers"])
    return (f"Freelancer: {p['name']}, {p['title']}. {p['years_experience']} years of experience. "
            f"Career: {emp}. Niches: {', '.join(p['niches'])}. Writing voice: {p['voice']}.")


def _layout(seed: int) -> str:
    return ["three short headed sections (e.g. 'The problem', 'What I did', 'Results') in markdown",
            "a flowing narrative of 4-6 paragraphs with no headings",
            "a short intro paragraph, then 'Challenge', 'Approach' and 'Impact' as bold labels with "
            "a mix of bullets and prose",
            "a client-story style: who they were, what was hurting, how we fixed it, what changed, "
            "with one or two markdown subheadings"][seed % 4]


# ----------------------------------------------------------------------------- case studies
GENERIC_STACK = {"python", "sql", "tool calling", "survey weighting", "excel", "typescript", "react", "node.js"}


def named_tools(text: str, stack: list[str]) -> list[str]:
    """Stack entries (product names) that literally appear in the text."""
    low = text.lower()
    hits = []
    for t in stack:
        if t.lower() in GENERIC_STACK:
            continue
        key = t.lower().split(" (")[0]
        variants = {key, key.split()[0]} if len(key.split()[0]) > 3 and key.split()[0] not in {"apache", "openai", "shopify", "stripe", "hugging", "google", "sql"} else {key}
        if any(re.search(r"(?<![\w-])" + re.escape(v) + r"(?![\w-])", low) for v in variants):
            hits.append(t)
    return hits


def case_study_task(pid: str, p: dict, item: dict, minor: bool) -> dict:
    eid = f"{pid}:case:{item['slug']}"
    seed = stable_int(eid)
    lo, hi = (250, 420) if minor else (330, 600)
    if minor:
        facts = (f"Project: {item['title']}\nClient industry: {item['client_industry']}\nDate: {item['date']}\n"
                 f"Skills involved: {', '.join(item['skills'])}\nOutcome: {item['outcome']}\n"
                 + ("This gig is OUTSIDE the freelancer's main niche; say so casually (a favour, a one-off, "
                    "a side job).\n" if item.get("off_niche") else ""))
        style = ("Invent a modest, believable small-gig story. Name at most one specific tool, once. "
                 "Avoid buzzwords.")
    else:
        employer = item["client"] if item["client"] in [e["name"] for e in p["employers"]] else None
        facts = (f"Project: {item['title']}\nClient: {item['client']} ({item['client_industry']})"
                 + (" - this was the freelancer's EMPLOYER at the time, not a freelance client" if employer else "")
                 + f"\nDate: {item['date']}\nOutcome (use these numbers exactly): {item['outcome']}\n"
                 f"Tools actually used (internal fact sheet): {', '.join(item['stack'])}\n"
                 f"Describe the work using phrasing like: {' | '.join(item['implied'])}\n")
        style = ("IMPORTANT style rules, so the text is realistic and a little messy:\n"
                 "- Describe techniques by what they DO, not by product names. Name at most TWO tools from the "
                 "fact sheet, each in a single sentence only. Never list the stack, never put tool names in parentheses.\n"
                 "- Use your own vocabulary for the domain (synonyms, business framing), not the project title's words.\n")
    user = (f"{persona_brief(p)}\n\nWrite a portfolio case study in the first person.\n{facts}\n{style}\n"
            f"Layout: {_layout(seed)}.\nLength: {lo}-{hi} words for the body.\n"
            'Return JSON: {"summary": "two plain sentences: what was built and the result", '
            '"body": "the markdown body, without a title line"}')

    def ok(content: str) -> bool:
        d = parse_json(content)
        if not (isinstance(d.get("body"), str) and lo - 60 <= word_count(d["body"]) <= hi + 150 and d.get("summary")):
            return False
        return minor or len(named_tools(d["body"], item["stack"])) <= 2

    data, res = chat_json(GEN_MODELS, [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
                          temperature=0.8, seed=seed, max_tokens=3000, validate=ok)
    return {"kind": "case", "pid": pid, "item": item, "minor": minor, "eid": eid, "seed": seed,
            "model": res["model"], "data": data}


def write_case(out: Path, r: dict) -> dict:
    item, data = r["item"], r["data"]
    fm = {"evidence_id": r["eid"], "title": item["title"],
          "project": item.get("client", "freelance gig") + " - " + item["title"] if not r["minor"] else item["title"],
          "client_industry": item["client_industry"], "date": str(item["date"]), "skills": list(item["skills"]),
          "outcome": item["outcome"], "synthetic": True, "generator": generator(r["model"], PV, r["seed"])}
    body = data["body"].strip()
    body = re.sub(r"^#\s+.*\n+", "", body)  # drop a stray title line
    text = "---\n" + yaml.safe_dump(fm, sort_keys=False, allow_unicode=True) + "---\n\n# " + item["title"] + "\n\n" + body + "\n"
    path = out / "case_studies" / f"{item['slug']}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return {"evidence_id": r["eid"], "type": "case", "title": item["title"], "project_slug": item["slug"],
            "date": str(item["date"]), "path": str(path.relative_to(out)).replace("\\", "/"),
            "summary": data["summary"].strip(), "off_niche": bool(item.get("off_niche", False))}


# ----------------------------------------------------------------------------- repos
LANG_RULES = {
    "python": "Python 3.11 files under src/ (and optionally tests/). Notebooks are written as .py files with '# %%' cells.",
    "typescript": "TypeScript files under src/ (and optionally a package.json and one test file).",
    "sql": "dbt-style SQL models under models/ or plain SQL views under sql/, plus one YAML schema/test file and optionally a small Python helper.",
}


SYSTEM_TEXT = SYSTEM.replace("Reply with a single JSON object only.", "Follow the requested output format exactly.")


def parse_repo(text: str) -> dict:
    parts = re.split(r"^=== (SUMMARY|FILE: [^=\n]+?) ===[ \t]*$", text.strip(), flags=re.M)
    out: dict = {"summary": "", "readme": "", "files": []}
    for tag, body in zip(parts[1::2], parts[2::2]):
        body = body.strip("\n")
        body = re.sub(r"^```[\w-]*\n", "", body)
        body = re.sub(r"\n```\s*$", "", body).strip("\n")
        if tag == "SUMMARY":
            out["summary"] = body.strip()
        else:
            path = tag[len("FILE: "):].strip()
            if path.lower() == "readme.md":
                out["readme"] = body
            else:
                out["files"].append({"path": path, "content": body})
    return out


def repo_task(pid: str, p: dict, proj: dict) -> dict:
    repo = proj["repo"]
    eid = f"{pid}:repo:{repo['slug']}"
    seed = stable_int(eid)
    if repo["vague_readme"]:
        readme_rule = ("README: VAGUE on purpose, 2-4 sentences, e.g. 'Bits from a client job. Run the main "
                       "script.' Do NOT name the client, the domain, the tools or what problem it solves. "
                       "The code itself must make the purpose obvious.")
    else:
        readme_rule = ("README: clear and useful (purpose, how it works in a few bullets, setup, usage). Refer to "
                       "the client only anonymously (e.g. 'a legal-tech client'). Mention at most two tool names.")
    user = (f"{persona_brief(p)}\n\nCreate a small but real-looking code repository '{repo['slug']}' extracted from "
            f"this project:\nProject: {proj['title']} for {proj['client']} ({proj['client_industry']}), {proj['date']}.\n"
            f"What it did: {' | '.join(proj['implied'])}. Outcome: {proj['outcome']}.\n"
            f"Tools: {', '.join(proj['stack'])} - the code must import / use these libraries by name where natural.\n"
            f"Language rules: {LANG_RULES[repo['lang']]}\n{readme_rule}\n"
            "Code rules: 3-5 files, 120-320 lines of code in total, idiomatic, with docstrings or comments, no secrets "
            "(read config from environment variables), no real company data, no placeholder 'TODO' stubs for the core logic.\n"
            "Output format (plain text, NOT JSON, no markdown code fences around files), using exactly these "
            "delimiter lines:\n"
            "=== SUMMARY ===\n<two plain sentences describing what the code actually does, for an index>\n"
            "=== FILE: README.md ===\n<readme>\n=== FILE: src/<name> ===\n<code>\n"
            "(one '=== FILE: <path> ===' block per file)")

    def ok(content: str) -> bool:
        d = parse_repo(content)
        files = d.get("files") or []
        if not (3 <= len(files) <= 7) or not d.get("readme") or not d.get("summary"):
            return False
        for f in files:
            if not f.get("path") or not f.get("content") or ".." in f["path"]:
                return False
            if f["path"].endswith(".py"):
                ast.parse(f["content"])
        return True

    res = chat_fallback(GEN_MODELS, [{"role": "system", "content": SYSTEM_TEXT}, {"role": "user", "content": user}],
                        temperature=0.5, seed=seed, max_tokens=7000, validate=ok)
    data = parse_repo(res["content"])
    return {"kind": "repo", "pid": pid, "item": proj, "eid": eid, "seed": seed, "model": res["model"], "data": data}


VAGUE_READMES = [
    "Bits from a client job. Run the main script.",
    "# {slug}\n\nOld project, tidied up a little. Config comes from env vars. Not maintained.",
    "# {slug}\n\nmisc scripts pulled out of a bigger repo - some parts removed. see src/",
    "Internal tool from a past contract. Works on my machine; ask before reusing.",
    "# {slug}\n\nWIP. Notes to self: set the env vars, then run the entry point.",
    "Helper code I keep around. No docs yet, sorry.",
]


def write_repo(out: Path, r: dict) -> dict:
    proj, data = r["item"], r["data"]
    slug = proj["repo"]["slug"]
    root = out / "repos" / slug
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    readme = data["readme"].strip()
    if proj["repo"]["vague_readme"]:
        # the model tends to copy the example sentence verbatim; vary it deterministically
        readme = VAGUE_READMES[stable_int(r["eid"]) % len(VAGUE_READMES)].format(slug=slug)
    (root / "README.md").write_text(readme + "\n", encoding="utf-8")
    paths = []
    for f in data["files"]:
        rel = f["path"].lstrip("/").replace("\\", "/")
        dest = (root / rel).resolve()
        if not str(dest).startswith(str(root.resolve())):
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(f["content"].rstrip() + "\n", encoding="utf-8")
        paths.append(rel)
    meta = {"evidence_id": r["eid"], "project_slug": proj["slug"], "vague_readme": proj["repo"]["vague_readme"],
            "synthetic": True, "generator": generator(r["model"], PV, r["seed"])}
    (root / ".evidence.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return {"evidence_id": r["eid"], "type": "repo", "title": slug, "project_slug": proj["slug"],
            "date": str(proj["date"]), "path": f"repos/{slug}", "files": ["README.md"] + paths,
            "summary": data["summary"].strip(), "vague_readme": proj["repo"]["vague_readme"], "off_niche": False}


# ----------------------------------------------------------------------------- reviews
def _next_month(ym: str) -> str:
    y, m = map(int, str(ym).split("-"))
    m += 1
    if m > 12:
        y, m = y + 1, 1
    return f"{y:04d}-{m:02d}"


def review_items(p: dict) -> list[dict]:
    items = []
    for proj in p["projects"]:
        if proj.get("review"):
            items.append({"slug": proj["slug"], "project": proj["title"], "client": proj["client"],
                          "industry": proj["client_industry"], "date": str(proj["date"]),
                          "outcome": proj["outcome"], **proj["review"]})
    for g in p["minor_gigs"]:
        if g.get("review"):
            items.append({"slug": g["slug"], "project": g["title"], "client": None, "industry": g["client_industry"],
                          "date": str(g["date"]), "outcome": g["outcome"], **g["review"]})
    items.sort(key=lambda x: x["date"])
    return items


def reviews_task(pid: str, p: dict) -> dict:
    items = review_items(p)
    seed = stable_int(pid, "reviews")
    lines = "\n".join(f"- key={it['slug']}; reviewer={it['client_name']}"
                      + (f" ({it['client']})" if it["client"] else "")
                      + f"; industry={it['industry']}; project={it['project']}; outcome={it['outcome']}; rating={it['rating']}"
                      for it in items)
    user = (f"{persona_brief(p)}\n\nWrite one marketplace client review per line below, in the CLIENT's voice.\n{lines}\n\n"
            "Rules: 25-110 words each; vary length and tone; clients describe the business result in their own words "
            "and almost never use technical tool names (say 'the dashboard', 'the new system', 'the bot'); refer to the "
            "project in different words than its title; a rating of 3 or 4 must include a concrete, believable "
            "complaint (timeline slipped, communication gaps, scope confusion). Some reviews mention the freelancer by "
            "first name, some don't.\n"
            'Return JSON: {"reviews": [{"key": "...", "text": "..."}]} with exactly one entry per key.')

    def ok(content: str) -> bool:
        d = parse_json(content)
        keys = {x.get("key") for x in d.get("reviews", [])}
        return keys >= {it["slug"] for it in items}

    data, res = chat_json(GEN_MODELS, [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
                          temperature=0.8, seed=seed, max_tokens=5000, validate=ok)
    return {"kind": "reviews", "pid": pid, "items": items, "seed": seed, "model": res["model"], "data": data}


def write_reviews(out: Path, r: dict) -> list[dict]:
    names = {it["slug"]: it["client_name"] for it in r["items"]}
    texts = {}
    for x in r["data"]["reviews"]:
        t = x["text"].strip()
        nm = names.get(x["key"], "")
        if nm and t.startswith(nm):   # the model sometimes prefixes "Name (Company):"
            t = re.sub(r"^" + re.escape(nm) + r"\s*(\([^)]*\))?\s*[:\-–—]\s*", "", t)
        texts[x["key"]] = t
    rows, idx = [], []
    for i, it in enumerate(r["items"], start=1):
        eid = f"{r['pid']}:review:{i:03d}"
        day = 3 + stable_int(eid) % 25
        row = {"evidence_id": eid, "client_name": it["client_name"], "project": it["project"],
               "project_slug": it["slug"], "rating": int(it["rating"]), "text": texts[it["slug"]],
               "date": f"{_next_month(it['date'])}-{day:02d}", "synthetic": True,
               "generator": generator(r["model"], PV, r["seed"])}
        rows.append(row)
        idx.append({"evidence_id": eid, "type": "review", "title": f"Review from {it['client_name']}: {it['project']}",
                    "project_slug": it["slug"], "date": row["date"], "path": "reviews.jsonl",
                    "summary": f"{it['rating']}-star client review. " + texts[it["slug"]][:160],
                    "off_niche": False})
    write_jsonl(out / "reviews.jsonl", rows)
    return idx


# ----------------------------------------------------------------------------- CV + profile
def cv_task(pid: str, p: dict) -> dict:
    seed = stable_int(pid, "cv")
    emp_names = {e["name"] for e in p["employers"]}

    def fmt(x):
        return f"- {x['date']} {x['title']} for {x['client']} ({x['client_industry']}): {x['outcome']}; tools: {', '.join(x['stack'])}"

    projs = ("Done while EMPLOYED (mention only under that employer, never in the freelance section):\n"
             + "\n".join(fmt(x) for x in p["projects"] if x["client"] in emp_names)
             + "\nFREELANCE projects (the ONLY ones allowed under 'Selected freelance projects'):\n"
             + "\n".join(fmt(x) for x in p["projects"] if x["client"] not in emp_names))
    emp = "\n".join(f"- {e['role']}, {e['name']}, {e['start']} to {e['end']}: {e['summary']}" for e in p["employers"])
    user = (f"Write the CV and marketplace bio of {p['name']} ({p['title']}, {p['location']}).\n"
            f"Employment (use exactly):\n{emp}\nProjects:\n{projs}\nEducation: {p['education']}\n"
            f"Skills: {', '.join(p['skills'])}\nVoice: {p['voice']}\n\n"
            "CV rules: markdown; '# Name' then a one-line title; sections Summary, Experience (newest first, "
            "3-5 bullets per role, results with numbers), Selected freelance projects (4-6), Skills, Education. "
            "450-750 words. Plain ASCII punctuation.\n"
            "Bio rules: 80-130 words, first person, the marketplace profile overview.\n"
            'Return JSON: {"bio": "...", "cv_markdown": "..."}')

    def ok(content: str) -> bool:
        d = parse_json(content)
        return 350 <= word_count(d.get("cv_markdown", "")) <= 1000 and 60 <= word_count(d.get("bio", "")) <= 180

    data, res = chat_json(GEN_MODELS, [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
                          temperature=0.6, seed=seed, max_tokens=4000, validate=ok)
    return {"kind": "cv", "pid": pid, "seed": seed, "model": res["model"], "data": data}


_ASCII = {"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", "•": "-",
          "…": "...", "‑": "-", "‐": "-", " ": " ", "→": "->", "↑": "up ", "↓": "down ","−": "-", "×": "x", "≥": ">=", "≤": "<="}


def _latin1(s: str) -> str:
    for k, v in _ASCII.items():
        s = s.replace(k, v)
    return s.encode("latin-1", "replace").decode("latin-1")


def render_cv_pdf(md: str, path: Path) -> None:
    from fpdf import FPDF

    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_margins(18, 15, 18)
    w = pdf.w - pdf.l_margin - pdf.r_margin
    for raw in md.splitlines():
        line = _latin1(raw.rstrip())
        if not line.strip():
            pdf.ln(2)
            continue
        m = re.match(r"^(#{1,4})\s+(.*)", line)
        if m:
            level = len(m.group(1))
            size = {1: 18, 2: 13, 3: 11.5, 4: 11}[level]
            pdf.set_font("Helvetica", "B", size)
            pdf.ln(2 if level > 1 else 0)
            pdf.multi_cell(w, size * 0.5, m.group(2).replace("**", ""), new_x="LMARGIN", new_y="NEXT")
            if level == 2:
                y = pdf.get_y()
                pdf.line(pdf.l_margin, y, pdf.l_margin + w, y)
                pdf.ln(1)
            continue
        pdf.set_font("Helvetica", "", 10)
        b = re.match(r"^\s*[-*]\s+(.*)", line)
        if b:
            pdf.set_x(pdf.l_margin + 4)
            pdf.multi_cell(w - 4, 5, "- " + b.group(1), markdown=True, new_x="LMARGIN", new_y="NEXT")
        else:
            pdf.multi_cell(w, 5, line, markdown=True, new_x="LMARGIN", new_y="NEXT")
    pdf.output(str(path))


# ----------------------------------------------------------------------------- main
def build(only: list[str] | None = None, workers: int = 3) -> None:
    specs = load_specs()
    pids = only or list(specs)
    tasks = []
    for pid in pids:
        p = specs[pid]
        tasks.append((cv_task, (pid, p)))
        tasks.append((reviews_task, (pid, p)))
        for proj in p["projects"]:
            if proj.get("repo"):
                tasks.append((repo_task, (pid, p, proj)))
            if proj.get("case_study", True):
                tasks.append((case_study_task, (pid, p, proj, False)))
        for g in p["minor_gigs"]:
            tasks.append((case_study_task, (pid, p, g, True)))
    print(f"persona generation: {len(tasks)} LLM tasks for {pids}", flush=True)
    results: dict[str, list[dict]] = {pid: [] for pid in pids}
    failures = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(fn, *args): (fn.__name__, args[0], (args[2].get("slug") if len(args) > 2 else "")) for fn, args in tasks}
        for i, fut in enumerate(as_completed(futs), 1):
            name = futs[fut]
            try:
                r = fut.result()
                results[r["pid"]].append(r)
                print(f"  [{i}/{len(tasks)}] {name[0]} {name[1]} {name[2]} ok ({r['model']})", flush=True)
            except Exception as e:  # noqa: BLE001
                failures.append((name, repr(e)))
                print(f"  [{i}/{len(tasks)}] {name} FAILED: {e!r}", flush=True)
    if failures:
        print_session_usage()
        raise SystemExit(f"{len(failures)} persona tasks failed; rerun to resume from cache")

    for pid in pids:
        p = specs[pid]
        out = PERSONAS_DIR / pid
        for sub in ("case_studies", "repos"):
            if (out / sub).exists():
                shutil.rmtree(out / sub)
        out.mkdir(parents=True, exist_ok=True)
        index: list[dict] = []
        rs = results[pid]
        cv = next(r for r in rs if r["kind"] == "cv")
        cv_md = cv["data"]["cv_markdown"].strip() + "\n"
        (out / "cv.md").write_text(cv_md, encoding="utf-8")
        render_cv_pdf(cv_md, out / "cv.pdf")
        index.append({"evidence_id": f"{pid}:cv:main", "type": "cv", "title": f"CV of {p['name']}",
                      "project_slug": None, "date": None, "path": "cv.md",
                      "summary": f"{p['title']}; {p['years_experience']} years; employers: "
                                 + ", ".join(e["name"] for e in p["employers"]), "off_niche": False})
        profile = {"persona_id": pid, "name": p["name"], "title": p["title"], "hourly_rate": p["hourly_rate"],
                   "skills": p["skills"], "years_experience": p["years_experience"], "industries": p["industries"],
                   "bio": cv["data"]["bio"].strip(), "location": p["location"], "niches": p["niches"],
                   "gigsim_account_id": p["gigsim_account_id"], "synthetic": True,
                   "generator": generator(cv["model"], PV, cv["seed"])}
        (out / "profile.json").write_text(json.dumps(profile, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        for r in sorted((r for r in rs if r["kind"] == "case"), key=lambda r: str(r["item"]["date"])):
            index.append(write_case(out, r))
        for r in sorted((r for r in rs if r["kind"] == "repo"), key=lambda r: r["eid"]):
            index.append(write_repo(out, r))
        rv = next(r for r in rs if r["kind"] == "reviews")
        index.extend(write_reviews(out, rv))
        # keep any proposal rows that label_proposals.py appended earlier
        old = PERSONAS_DIR / pid / "index.jsonl"
        if old.exists():
            index.extend(json.loads(line) for line in old.read_text(encoding="utf-8").splitlines()
                         if line.strip() and json.loads(line).get("type") == "proposal")
        write_jsonl(out / "index.jsonl", index)
        counts = {t: sum(1 for x in index if x["type"] == t) for t in ("cv", "case", "repo", "review", "proposal")}
        print(f"{pid}: {counts}")
    print_session_usage()
