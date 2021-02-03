import sys
import os
import json
from tqdm import tqdm
import re
from dateutil.parser import parse
from datetime import datetime

from icecream import ic
ic.configureOutput(includeContext=True)

YAML = """---
title: {title}
created: {created}
---

"""

months = r"January|February|March|April|May|June|July|August|September|October|November|December"

# fr"() is a combination of f-string and raw strings
# escape literal braces in f-string: https://stackoverflow.com/a/5466478/6908282
re_daily = re.compile(fr"({months}) ([0-9]+)[a-z]{{2}}, ([0-9]{{4}})")
re_daylink = re.compile(fr"(\[\[)([{months} [0-9]+[a-z]{{2}}, [0-9]{{4}})(\]\])")
re_blockmentions = re.compile(r"({{mentions: \(\()(.{9})(\)\)}})")
re_blockembed = re.compile(r"({{embed: \(\()(.{9})(\)\)}})")
re_blockref = re.compile(r"(\(\()(.{9})(\)\))")
re_HTML = re.compile("(?<!`)<(?!\s|-).+?>(?!`)")
# Reference to above Regex: https://regex101.com/r/BVWwGK/10

def scan(jdict, page):
    u2b = {jdict["uid"]: jdict}
    for child in jdict.get("children", []):
        child["page"] = page
        u2b.update(scan(child, page))
    return u2b


def fence_HTMLtags(string):
    # Reference: https://regex101.com/r/BVWwGK/10
    if not string.startswith("```"):
        # \g<0> stands for whole match - so we're adding backtick (`) as suffix and prefix for whole match
        # reference: https://docs.python.org/3/library/re.html#re.sub
        # \g<0> instead of \0 - reference: https://stackoverflow.com/q/58134893/6908282
        string = re.sub(re_HTML, r"`\g<0>`", string)
    return string


def replace_daylinks(s):
    new_s = s
    while True:
        m = re_daylink.search(new_s)
        if not m:
            break

        head = new_s[: m.end(1)]
        dt = parse(m.group(2))
        replacement = dt.isoformat()[:10]
        tail = "]]" + new_s[m.end(0) :]
        new_s = head + replacement + tail

    return new_s


def replace_blockrefs(s, uid2block, referenced_uids, broken_uids=None):
    new_s = s
    while True:

        m = re_blockembed.search(new_s) or \
            re_blockmentions.search(new_s) or \
            re_blockref.search(new_s) or None

        if m is None:
            break

        uid = m.group(2)

        if uid not in uid2block:
            if broken_uids is not None:
                broken_uids.add(uid)
            break

        referenced_uids.add(uid)
        head = new_s[: m.start(1)]
        r_block = uid2block[uid]
        # shall we replace with the text or the link or both
        replacement = ""
        # replacement = r_block['string']
        replacement += f' ![[{r_block["page"]["title"]}#^{r_block["uid"].replace("_", "-")}]]'
        tail = new_s[m.end(3) :]
        new_s = head + replacement + tail

    return replace_daylinks(new_s)


def expand_children(block,
                    uid2block,
                    referenced_uids,
                    *,
                    level=0,
                    prev_block_is_header=False,
                    broken_uids=None):
    lines = []
    for child_block in block.get("children", []):

        prefix = ""
        postfix = ""
        block_content = child_block["string"]

        # parse heading level
        headinglevel = child_block.get("heading")
        if headinglevel:
            is_header = True
            prefix = "#" * headinglevel + " "
        else:
            is_header = False
            # the indentation should reflect the nesting level of each block
            level = level if not prev_block_is_header else 0
            prefix = "  " * level
            if not block_content.startswith("```"):
                prefix += "- "
                if '\n' in block_content:
                    bc = block_content.split('\n') # split the multi-line block
                    bc_rest = [" " * len(prefix) + x for x in bc[1:]] # prepend the correct number of whitespaces to the lines except the 1st
                    bc = bc[:1] # the first line of a multi-line block AS A LIST
                    bc.extend(bc_rest)
                    block_content = '\n'.join(bc)

        uid = child_block["uid"]
        if uid in referenced_uids:
            postfix = f' ^{uid.replace("_", "-")}' + postfix

        # multi-line code blocks
        if block_content.startswith("```"):
            block_content = block_content[:-3] + "\n```\n"

        # b id magic
        block_content = prefix + replace_blockrefs(block_content, uid2block, referenced_uids, broken_uids) + postfix

        block_content = fence_HTMLtags(block_content)
        lines.append(block_content)
        lines.extend(expand_children(child_block,
                                     uid2block,
                                     referenced_uids,
                                     level=level + 1,
                                     prev_block_is_header=is_header,
                                     broken_uids=broken_uids))
    return lines


def run():
    j = json.load(open(sys.argv[1], mode="rt", encoding="utf-8", errors="ignore"))

    odir = "md"
    ddir = "md/daily"
    os.makedirs(ddir, exist_ok=True)

    print("Pass 1: scan all pages")

    uid2block = {}
    referenced_uids = set()
    pages = []
    broken_uids = set()

    for page in tqdm(j):
        title = page["title"]
        if 'edit-time' in page.keys():
            created = page.get('create-time', page['edit-time'])
        else:
            created = page.get('create-time', page['children'][0]['edit-time'])
        created = datetime.fromtimestamp(created / 1000).isoformat()[:10]
        children = page.get("children") or []

        is_daily = False
        m = re_daily.match(title)
        if m:
            is_daily = True
            dt = parse(title)
            title = dt.isoformat().split("T")[0]

        page = {
            "uid": None,
            "title": title,
            "created": created,
            "children": children,
            "daily": is_daily,
        }

        uid2block.update(scan(page, page))
        pages.append(page)

    print("Pass 2: track blockrefs")

    for p in tqdm(pages):
        expand_children(p, uid2block, referenced_uids, broken_uids=broken_uids)

    if broken_uids:
        print("************************************")
        print("WARNING: there were broken backrefs!")
        print(*broken_uids, sep=', ')
        print("************************************")

    print("Pass 3: generate")

    error_pages = []

    for p in tqdm(pages):
        title = p["title"]
        if not title:
            continue
        ofiln = f'{odir}/{p["title"]}.md'
        if p["daily"]:
            ofiln = f'{ddir}/{p["title"]}.md'

        # hack for crazy slashes in titles
        if "/" in title:
            d = odir
            for part in title.split("/")[:-1]:
                d = os.path.join(d, part)
                os.makedirs(d, exist_ok=True)

        lines = expand_children(p, uid2block, referenced_uids)
        try:
            with open(ofiln, mode="wt", encoding="utf-8") as f:
                f.write(YAML.format(**p))
                f.write("\n".join(lines))
        except:
            error_pages.append({"page": p, "content": lines})

    if error_pages:
        print("The following pages had errors:")
        for ep in error_pages:
            page = ep["page"]
            title = page["title"]
            content = ep["content"]
            print(f"Title: >{title}<")
            print(f"Content:")
            print("    " + "\n    ".join(content))
    print("Done!")

if __name__ == "__main__":
    run()
