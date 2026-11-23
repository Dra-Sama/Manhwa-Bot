# Code By @V_Sbotmaker (on Telegram)
"""Available manga sources."""

from .mangadot import MangadotWebs
from .mangamob import MangaMobWebs
from .asurascans import AsuraScansWebs
from .flamecomics import FlameComicsWebs
from .demonicscans import DemonicScansWebs
from .weebcentral import WeebCentralWebs
from .manhuaplus import ManhuaplusWebs
from .mgeko import MgekoWebs
from .mangakatana import MangaKatanaWebs
from .manhuapluscom import ManhuaPlusComWebs
from .vortexscans import VortexScansWebs
from .kingofshojo import KingofShojoWebs
from .madarascans import MadaraScans
from .thunderscans import ThunderScansWebs
from .roliascan import RoliaScanWebs
from .omegascans import OmgeaScansWebs
from .manhwa18_net import Manhwa18NetSource
from .manhwa18_cc import Manhwa18Source

web_data = {
    ' MangaDot [cf] ': MangadotWebs(),
    ' MangaMob ': MangaMobWebs(),
    ' Asura Scans ': AsuraScansWebs(),
    ' Flame Comics': FlameComicsWebs(),
    ' Demonic Scans ': DemonicScansWebs(),
    ' Weeb Central ': WeebCentralWebs(),
    ' Manhuaplus ': ManhuaplusWebs(),
    ' Mgeko ': MgekoWebs(),
    ' MangaKatana ': MangaKatanaWebs(),
    ' ManhuaPlus.com ': ManhuaPlusComWebs(),
    ' VortexScans ': VortexScansWebs(),
    ' KingofShojo ': KingofShojoWebs(),
    ' MadaraScans ': MadaraScans(),
    ' ThunderScans ': ThunderScansWebs(),
    ' RoliaScan ': RoliaScanWebs(),
    ' OmegaScans ': OmgeaScansWebs(),
    ' Manhwa18.net ': Manhwa18NetSource(),
    ' Manhwa18.cc ': Manhwa18Source(),
}
