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

import logging as _logging
import os as _os

import lxml.html as _html
import numpy as _np
import pandas as _pd
import requests as _requests

import cards
import decks

from json.decoder import JSONDecodeError as _JSONDecodeError

# ----------------------------- #
#   Module Constants            #
# ----------------------------- #

_HERE = _os.path.dirname(_os.path.realpath(__file__))
_LOGGER = _logging.getLogger(__name__)
_LOGGER.setLevel(_logging.DEBUG)

_URL = 'http://tappedout.net/api/inventory/{owner:}/board/'
_FIELDNAMES = ['Name',
               'Edition',
               'Qty',
               'Foil', ]
_FNAME = _os.path.join(_os.sep, 'tmp', 'mtg_inventory.csv')


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
                                          'qty': 'Qty',})
    inventory.loc[:, 'Foil'] = _np.where(inventory.foil.notnull(), 'Yes', 'No')
    inventory[_FIELDNAMES].to_csv(fname, index=False)
    print('wrote file {}'.format(fname))


if __name__ == '__main__':
    main()
