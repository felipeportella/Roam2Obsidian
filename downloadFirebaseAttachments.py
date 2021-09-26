# Modified from: https://nicolevanderhoeven.com/blog/20210602-downloading-files-from-roam/

import pathlib
import re
import sys

import requests
from tqdm.auto import tqdm

def downloadFirebaseAttachments(vault_dir, attachments_subdir='attachments', shortpath_mode=True):

    vault_dir = pathlib.Path(vault_dir)
    if not vault_dir.exists():
        print(f"No vault directory exists at '{vault_dir}'.")
        return

    attachments_subdir = vault_dir / attachments_subdir
    attachments_subdir.mkdir(exist_ok=True)

    firebase_attachment_pat = re.compile(r'https://firebasestorage.googleapis.com/[\w+~%/._-]+%2F([\w._-]+)\?[\w&=+~%/._-]+')

    markdown_files_in_vault = list(vault_dir.glob('**/*.md'))
    for file in tqdm(markdown_files_in_vault):

        with file.open() as f:
            original_text = f.read()

        num_expected_matches = original_text.count('https://firebasestorage.googleapis.com')
        matches = list(re.finditer(firebase_attachment_pat, original_text))

        if len(matches) != num_expected_matches:
            print(f"\nSeems like the regex for Firebase attachements missed a match in file '{file}'.")

        if not matches:
            continue

        new_text = original_text

        for match in matches:

            full_url = match.group(0)
            attachment_name = match.group(1)

            attachment_file = attachments_subdir / attachment_name

            if attachment_file.exists():
                print(f"Skipping existing attachment '{attachment_file}'.")

            else:
                print(f"Downloading '{attachment_file}'... ", end="", flush=True)
                request = requests.get(full_url)
                print("done.")

                with attachment_file.open('wb') as f:
                    f.write(request.content)

            if shortpath_mode:
                new_link = attachment_file.parts[-1]
            else:
                new_link = attachment_file.relative_to(vault_dir)

            new_text = new_text.replace(full_url, new_link)

        print(f"Replacing links in '{file}'.")
        print()
        with file.open('w') as f:
            f.write(new_text)

    print("All done!")


if __name__ == '__main__':
    downloadFirebaseAttachments(vault_dir=sys.argv[1])
