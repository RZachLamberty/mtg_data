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

from json.decoder import JSONDecodeError as _JSONDecodeError

from mtg import cards, decks, tags

# ----------------------------- #
#   Module Constants            #
# ----------------------------- #

_LOGGER = _logging.getLogger(__name__)
_LOGGER.setLevel(_logging.DEBUG)

_URL = 'http://tappedout.net/api/inventory/{owner:}/board/'
_FIELDNAMES = ['Name', 'Edition', 'Qty', 'Foil', ]
_FNAME = _os.path.join(_os.sep, 'tmp', 'mtg_inventory.csv')


class TappedOutError(Exception):
    pass


# ----------------------------- #
#   generic functions           #
# ----------------------------- #

def get_inventory(url=_URL, owner='ndlambo', pagelength=500):
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
    # useful lookup dict
    mtgjson = {(card.get('name'), card.get('setname')): card
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
        price = _html.fromstring(record['market_price']).text_content()
        try:
            record['px'] = float(price)
        except:
            record['px'] = None

        try:
            record.update(mtgjson[record['name'], record['set']])
        except:
            pass

    return inventory


def df_inventory(url=_URL, owner='ndlambo', pagelength=500):
    return _pd.DataFrame(get_inventory(url, owner, pagelength))


# ----------------------------- #
# deck-specific information     #
# ----------------------------- #

def _get_deck_df(deckid):
    deckurl = 'http://tappedout.net/mtg-decks/{}/?fmt=csv'.format(deckid)
    try:
        df = _pd.read_csv(deckurl)
        df.columns = [_.lower() for _ in df.columns]
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

    def __init__(self, deckid, keep_data=True, card_universe=None,
                 ignore_lands=True):
        """build a deck object off of `deckid` on TO

        args:
            deckid (str): the id we go and fetch from the TO site (will also be
                the name of the deck object)
            keep_data (bool): whether or not to keep the dataframe we obtain
                from tappedout for `deckid` as an attribute `self.df`
                (default: True)
            card_universe (iterable): a list of the card names available in the
                entire game universe (also will be converted to a distinct set).
                (default: _CARD_UNIVERSE with or without lands as determined by
                `ignore_lands`)
            ignore_lands (bool): whether or not we should ignore lands in all of
                our various collections of cards (default: True)

        returns:
            TappedoutDeck: an initialized deck object

        raises:
            DeckError

        """
        self.deckid = deckid
        if keep_data:
            self.df = _get_deck_df(self.deckid)

        cardnames = set(self.df.name.tolist())

        if ignore_lands:
            cardnames = cardnames.difference(cards.all_land_card_names())

        super().__init__(cardnames=cardnames,
                         name=self.deckid,
                         card_universe=card_universe,
                         ignore_lands=ignore_lands, )


# ----------------------------- #
# tags                          #
# ----------------------------- #

def get_categories(deckid):
    """given a tappedout deck id, get all tagged custom categories for that deck

    "categories" is the TO name for what we internally call a tag

    args:
        deckid (str): tappedout.net deck id

    """
    resp = _requests.get('http://tappedout.net/mtg-decks/{}/'.format(deckid),
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
    # meaning in the context of the given deckid. we chose to represent these as
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

def binder_summary(url=_URL, owner='ndlambo', bulkthresh=0.30, mainthresh=1.00):
    """break things down as if they're in a binder"""
    keepkeys = ['name', 'qty', 'foil', 'px', 'tla', 'type', 'tcg-foil-price',
                'colorIdentity', 'power', 'toughness', 'cmc', 'set']
    inventory = _pd.DataFrame(get_inventory(url, owner))[keepkeys]

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

    # for prices, give everything the average, and then overwrite where foil
    inventory.rename(columns={'px': 'price'}, inplace=True)
    usefoilpx = inventory.foil.notnull() & (inventory['tcg-foil-price'] != '')
    foilpx = (inventory
              .loc[usefoilpx, 'tcg-foil-price']
              .str
              .replace(',', '.')
              .astype(float))
    inventory.loc[usefoilpx, 'price'] = foilpx

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
        by=['card_value', 'is_land', 'colorstr', 'mytype', 'cmc', 'power',
            'toughness', 'name', 'foil'])

    return inventory


def binder_df_to_pagelists(inventory):
    """given a binder inventory dataframe, create a 9x9 pagelist with
    information needed for actually laying out the binder

    """
    return ['{} ({}, {} of {})'.format(row['name'], row.type, i + 1, row.qty)
            for (ind, row) in inventory.iterrows()
            for i in range(row.qty)]


# ----------------------------- #
#   cli                         #
# ----------------------------- #

def main(url=_URL, owner='ndlambo', fname=_FNAME):
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
