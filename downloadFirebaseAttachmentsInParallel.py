"""
Downloads firebase files found in markdown files (MD) exported from 
RoamResearch and then replace the original firebase links by a local
one. All in parallel.

Cronological History:
=====================

https://github.com/renerocksai/rj2obs implemented the r2o.py (Roam JSON
to Obsidian Converter).

https://github.com/AnweshGangula/Roam2Obsidian added a few more
additional features (convert code-blocks into proper markdown 
code-blocks etc.)

https://github.com/yatharth/Roam2Obsidian added the download script
of attachments stored on Firebase by Roam, originally inspired by: 
https://nicolevanderhoeven.com/blog/20210602-downloading-files-from-roam/

https://github.com/felipeportella/Roam2Obsidian refactored the code
into more atomic functions and implemented a parallel processing to
analyse the markdown files in parallel and then download in parallel
the files from Firebase. The motivation is that using yatharth as 
Dec/2021 was taking more than 5h to process all my Roam database, and
with the current code took around 5 min. As the changes were consi-
derably I opt to leave the original file and add this one *InParallel.py.
The command line is the same
"""

from multiprocessing import cpu_count
import pathlib
import re
import sys
from typing import Dict

import requests
from joblib import Parallel, delayed
from tqdm.auto import tqdm

# some default values
SIMULTANEOUS_DOWNLOADS = 40
REQUESTS_TIMEOUT = 5

re_firebase_attachment_pat = re.compile(
    r"https://firebasestorage.googleapis.com/[\w+~%/._-]+%2F([\w._-]+)\?[\w&=+~%/._-]+"
)


# The requests.get was hanging after a while, so I followed
# this solution: https://stackoverflow.com/a/61366068/1975192
old_send = requests.Session.send


def new_send(*args, **kwargs):
    if kwargs.get("timeout", None) is None:
        kwargs["timeout"] = REQUESTS_TIMEOUT
    return old_send(*args, **kwargs)


requests.Session.send = new_send


def download_single_file(attachment_file, full_url):
    request = requests.get(full_url, timeout=REQUESTS_TIMEOUT)
    with attachment_file.open("wb") as f:
        f.write(request.content)


def download_in_parallel(download_queue):
    """
    Method that calls in parallel the download_single_file() method, 
    one instance for each link received in the queue. The number of
    parallel threads are defined by the SIMULTANEOUS_DOWNLOADS.
    """
    print(
        f"Starting the download of {len(download_queue)} files in batches of {SIMULTANEOUS_DOWNLOADS} simultaneous downloads ..."
    )
    tqdm_queue = tqdm(
        download_queue.items(), total=len(download_queue), desc="Parallel Downloading "
    )
    Parallel(n_jobs=SIMULTANEOUS_DOWNLOADS)(
        delayed(download_single_file)(k, v) for k, v in tqdm_queue
    )


def find_firebase_links_in_md(md_file):
    """
    Given a markdown file returns all the matches of Firebase links

    Parameters
    ----------

        md_file: pathlib.PosixPath
            the markdown file that should be searched for a Firebase
            link pattern
            

        attachments_subdir: pathlib.PosixPath
            the path where the attachments should be placed (used to 
            verify if the attachment were already donwloaded or not)

    Returns
    -------

        download_queue: dict
            a dict with the attachment name as index and the respective download link

        replace_queue: : dict
            another queue with the links that should be replaced. Its not the
            same as the download as some files could have being downloaded before
            in a incomplete attempt. The index here is the md_file as we later
            will ask one thread to open one file to avoid concurrency.
    """
    with md_file.open() as f:
        original_text = f.read()

    num_expected_matches = original_text.count("https://firebasestorage.googleapis.com")
    matches = list(re.finditer(re_firebase_attachment_pat, original_text))

    if len(matches) != num_expected_matches:
        print(
            f"\nSeems like the regex for Firebase attachements missed a match in file '{md_file}'."
        )

    if not matches:
        return None

    found_links = []
    for match in matches:

        full_url = match.group(0)
        attachment_name = match.group(1)
        found_links.append({attachment_name: full_url})

    return {md_file: found_links}


def prepare_queues_in_parallel(
    markdown_files_in_vault, attachments_subdir, verbose: bool = False
):
    """
    This method will prepare a download and a replace
    list (queues) to be processes later.

    Parameters
    ----------

        markdown_files_in_vault: list of pathlib.PosixPath
            a list of all the markdown files that should be analyzed
            in seach for a Firebase link pattern
            

        attachments_subdir: pathlib.PosixPath
            the path where the attachments should be placed (used to 
            verify if the attachment were already donwloaded or not)

        verbose: bool (Default=False)
            A flag to print addition info (if the download was skipt)

    Returns
    -------

        download_queue: dict
            a dict with the attachment name as index and the respective download link

        replace_queue: : dict
            another queue with the links that should be replaced. Its not the
            same as the download as some files could have being downloaded before
            in a incomplete attempt. The index here is the md_file as we later
            will ask one thread to open one file to avoid concurrency.

    Remarks
    -------

        The find is done in parallel, each thread parsing one file, and with the
        number of cores available in the machine as the number of concurrent jobs.  

    """

    md_files = tqdm(markdown_files_in_vault, desc="Analysing MD files in parallel")
    matches = Parallel(n_jobs=cpu_count())(
        delayed(find_firebase_links_in_md)(f) for f in md_files
    )
    matches = list(filter(None, matches))  # removing the Nones

    download_queue = {}
    replace_queue = {}

    for match in matches:

        for md_file, links in match.items():

            for link in links:

                full_url = list(link.values())[0]
                attachment_name = list(link.keys())[0]

                attachment_file = attachments_subdir / attachment_name

                if attachment_file.exists():
                    if verbose:
                        print(
                            f"Skipping existing attachment '{attachment_file}' from download."
                        )
                else:
                    download_queue[attachment_file] = full_url

                # all matches should be replaced
                if md_file not in replace_queue:
                    replace_queue[md_file] = [{attachment_file: full_url}]
                else:
                    replace_queue[md_file].append({attachment_file: full_url})

    return download_queue, replace_queue


def replace_links_in_md(md_file, links, vault_dir, shortpath_mode):

    with md_file.open() as f:
        original_text = f.read()

    new_text = original_text

    for match in links:

        full_url = list(match.values())[0]
        attachment_file = list(match.keys())[0]

        if shortpath_mode:
            new_link = attachment_file.parts[-1]
        else:
            new_link = attachment_file.relative_to(vault_dir)

        new_text = new_text.replace(full_url, str(new_link))

    with md_file.open("w") as f:
        f.write(new_text)


def replace_links_in_parallel(replace_queue, vault_dir, shortpath_mode):
    """
    Method that calls in parallel the replace_links_in_md() method, 
    one instance for each md_file received in the queue. The number of
    parallel threads are defined by the number of cores available.
    """
    print(
        f"Starting to replace the links in {len(replace_queue)} files in batches of {cpu_count()} ..."
    )
    tqdm_queue = tqdm(
        replace_queue.items(), total=len(replace_queue), desc="Parallel Replacing "
    )

    Parallel(n_jobs=cpu_count())(
        delayed(replace_links_in_md)(k, v, vault_dir, shortpath_mode)
        for k, v in tqdm_queue
    )


def main(vault_dir, attachments_subdir="attachments", shortpath_mode=False):

    vault_dir = pathlib.Path(vault_dir).expanduser()
    if not vault_dir.exists():
        print(f"No vault directory exists at '{vault_dir}'.")
        return

    attachments_subdir = vault_dir / attachments_subdir
    attachments_subdir.mkdir(exist_ok=True)

    markdown_files_in_vault = list(vault_dir.glob("**/*.md"))

    download_queue, replace_queue = prepare_queues_in_parallel(
        markdown_files_in_vault, attachments_subdir
    )

    download_in_parallel(download_queue)

    replace_links_in_parallel(replace_queue, vault_dir, shortpath_mode)

    print("All done!")


if __name__ == "__main__":
    main(vault_dir=sys.argv[1])
