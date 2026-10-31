"""Write the free-plan site using the same page renderer as the Python server."""
import os
import shutil

os.environ["REPLAY_ENABLED"] = "false"

from foxscanner.paths import FRONTEND_DIR
from foxscanner.server import ICONS, PAGE_META, render_site_page, versioned

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public")


def main():
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    shutil.copytree(os.path.join(FRONTEND_DIR, "static"), os.path.join(OUT, "static"))
    for name in PAGE_META:
        if name == "replay.html":
            continue
        body = versioned(render_site_page(os.path.join(FRONTEND_DIR, name)))
        with open(os.path.join(OUT, name), "wb") as f:
            f.write(body)
    static_dir = os.path.join(FRONTEND_DIR, "static")
    for url, (filename, _ctype) in ICONS.items():
        src = os.path.join(static_dir, filename)
        if os.path.isfile(src):
            shutil.copyfile(src, os.path.join(OUT, url.lstrip("/")))
    print("wrote " + OUT)


if __name__ == "__main__":
    main()
