import collections

# --------------------------#
# sets of colors            #
# --------------------------#

# mono-color
MONO = tuple((_,) for _ in "WUBRG")

# guilds (ordering is to match edhrec, fwiw)
AZORIUS = ('W', 'U')
DIMIR = ('U', 'B')
RAKDOS = ('B', 'R')
GRUUL = ('R', 'G')
SELESNYA = ('G', 'W')
ORZHOV = ('W', 'B')
IZZET = ('U', 'R')
GOLGARI = ('B', 'G')
BOROS = ('R', 'W')
SIMIC = ('G', 'U')
GUILDS = (AZORIUS,
          ORZHOV,
          BOROS,
          SELESNYA,
          DIMIR,
          IZZET,
          SIMIC,
          RAKDOS,
          GOLGARI,
          GRUUL,)

# shards
ESPER = ('W', 'U', 'B')
GRIXIS = ('U', 'B', 'R')
JUND = ('B', 'R', 'G')
NAYA = ('R', 'G', 'W')
BANT = ('G', 'W', 'U')
SHARDS = (ESPER,
          GRIXIS,
          JUND,
          NAYA,
          BANT,)

# wedges
ABZAN = ('W', 'B', 'G')
JESKAI = ('U', 'R', 'W')
SULTAI = ('B', 'G', 'U')
MARDU = ('R', 'W', 'B')
TEMUR = ('G', 'U', 'R')
WEDGES = (ABZAN,
          JESKAI,
          SULTAI,
          MARDU,
          TEMUR,)

# four c
ARTIFICE = ('W', 'U', 'B', 'R')  # edhrec: yore-tiller
CHAOS = ('U', 'B', 'R', 'G')  # edhrec: glint-eye
AGGRESSION = ('B', 'R', 'G', 'W')  # edhrec: dune-brood
ALTRUISM = ('R', 'G', 'W', 'U')  # edhrec: ink-treader
GROWTH = ('G', 'W', 'U', 'B')  # edhrec: witch-maw
FOUR_C = (ARTIFICE,
          CHAOS,
          AGGRESSION,
          ALTRUISM,
          GROWTH,)

# five c
WUBRG = ('W', 'U', 'B', 'R', 'G')
FIVE_C = (WUBRG,)

# iterable of all of the above
ALL_COLOR_COMBOS = (MONO
                    + GUILDS
                    + SHARDS
                    + WEDGES
                    + FOUR_C
                    + FIVE_C)
COLORLESS = (('COLORLESS',),)
ALL_COLOR_COMBOS_W_COLORLESS = COLORLESS + ALL_COLOR_COMBOS

# --------------------------#
# color namedtuples         #
# --------------------------#

MtgColor = collections.namedtuple('MtgColor',
                                  ['fullname', 'shortname', 'is_color', 'rgb'])
WHITE = MtgColor('white', 'w', True, 'rgb(245, 228, 183)')
BLUE = MtgColor('blue', 'u', True, 'rgb(193, 232, 251)')
BLACK = MtgColor('black', 'b', True, 'rgb(2, 2, 2)')
RED = MtgColor('red', 'r', True, 'rgb(250, 170, 143)')
GREEN = MtgColor('green', 'g', True, 'rgb(152, 207, 171)')
COLORLESS = MtgColor('colorless', '0', False, 'rgb(208, 202, 200)')
MTG_COLORS = [WHITE, BLUE, BLACK, RED, GREEN, COLORLESS]

# --------------------------#
# common card lists         #
# --------------------------#

BASIC_LANDS = ['Plains', 'Island', 'Swamp', 'Mountain', 'Forest', 'Wastes']
