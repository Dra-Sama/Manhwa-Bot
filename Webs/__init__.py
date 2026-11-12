# Code By @V_Sbotmaker (on Telegram)
#from .comick import ComickWebs
from .mangamob import MangaMobWebs
from .mangafire import MangaFireWebs
from .api import (
    ComicKAPIWebs, QiManhwaAPIWebs, HentaraAPIWebs,
    AquaReaderAPIWebs, KaliScansAPIWebs,
    AnisaScansAPIWebs, ComicKFanAPIWebs, ManhuaHotAPIWebs,
    MangaPillAPIWebs, ScansGGAPIWebs, ManhwaZoneAPIWebs,
    MangaKAPIWebs, ManganatoAPIWebs, MangaHeAPIWebs,
    BrainrotComicsAPIWebs, BakkinAPIWebs, BunMangaAPIWebs,
    Hentai4FreeAPIWebs, MangaFoxAPIWebs, MantaAPIWebs,
    RitharScansAPIWebs, WitchScansAPIWebs, MangaHubAPIWebs,
    WebtoonsAPIWebs, MangaGGAPIWebs, AllmangaAPIWebs
)
from .asurascans import AsuraScansWebs
from .flamecomics import FlameComicsWebs
from .demonicscans import DemonicScansWebs
from .manhuafast import ManhuaFastWebs
from .weebcentral import WeebCentralWebs
from .manhwaclan import ManhwaClanWebs
from .templetoons import TempleToonsWebs
from .manhuaplus import ManhuaplusWebs
from .mgeko import MgekoWebs
from .batoto import BatotoWebs
from .mangabuddy import MangaBuddyWebs
# from .aquareader import AquaReaderWebs      # API se use ho rha
from .mangakatana import MangaKatanaWebs
from .likemanga import MangayyWebs
from .mangapark import MangaParkWebs
# from .kaliscans import KaliScansWebs         # API se use ho rha
from .mangakakalot import MangaKakalotGGWebs
from .lunatoons import LunatoonsWebs
from .manhuaus import ManhuaUSWebs
from .manhuatop import ManhuaTopWebs
from .manhwatop import ManhwaTopWebs
#from .allmanga import AllMangaWebs
from .taadd import TaaddWebs
from .mangaball import MangaBallWebs
from .mangadna import ManhaDNAWebs
from .atsumaru import AtsumaruWebs
from .hivetoons import HiveToonsWebs
from .manhuapluscom import ManhuaPlusComWebs
from .vortexscans import VortexScansWebs
from .kingofshojo import KingofShojoWebs
from .resetscans import ResetScansWebs
# from .qiscans import QiScansWebs
# from .comix import ComixWebs
from .madarascans import MadaraScans as MadaraScansWebs
from .thunderscans import ThunderScansWebs 
from .elftoon import ElftoonWebs
from .roliascan import RoliaScanWebs
from .mangadot import MangadotWebs
# from .mangacloud import MangaCloudWebs


web_data = {
    " MangaDot [cf] ": MangadotWebs(),
    #" Comix ": ComixWebs(),
    " Hentara ": HentaraAPIWebs(),
    " ComicK ": ComicKAPIWebs(),
    " MangaMob ": MangaMobWebs(),
    " Asura Scans ": AsuraScansWebs(),
    " Flame Comics": FlameComicsWebs(),
    " Demonic Scans ": DemonicScansWebs(),
    " Manhua Fast ": ManhuaFastWebs(),
    " Weeb Central ": WeebCentralWebs(),
    #" ManhwaClan ": ManhwaClanWebs(),
    " TempleToons ": TempleToonsWebs(),
    " Manhuaplus ": ManhuaplusWebs(),
    " Mgeko ": MgekoWebs(),
    #" Batoto ": BatotoWebs(),
    " MangaFire ": MangaFireWebs(),
    " MangaBuddy ": MangaBuddyWebs(),
    " AquaReader ": AquaReaderAPIWebs(),
    " MangaKatana ": MangaKatanaWebs(),
    " MangaGayy ": MangayyWebs(),
    " KaliScans ": KaliScansAPIWebs(),
    " MangaKakalot ": MangaKakalotGGWebs(),
    " Lunatoons ": LunatoonsWebs(),
    " Manhuaus ": ManhuaUSWebs(),
    " ManhuaTop ": ManhuaTopWebs(),
    " ManhwaTop ": ManhwaTopWebs(),
    " AllManga ": AllmangaAPIWebs(),
    " Taadd ": TaaddWebs(),
    " MangaBall ": MangaBallWebs(),
    #" Manga DNA ": ManhaDNAWebs(),
    " Atsumaru ": AtsumaruWebs(),
    " HiveToons": HiveToonsWebs(),
    " ManhuaPlus.com ": ManhuaPlusComWebs(),
    " VortexScans ": VortexScansWebs(),
    " KingofShojo ": KingofShojoWebs(),
    " ResetScans ": ResetScansWebs(),
    " QiScans ": QiManhwaAPIWebs(),
    " MadaraScans ": MadaraScansWebs(),
    " ThunderScans ": ThunderScansWebs(),
    " Elftoon ": ElftoonWebs(),
    " RoliaScan ": RoliaScanWebs(),
   # " MangaCloud ": MangaCloudWebs(),
    
    # ===== NEW API SOURCES =====
    " AnisaScans ": AnisaScansAPIWebs(),
    " ComicK Fanmade ": ComicKFanAPIWebs(),
    " ManhuaHot ": ManhuaHotAPIWebs(),
    " MangaPill ": MangaPillAPIWebs(),
    " ScansGG ": ScansGGAPIWebs(),
    " ManhwaZone ": ManhwaZoneAPIWebs(),
    " MangaK ": MangaKAPIWebs(),
    " Manganato ": ManganatoAPIWebs(),
    " MangaHe ": MangaHeAPIWebs(),
    " Brainrot Comics ": BrainrotComicsAPIWebs(),
    " Bakkin ": BakkinAPIWebs(),
    " BunManga ": BunMangaAPIWebs(),
    " Hentai4Free ": Hentai4FreeAPIWebs(),
    " MangaFox ": MangaFoxAPIWebs(),
    " Manta ": MantaAPIWebs(),
    " Rithar Scans ": RitharScansAPIWebs(),
    " Witch Scans ": WitchScansAPIWebs(),
    " MangaHub ": MangaHubAPIWebs(),
    " Webtoons ": WebtoonsAPIWebs(),
    " MangaGG ": MangaGGAPIWebs(),
}
