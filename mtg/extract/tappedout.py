#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module: tappedout.py
Author: zlamberty
Created: 2018-05-14

Description:
    tapped out instantiations of the various objects (decks, inventories) in
    this repository

Usage:
    <usage>

"""

import collections as _collections
import logging as _logging
import os as _os
import re as _re

import lxml.html as _html
import numpy as _np
import networkx as _nx
import pandas as _pd
import requests as _requests

from functools import lru_cache as _lru_cache
from json.decoder import JSONDecodeError as _JSONDecodeError

from mtg import cards, decks, tags

# ----------------------------- #
#   Module Constants            #
# ----------------------------- #

_LOGGER = _logging.getLogger(__name__)
_LOGGER.setLevel(_logging.DEBUG)

_INVENTORY_URL = 'http://tappedout.net/api/inventory/{owner:}/board/'
_FIELDNAMES = ['Name', 'Edition', 'Qty', 'Foil', ]
_FNAME = _os.path.join(_os.sep, 'tmp', 'mtg_inventory.csv')

# to handle stupid casing and special characters
_CARD_ALIASES = {'Open Into Wonder': 'Open into Wonder',
                 "Lim-Dul's Vault": "Lim-Dûl's Vault"}

_CURRENT_DECK_URLS = {'/mtg-decks/06-06-18-esper-blink/',
                      '/mtg-decks/12-07-19-jeskai-edh/',
                      '/mtg-decks/13-02-16-mizzix-of-the-izmagnus-edh/',
                      '/mtg-decks/19-02-17-AGL-breya-edh/',
                      '/mtg-decks/23-03-17-gobrins/',
                      '/mtg-decks/doubling-season-edh/',
                      '/mtg-decks/havoc-festival-edh/',
                      '/mtg-decks/19-09-19-grixis-rogues/',
                      '/mtg-decks/zadaaaaaahhhhhhh-copy/',
                      '/mtg-decks/sprite-draw/',
                      # EDH   ^^^^
                      # other vvvv
                      '/mtg-decks/modern-delve-4/',
                      '/mtg-decks/mtggoldfish-restore-balance/',
                      '/mtg-decks/mtggoldfish-uw-tempered-steel/',
                      '/mtg-decks/08-06-17-fevered-thing-tutelage/', }


class TappedOutError(Exception):
    pass


# ----------------------------- #
#   generic functions           #
# ----------------------------- #

@_lru_cache(None)
def get_inventory(url=_INVENTORY_URL, owner='ndlambo', pagelength=500):
    """simple inventory json getter"""
    inventory = []
    params = {'length': pagelength, 'start': 0, }

    while True:
        resp = _requests.get(url.format(owner=owner), params=params)

        # we *should* be able to read everything returned this way
        try:
            j = resp.json()
        except _JSONDecodeError:
            print(resp.status_code)
            raise

        # j['data'] is a possibly-empty list. iterate until it's empty.
        if j['data']:
            inventory += j['data']
            params['start'] += pagelength
            _LOGGER.debug('collected {} records so far'.format(len(inventory)))
        else:
            break

    # we get a bit of extra information from the mtgjson site we'd like to join
    # in (specifically, cmc and color identity), so pivot that out into a more
    # useful lookup dict. include a hand-maintained mapping from mtgjson set
    # names to those supported in tappedout
    setname_remapping = {'CMA': 'CM1'}

    def parse_set_name(card):
        setname = card.get('setname')
        return setname_remapping.get(setname, setname)

    mtgjson = {(card.get('name', '').lower(), parse_set_name(card)): card
               for card in cards.get_cards()}

    # do some parsing of the html elements returned (because we can't just get
    # names, I guess).
    for record in inventory:
        record['qty'] = record['amount']['qty']
        carddetails = _html.fromstring(record['card']).find('.//a').attrib
        record.update({k.replace('data-', ''): v
                       for (k, v) in carddetails.items()
                       if k.startswith('data-')})
        record.update(record['edit'])

        # merging with mtgjson requires fixing the setname and the card name
        setname = record['set']
        if setname == '000':
            for (_, sn) in record['all_printings']:
                if sn != setname:
                    setname = sn
                    break

        orig_name = record['name']
        cardname = orig_name.lower()

        # merge in stuff from the mtgjson api
        if ' / ' in cardname:
            # handle fusion cards, which are lame and suck. take the bulk of the
            # info from the first of the two cards, but get color identity from
            # the second
            left_half, right_half = cardname.split(' / ')
            record.update(mtgjson.get((left_half, setname), {}))
            other_ci = mtgjson.get((right_half, setname), {})['colorIdentity']
            record['colorIdentity'] += other_ci
            # make unique
            record['colorIdentity'] = list(set(record['colorIdentity']))

            # undo the overwrite of the cardname which is stupid af
            record['name'] = orig_name
        else:
            record.update(mtgjson.get((cardname, setname), {}))

        is_foil = record['foil'] is not None
        try:
            tcg_px_key = f"tcg{'-foil' if is_foil else ''}-price"
            price = float(record[tcg_px_key])
        except:
            try:
                reg_px_key = 'paperFoil' if is_foil else 'paper'
                px_dict = record['prices'][reg_px_key]
                most_recent_date = max(px_dict.keys())
                price = float(px_dict[most_recent_date])
            except:
                _LOGGER.debug(f"no price info found for {record['name']}")
                pass

        try:
            record['px'] = float(price)
        except:
            record['px'] = None

        try:
            record['in_collections'] = {_['url'] for _ in
                                        record['other_collections'][
                                            'collections']}
        except KeyError:
            pass

    return inventory


@_lru_cache(None)
def df_inventory(url=_INVENTORY_URL, owner='ndlambo', pagelength=500):
    return _pd.DataFrame(get_inventory(url, owner, pagelength))


# ----------------------------- #
# deck-specific information     #
# ----------------------------- #

@_lru_cache(None)
def _get_deck_ids(owner='ndlambo'):
    ids = []
    page = 1

    while True:
        _LOGGER.debug('loading deck ids, page {}'.format(page))

        resp = _requests.get(
            'https://tappedout.net/users/{}/mtg-decks/'.format(owner),
            params={'page': page})

        if resp.status_code == 404:
            break

        root = _html.fromstring(resp.text)
        ids += [_.attrib['href'].replace('/mtg-decks/', '').replace('/', '')
                for _ in root.xpath('.//h3[contains(@class, "name")]/a')]

        page += 1

    return ids


@_lru_cache(None)
def _get_deck_df(deck_id):
    deckurl = 'http://tappedout.net/mtg-decks/{}/?fmt=csv'.format(deck_id)
    try:
        df = _pd.read_csv(deckurl)
        df.columns = [_.lower() for _ in df.columns]
        # if we entered a card more than once in the editor, it will appear as
        # separate lines. in those instances, let's collapse them
        cols = df.columns
        df = (df
              .groupby('name')
              .agg({c: ('sum' if c == 'qty' else 'first')
                    for c in cols if c != 'name'})
              .reset_index())[cols]

        # alias some names to play nice with mtgjson
        df.replace({'name': _CARD_ALIASES}, inplace=True)

        return df
    except _pd.io.common.HTTPException:
        raise ValueError("receive http exception -- check that deck is public")


class TappedoutDeck(decks.Deck):
    """a TO-specific wrapper around the deck model

    this will have a sampling function (`choice`) as a subclass of `decks.Deck`,
    but will also have a to-specific dataframe of deck information as self.df
    (if
    requested at construction time)

    """

    def __init__(self, deck_id, keep_data=True, card_universe=None,
                 ignore_lands=True, with_tags=False):
        """build a deck object off of `deck_id` on TO

        args:
            deck_id (str): the id we go and fetch from the TO site (will also be
                the name of the deck object)
            keep_data (bool): whether or not to keep the dataframe we obtain
                from tappedout for `deck_id` as an attribute `self.df`
                (default: True)
            card_universe (iterable): a list of the card names available in the
                entire game universe (also will be converted to a distinct set).
                (default: _CARD_UNIVERSE with or without lands as determined by
                `ignore_lands`)
            ignore_lands (bool): whether or not we should ignore lands in all of
                our various collections of cards (default: True)
            with_tags (bool): whether or not we should load the category tags we
                have entered in TO (default: False)

        returns:
            TappedoutDeck: an initialized deck object

        raises:
            DeckError

        """
        self.deck_id = deck_id
        self.ignore_lands = ignore_lands
        self.with_tags = with_tags

        if keep_data:
            self.df = _get_deck_df(self.deck_id)

        cardnames = set(self.df.name.tolist())

        if self.ignore_lands:
            cardnames = cardnames.difference(cards.all_land_card_names())

        if self.with_tags:
            self.df = self.df.merge(self.deck_tags,
                                    how='left',
                                    on=['name'])

        super().__init__(cardnames=cardnames,
                         name=self.deck_id,
                         card_universe=card_universe,
                         ignore_lands=ignore_lands, )

    @property
    def deck_tags(self):
        try:
            return self._deck_tags
        except AttributeError:
            self._deck_tags = _pd.DataFrame(
                get_categories(self.deck_id).items(),
                columns=['name', 'tag_list'])
            return self._deck_tags

    @property
    def text_description(self):
        """the text block you could use to create this deck by copy-pasta"""
        # the basic form of a single line is
        #   {qty}x {name}[ ({set_code})][ {tag_list}]
        # where the items in brackets are optional and depend on the column
        # existing
        qty = self.df.qty.astype('str')
        name = self.df.name

        set_code = self.df.printing.apply(lambda sc: (''
                                                      if _np.isnan(sc)
                                                      else ' ({})'.format(sc)))

        def make_tag_list_str(tl):
            try:
                return ' '.join(tl)
            except TypeError:
                return ''

        tag_list = self.df.tag_list.apply(make_tag_list_str)

        return '\n'.join((self.df.qty.astype('str')
                          + 'x '
                          + self.df.name
                          + ' '
                          + set_code
                          + tag_list).values)


# ----------------------------- #
# tags                          #
# ----------------------------- #

@_lru_cache(None)
def get_categories(deck_id):
    """given a tappedout deck id, get all tagged custom categories for that deck

    "categories" is the TO name for what we internally call a tag

    args:
        deck_id (str): tappedout.net deck id

    """
    _LOGGER.debug('loading categories for deck {}'.format(deck_id))
    resp = _requests.get('http://tappedout.net/mtg-decks/{}/'.format(deck_id),
                         params={'cat': 'custom'})
    root = _html.fromstring(resp.text)
    mbc_xp = './/div[contains(@class, "board-container")]'
    mainboard_container = root.xpath(mbc_xp)[0]
    categories = _collections.defaultdict(list)

    cd_xp = './/div[contains(@class, "board-col")]//h3'
    for cat_div in mainboard_container.xpath(cd_xp):
        category = '#{}'.format(cat_div
                                .text
                                .strip()
                                .split('\xa0')
                                [0]
                                .replace(' ', '_')
                                .lower())
        if category == '#other':
            continue
        cat_ul = cat_div.getnext()
        cardnames = [_.attrib['data-name'] for _ in cat_ul.xpath('./li/a')]
        for cardname in cardnames:
            categories[cardname].append(category)

    return categories


@_lru_cache(None)
def get_all_categories(owner='ndlambo'):
    return {deck_id: dict(get_categories(deck_id))
            for deck_id in _get_deck_ids(owner)}


TAPPEDOUT_TAGS_TO_REPLACE = {'enbaler': 'stopgap',
                             'enabler': 'stopgap',
                             'enhancer': 'amplify',
                             'win': 'wincon',
                             'winning': 'wincon', }
TAPPEDOUT_SPECIAL_TAGS = ['amplify',
                          'engine',
                          'standalone',
                          'stopgap',
                          'wincon']


def build_categories_df(categories, aliases=None):
    """given a categories dictionary such as get_all_categories returns
    above, build a dataframe view with some helpful extra pieces

    """
    if aliases is None:
        aliases = {}
    aliases_df = _pd.DataFrame(aliases.items(),
                               columns=['tappedout_tag', 'tag'])

    tappedout_tag_df = _pd.DataFrame([{'deck_id': deck_id,
                                       'card': card,
                                       'tappedout_tag_raw': tappedout_tag}
                                      for (deck_id, card_dict) in
                                      categories.items()
                                      for card, taglist in card_dict.items()
                                      for tappedout_tag in taglist])

    tappedout_tag_df.loc[:, 'tappedout_tag'] = (tappedout_tag_df
                                                .tappedout_tag_raw
                                                .str.replace('#', '')
                                                .str.replace('_', ' '))

    to_replace = {'tappedout_tag': TAPPEDOUT_TAGS_TO_REPLACE}
    tappedout_tag_df = (tappedout_tag_df
                        # just fix a typo and remap terms I've had two names for
                        .replace(to_replace=to_replace)
                        .merge(aliases_df, how='left', on='tappedout_tag'))

    # replace the tags with the deck-specific ones in some instances
    tappedout_tag_df.loc[:, 'is_special'] = (tappedout_tag_df
                                             .tappedout_tag
                                             .isin(TAPPEDOUT_SPECIAL_TAGS))
    tappedout_tag_df.tag = (tappedout_tag_df
                            .tag
                            .where(~tappedout_tag_df.is_special,
                                   (tappedout_tag_df.deck_id
                                    + ' - '
                                    + (tappedout_tag_df
                                       .tappedout_tag
                                       .str.capitalize()))))

    return tappedout_tag_df


def tappedout_categories_to_tags(deckid, categories):
    """given categories as represented above, create a network linking cards to
    categories and categories to tags

    the mapping between categories and tags is effectively one-to-one, but this
    model supports the ability to have "dangling" categories (which don't match
    to any known tag)

    """
    # get a list of known tags and mappings from TO categories to them
    catgraph = tags.Tags().tags.copy()
    _nx.set_node_attributes(catgraph, 'Tag', 'label')
    _nx.set_edge_attributes(catgraph, 'IS_SUBTAG_OF', '_type')

    # let's handle the mapping between tappedout categories and tags.
    def tagname_to_cat(tagname):
        cat = _re.sub('mtg:?', '', tagname)
        cat = _re.sub('deck_categories:?', '', cat)
        cat = _re.sub(':', '_', cat)
        cat = '#{}'.format(cat)
        return cat

    categories_to_tags = {tagname_to_cat(tagname): tagname
                          for tagname in catgraph
                          if tagname not in ['mtg', 'mtg:deck_categories']}

    # let's handle the deck node before we get into the nitty gritty
    catgraph.add_node(deckid, label='Deck', is_tappedout=True)

    # the tappedout categories of amplify, standalone, and stopgap only have
    # meaning in the context of the given deck_id. we chose to represent
    # these as
    # subcategories of the broader category "amplify" (etc) named for their
    # decks (similar to how goblin tribal cards are "tribal:goblin")
    for deckcat in ['amplify', 'standalone', 'stopgap']:
        old_tagname = 'mtg:deck_categories:{}'.format(deckcat)
        new_tagname = 'mtg:deck_categories:{}:{}'.format(deckcat,
                                                         deckid.replace(':',
                                                                        ''))
        catgraph.add_node(new_tagname, label="Tag")
        catgraph.add_edge(new_tagname, old_tagname, _type='IS_SUBTAG_OF')
        categories_to_tags['#{}_{}'.format(deckcat, deckid)] = new_tagname

    # for each of the "known" categories above, pre-emptively add the tappedout
    # node and real tag relationship
    for (catname, tagname) in categories_to_tags.items():
        catgraph.add_node(catname, label="TappedoutCategory")
        catgraph.add_edge(catname, tagname, _type="IS_TAPPEDOUT_VERSION_OF")

    # categories is a cardname: [to_cat1, to_cat2, ...] mapping. iterate through
    # it, creating new nodes and edges to known tags. raise an error if a
    # recommended category doesn't exist as a tag (fix whichever is incorrect,
    # normalizing the category name to match prior tags or adding a new tag)
    failures = []
    for (cardname, category_list) in categories.items():
        catgraph.add_node(cardname, label='Card')
        catgraph.add_edge(cardname, deckid, _type='IS_IN_DECK')

        for category in category_list:
            if category in ['#amplify', '#standalone', '#stopgap']:
                category = '{}_{}'.format(category, deckid)
            catgraph.add_edge(cardname, category, _type='HAS_TO_CATEGORY')
            if not category in categories_to_tags:
                msg = 'tappedout category "{}" does not map to any known tag'
                msg = msg.format(category)
                _LOGGER.warning(msg)
                failures.append([cardname, category, msg])

    return catgraph


# ----------------------------- #
# binder-specific information   #
# ----------------------------- #

def binder_summary(url=_INVENTORY_URL, owner='ndlambo', bulkthresh=0.30,
                   mainthresh=1.00):
    """break things down as if they're in a binder"""
    keepkeys = ['name', 'qty', 'foil', 'px', 'tla', 'type', 'tcg-foil-price',
                'colorIdentity', 'power', 'toughness', 'convertedManaCost',
                'set', 'in_collections', 'other_collections']
    inventory = _pd.DataFrame(get_inventory(url, owner))[keepkeys]

    # some collections are fixed and off limits -- if a card is in one,
    # we won't binder it. calculate the number of copies of a given card that
    # are reserved for current decks
    def num_unclaimed(rec):
        try:
            num_claimed = sum(_['qty']
                              for _ in
                              rec.other_collections['collections']
                              if _['url'] in _CURRENT_DECK_URLS)
            return max(0, rec.qty - num_claimed)
        except (AttributeError, TypeError):
            return rec.qty
        except Exception as e:
            _LOGGER.error(e)
            _LOGGER.error(f'rec = {rec}')
            raise

    inventory.loc[:, 'num_unclaimed'] = (inventory
                                         .apply(num_unclaimed, axis=1)
                                         .fillna(0))
    inventory = inventory[inventory.num_unclaimed > 0]

    # sets are annoying; could be strings or lists. fix
    def fix_set(s):
        return s if isinstance(s, str) else s[0]

    inventory.loc[:, 'set'] = (inventory
                               ['set']
                               .apply(fix_set))

    # power and toughness are numbers, *s and NaNs. replace *s with infs and
    # the category is already ordered
    def tryfloat(x):
        try:
            return float(x.replace('*', 'inf'))
        except (ValueError, AttributeError):
            return x

    inventory.loc[:, 'power'] = inventory.power.apply(tryfloat)
    inventory.loc[:, 'toughness'] = inventory.toughness.apply(tryfloat)

    inventory.power = inventory.power.astype('category')
    inventory.toughness = inventory.toughness.astype('category')

    orderedpow = sorted(inventory.power.cat.categories)
    orderedtuf = sorted(inventory.toughness.cat.categories)
    inventory.power = (inventory
                       .power
                       .cat
                       .reorder_categories(orderedpow, ordered=True))
    inventory.toughness = (inventory
                           .toughness
                           .cat
                           .reorder_categories(orderedtuf, ordered=True))

    # replace the "is land" notion
    inventory.loc[:, 'is_land'] = inventory.type.str.match('land', False)

    inventory.rename(columns={'px': 'price'}, inplace=True)
    # # for prices, give everything the average, and then overwrite where foil
    # usefoilpx = inventory.foil.notnull() & (inventory['tcg-foil-price'] != '')
    # foilpx = (inventory
    #           .loc[usefoilpx, 'tcg-foil-price']
    #           .str
    #           .replace(',', '.')
    #           .astype(float))
    # inventory.loc[usefoilpx, 'price'] = foilpx

    # subset based on whether or not they meet my thresholds
    inventory.loc[:, 'card_value'] = _pd.cut(inventory.price,
                                             right=False,
                                             bins=[0, bulkthresh, mainthresh,
                                                   float('inf')],
                                             labels=['small', 'medium',
                                                     'large'])
    inventory.card_value = (inventory
                            .card_value
                            .cat
                            .reorder_categories(['large', 'medium', 'small'],
                                                ordered=True))

    # drop small and sort the results in "binder order"
    inventory = inventory[inventory.card_value != 'small']

    # order also depends on number of colors involved in casting; create an
    # ordered category for this
    def colorstr(rec):
        try:
            return ''.join(sorted(rec))
        except TypeError:
            return ''

    inventory.loc[:, 'colorstr'] = inventory.colorIdentity.apply(colorstr)
    inventory.colorstr = inventory.colorstr.astype('category')

    def color_category_order(cat):
        """color order within the binder"""
        numcolor = len(cat)
        ismono = numcolor == 1
        iscolorless = numcolor == 0
        ismulti = numcolor > 1

        return (not ismono,
                not iscolorless,
                not ismulti,
                # just one in the opposite order
                -numcolor,
                # break ties by color
                'W' not in cat,
                'U' not in cat,
                'B' not in cat,
                'R' not in cat,
                'G' not in cat,)

    orderedcats = sorted(inventory.colorstr.cat.categories,
                         key=color_category_order)
    inventory.colorstr = (inventory
                          .colorstr
                          .cat
                          .reorder_categories(orderedcats, ordered=True))

    # ditto for type
    inventory.loc[:, 'mytype'] = (inventory
                                  .type
                                  .str.replace('\u2014', '-')
                                  .str.replace(' - ', '|')
                                  .str.extract('([^|]+)', expand=False))

    inventory.replace({'mytype': {'Artifact Land': 'Land',
                                  'Basic Land': 'Land',
                                  'Enchantment ': '',
                                  'Tribal ': '',
                                  'Legendary ': '',
                                  'Legendary Enchantment ': '', }, },
                      inplace=True,
                      regex=True)

    inventory.mytype = inventory.mytype.astype('category')

    def type_category_order(cat):
        """type order within the binder"""
        cat = cat.lower()
        return (cat != 'planeswalker',
                cat != 'creature',
                cat != 'enchantment',
                cat != 'sorcery',
                cat != 'instant',
                cat != 'artifact',
                cat != 'artifact creature',
                cat != 'land',)

    orderedtypes = sorted(inventory.mytype.cat.categories,
                          key=type_category_order)
    inventory.mytype = inventory.mytype.cat.reorder_categories(orderedtypes,
                                                               ordered=True)

    # separate lands, even if they have color identity (otherwise they get
    # sorted in with their colors)
    inventory.loc[:, 'is_land'] = inventory.mytype == 'Land'

    # finally, sort everything
    inventory = inventory.sort_values(
        by=['card_value', 'is_land', 'colorstr', 'mytype', 'convertedManaCost',
            'name', 'foil'])

    return inventory


def binder_df_to_pagelists(inventory):
    """given a binder inventory dataframe, create a 9x9 pagelist with
    information needed for actually laying out the binder

    """
    return [f"{row['name']} ({row.type}, {i + 1} of {row.qty}) - {row.price}"
            for (ind, row) in inventory.iterrows()
            for i in range(row.qty)]


# ----------------------------- #
#   cli                         #
# ----------------------------- #

def main(url=_INVENTORY_URL, owner='ndlambo', fname=_FNAME):
    """main function"""
    inventory = df_inventory(url, owner)
    inventory.name = inventory.name.str.replace('/', '//')
    inventory = inventory.rename(columns={'name': 'Name',
                                          'tla': 'Edition',
                                          'qty': 'Qty', })
    inventory.loc[:, 'Foil'] = _np.where(inventory.foil.notnull(), 'Yes', 'No')
    inventory[_FIELDNAMES].to_csv(fname, index=False)
    print('wrote file {}'.format(fname))


if __name__ == '__main__':
    main()
