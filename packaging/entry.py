"""PyInstaller-Einstiegspunkt.

Muss ein dünnes Skript mit ABSOLUTEM Import sein: PyInstaller führt Entry-Skripte
als loses Skript aus – relative Importe („from . import …“) schlagen dann im
fertigen Bundle mit „attempted relative import with no known parent package“ fehl.
Das Paket gideons_uebersetzer liegt über pathex (src/) im Bundle und ist hier
als normales Paket importierbar.
"""

import sys

from gideons_uebersetzer.app import main

if __name__ == "__main__":
    sys.exit(main())
