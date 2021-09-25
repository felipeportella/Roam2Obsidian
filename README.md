# Changelog

## Fixes w.r.t repository [edoardob90/Roam2Obsidian](https://github.com/edoardob90/Roam2Obsidian)

I tried go through all the PRs and forks of the original [renerocksai/rj2obs](https://github.com/renerocksai/rj2obs) repo to bring together all the changes from other people.

- [AnweshGangula/Roam2Obsidian](https://github.com/AnweshGangula/Roam2Obsidian) seemed like the best one to base off of.
- Then I cherry-picked [867def9](https://github.com/lkhphuc/rj2obs/commit/867def9d90f1a83928445cf6f7400ce13dca9783) from [lkhphuc/rj2obs](https://github.com/lkhphuc/rj2obs).
- I didn’t need to incorporate anything from [matthewwong525/rj20bs](https://github.com/matthewwong525/rj2obs/commits/main) or any of the other PRs or forks or forks of forks as of September 2021.

Don’t forget to run Obsidian's Markdown importer after this conversion. It will fix #tag links and formattings (todo syntax, highlights, etc).


## Fixes w.r.t. repository [AnweshGangula/Roam2Obsidian](https://github.com/AnweshGangula/Roam2Obsidian):

- [x] Handles broken Roam block references
- [x] Change to the formatting of multi-line blocks
- [ ] Fix code-blocks references: they don't seem to work with Obsidian's embed syntax


## Fixes w.r.t. repository [renerocksai/rj2obs](https://github.com/renerocksai/rj2obs):

* Convert code-blocks into proper markdown code-blocks
* enclose any html tags in backtics so that they are not rendered by obsidian - eg: `` `<br>` ``
* replace any underscore(`_`) in the UID of a block with hyphen(-) as obsidian doesn't support "`_`" in UID
* Preview Block-Refs by default
    * I have a custom CSS snippet for my Obsidian vault, that style the block-refs to look similar to Roam Research



# Roam JSON To Obsidian Converter

Converts Roam JSON export to Obsidian Markdown files.

I wrote this to convert my own roam export into an Obsidian friendly format.

Output has the following directory structure:

* `md/` : contains all normal Markdown files
* `md/daily/`: contains all daily notes

## Features

* Daily note format is changed to YYYY-MM-DD
* roam's block IDs are appended (only) to blocks actually referenced
    * e.g. `* this block gets referenced  ^someroamid`
* Blockrefs, block mentions, block embeds are replaced by their content with an appended Obsidian blockref link
    * e.g. `this block gets referenced  [[orignote#^someblockid]]`
* All notes are prefixed with a yaml header containing title and creation date:
```yaml
---
title:   
created: YYYY-MM-DD
---

```

* Top level roam blocks that don't contain children are not formatted as list
* Roam blocks containing linebreaks are broken down into multiple bullets
    * roam: 
```markdown

        * line 1
          line 2
        * next block
```
*
    * becomes:
```markdown
        * line 1
        * line 2

        * next block
```

**Note:** Please run Obsidian's Markdown importer after this conversion. It will fix #tag links and formattings (todo syntax, highlights, etc).

I might make it more user friendly and less hardcoded later. It did the job, though.

## Install

No need to install. But you need python3. Google is your friend. 

To install the required python packages:

```bash
pip install -r requirements.txt
```

## Usage

```bash
python r2o.py my-roam-export.json
```

