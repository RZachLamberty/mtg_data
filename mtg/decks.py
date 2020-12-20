#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module: decks.py
Author: zlamberty
Created: 2016-02-28

Description:
    MTG card deck class

Usage:
    <usage>

"""

import logging as _logging

import numpy as _np

from mtg import cards

# ----------------------------- #
#   Module Constants            #
# ----------------------------- #

_LOGGER = _logging.getLogger(__name__)
_LOGGER.setLevel(_logging.INFO)
_CARD_UNIVERSE = None

def get_card_universe(k):
    global _CARD_UNIVERSE
    if _CARD_UNIVERSE is None:
        _CARD_UNIVERSE = {'no_lands': cards.all_card_names(ignore_lands=True),
                          'w_lands': cards.all_card_names(ignore_lands=False), }
    return _CARD_UNIVERSE[k]


# ----------------------------- #
#   deck objects                #
# ----------------------------- #

class DeckError(Exception):
    pass


class Deck(object):
    """Abstract base class for other decks to inherit (defines the interface)

    at their core, however, a deck is simply a list of card names. in order to
    facilitate sampling of those decks, I will implement a somewhat complicated
    set of functions that will allow users to generate random samplings of the
    cards in a deck of arbitrary size and shape

    """

    def __init__(self, cardnames=None, name=None, card_universe=None,
                 ignore_lands=True):
        """initialize the deck

        args:
            cardnames (iterable): a list of the cards in the deck (will be
                forced to be unique, so essentially this is a set). (default:
                the empty set)
            name (str): a name for referring to this deck (will be used in
                compositions of this deck for super-sampling). (default: an
                empty string, in super-samples it will be repalced with a random
                string)
            card_universe (iterable): a list of the card names available in the
                entire game universe (also will be converted to a distinct set).
                note that the default value here is all cards *inclduing* lands
                and regardless of value of `ignore_lands`. this is because the
                purpose of this set is to define cards that *exist*, not cards
                we care about for the sampling (that is what the second
                parameter is for) (default: _CARD_UNIVERSE with lands)
            ignore_lands (bool): whether or not we should ignore lands in all of
                our various collections of cards (default: True)

        returns:
            Deck: an initialized deck object

        raises:
            DeckError

        """
        # reasonable default values
        self.cardnames = set(cardnames or set())
        self.name = name or ''
        self.card_universe = card_universe or get_card_universe('w_lands')
        self.ignore_lands = ignore_lands

        # collect all general purpose cleanup and prep work in one function
        self.cardnames = self._clean_cards(self.cardnames)

        # the general purpose cleanup will have exposed some lands

        # drop all cards that appear in the deck but not in the defined card
        # universe. keep them around as list of dropped cards for reference
        self._dropcards = set()
        dropcards = self.cardnames.difference(set(self.card_universe))
        for dc in dropcards:
            _LOGGER.warning('card not in card universe: "{}"'.format(dc))
            self.cardnames.discard(dc)
            self._dropcards.add(dc)

        # TODO: left off here
        nonland_cardnames = self.cardnames.intersection(
            get_card_universe('no_lands'))
        self.cardnames = _np.array(list(self.cardnames))
        self.nonland_cardnames = _np.array(list(nonland_cardnames))

        try:
            compliment_cardnames = set(self.card_universe).difference(
                self.cardnames)
            nonland_compliment_cardnames = compliment_cardnames.intersection(
                get_card_universe('no_lands'))
            self.compliment_cardnames = _np.array(list(compliment_cardnames))
            self.nonland_compliment_cardnames = _np.array(
                list(nonland_compliment_cardnames))
        except TypeError:
            _LOGGER.debug('pretty big deck ya got there')
            self.compliment_cardnames = _np.empty(1)

    # card name cleanup functions
    def _clean_cards(self, cardnames):
        """fix broken card names as needed, and create a list of all the cards
        in the defined card universe that are not in the deck (the compliment)

        """
        cardnames = self._split_two_part_cards(cardnames)
        cardnames = self._fix_weird_characters(cardnames)
        cardnames = self._apply_generic_remapping(cardnames)
        return cardnames

    def _split_two_part_cards(self, cardnames):
        """some systems refer to cards as A // B -- split those into two
        cards"""
        return {c.strip()
                for cardname in cardnames
                for c in cardname.replace('//', '/').split('/')}

    def _fix_weird_characters(self, cardnames):
        """for now the only example is AE, but some systems display pairs of
        characters oddly

        """
        return {_.replace('AE', 'Ae') for _ in cardnames}

    def _apply_generic_remapping(self, cardnames):
        """a catch-all bucket for hard-coding some replacements"""
        remap = {'Seance': 'Séance'}
        return {remap.get(_, _) for _ in cardnames}

    # size and sampling properties
    @property
    def num_cards(self):
        return self.cardnames.shape[0]

    @property
    def max_unique_pairs(self):
        return self.num_cards * (self.num_cards - 1)

    def choice(self, size, n_in_deck=2, n_not_in_deck=0, force_unique=True,
               no_lands=None, **kwargs):
        """sample cards from this deck and possible the compliment

        this is a thin wrapper on np.random.choice. size is assumed to be of
        size (n, n_in_deck + n_not_in_deck), where the first `n_in_deck` columns
        come from the deck and the next n_not_in_deck columns come from the
        compliment of the deck (card_universe - cardnames)

        args:
            size (tuple): the shape of the returned dataset as a tuple of ints
            n_in_deck (int): number of the dimensions of `size` that are to be
                sampled from the cards in this deck (default: 2)
            n_not_in_deck (int): number of the dimensions of `size` that are to
                be sampled from the cards in the compliment to this deck
                (default: 0)
            force_unique (bool): whether or not we should force the returned
                array to contain unique records (unique along the 0th axis)
                (default: True)
            no_lands (bool): whether or not we should exclude lands (default:
                `self.ignore_lands`)
            **kwargs: passed on to `np.choice` directly

        returns:
            np.ndarray: array of card names selected as declared

        raises:
            DeckError

        """
        # proper default for no_lands matches the constructor call
        no_lands = no_lands or self.ignore_lands

        # some sanity checks on the passed params
        if not n_in_deck + n_not_in_deck == size[1]:
            msg = ('n_in_deck and n_not_in_deck must sum to the requested'
                   ' number of columns in size')
            _LOGGER.error(msg)
            raise DeckError(msg)

        if n_in_deck == 0 and n_not_in_deck == 2:
            _LOGGER.warning('sampling only cards *not* in this deck, you'
                            ' probably want to sample all cards')

        # if we want all records to be unique, we simply iteratively add as many
        # records as remain, dedupe, and repeat until we are at the requested
        # size
        if force_unique:
            # sanity check on the number of unique pairs (pairs sample is our
            # most common use case right now)
            if size[1] == 2 and size[0] > self.max_unique_pairs:
                raise DeckError("can't uniquely sample that many cards")

            # break the problem into two equal chunks for left and right cols
            size_in = size[0], n_in_deck
            size_not = size[0], n_not_in_deck

            # build up our dataset in one or two steps
            concatable = []
            if n_in_deck:
                c_in = _np.random.choice((self.nonland_cardnames
                                          if no_lands else self.cardnames),
                                         size_in, **kwargs)
                concatable.append(c_in)

            if n_not_in_deck:
                c_not = _np.random.choice((self.nonland_compliment_cardnames
                                           if no_lands
                                           else self.compliment_cardnames),
                                          size_not, **kwargs)
                concatable.append(c_not)

            # we built a list of one or two datasets in the two if statements
            # above, now stitch them together side-by-side (columnwise). then,
            # drop duplicates
            c = _np.unique(_np.concatenate(concatable, axis=1), axis=0)

            # the above is either the number of records we requested (if all the
            # sampled pairs were unique) or less than what was requested. until
            # we've reached the required size, keep generating as many pairs as
            # are needed to round out the size, then dedupe, then repeat
            while c.shape[0] < size[0]:
                size_remaining = (size[0] - c.shape[0], size[1])
                size_in_remaining = size_remaining[0], n_in_deck
                size_not_remaining = size_remaining[0], n_not_in_deck

                concatable_remaining = []
                if n_in_deck:
                    c_in_remaining = _np.random.choice((self.nonland_cardnames
                                                        if no_lands
                                                        else self.cardnames),
                                                       size_in_remaining,
                                                       **kwargs)
                    concatable_remaining.append(c_in_remaining)
                if n_not_in_deck:
                    c_not_remaining = _np.random.choice(
                        (self.nonland_compliment_cardnames
                         if no_lands else self.compliment_cardnames),
                        size_not_remaining, **kwargs)
                    concatable_remaining.append(c_not_remaining)

                c_remaining = _np.concatenate(concatable_remaining, axis=1)

                c = _np.unique(_np.concatenate((c, c_remaining), axis=0),
                               axis=0)
            return c

        # no unique, no problem. the world is a lot simpler
        else:
            return _np.random.choice(self.cardnames, size, **kwargs)


def _get_decks(deckurls, decktype):
    """download all decks of a certain deck type from a base url

    args:
        deckurls: (iterable of strings) the urls of our decks
        decktype: (class) the class of the decks we will build (must inherit
            from MtgDeck)

    returns:
        generator of deck objects

    raises:
        None

    """
    for deckurl in deckurls:
        yield decktype(url=deckurl)


# ----------------------------- #
#   deck pool / sampler objects #
# ----------------------------- #

class DeckPool(object):
    """a deck pool is a... pool... of decks"""

    def __init__(self):
        self.decks = []

    def add_decks(self, decks):
        """a smart-ish append method for one or multiple deck objects"""
        try:
            self.decks += decks
        except TypeError:
            try:
                self.decks.append(decks)
            except TypeError:
                raise DeckError("append a single deck or list of decks")

    @property
    def _dropcards(self):
        return set.union(*(_._dropcards for _ in self.decks))

    @property
    def num_decks(self):
        return len(self.decks)

    @property
    def max_chunk_size(self):
        """minimum value of the maximum chunk size across all decks"""
        return min(_.max_unique_pairs for _ in self.decks)

    def choice(self, size, n_in_deck=2, n_not_in_deck=0, **kwargs):
        """sample from the collected decks, breaking size.shape[0]
        up into even chunks among the different decks within

        """
        chunksize = int(_np.ceil(size[0] / self.num_decks)), size[1]
        _LOGGER.debug('chunksize = {}'.format(chunksize))
        c = _np.empty((size), dtype='O')
        for (i, deck) in enumerate(self.decks):
            i0 = i * chunksize[0]
            i1 = min((i + 1) * chunksize[0], size[0])
            _LOGGER.debug('i0, i1 = {}, {}'.format(i0, i1))
            c[i0: i1] = deck.choice((i1 - i0, size[1]), n_in_deck=n_in_deck,
                                    n_not_in_deck=n_not_in_deck, **kwargs)

            if i1 == size[0]:
                break
        return c


class DeckSampler(object):
    """a random sampler for generating pairs of train and test records from a
    pool of known, validated deck recommendations

    """

    def __init__(self, deckpool, allcards):
        self.deckpool = deckpool
        self.allcards = allcards

    def sample(self, n, f_true=0.4, f_half=0.2, no_lands=False):
        """build an (n x 2) gird of true and false records

        args:
            n (int): height of returned array
            f_true (float): number between 0 and 1 for fraction of
                returned records that should be generated from true
                decks (default: 0.5)

        returns:
            np.ndarray: (n x 2) array of names
            np.ndarray: (n x 1) array of labels (0, 1)

        """
        err_msg = None
        if not (0 <= f_true <= 1):
            err_msg = "f_true must be between 0 and 1"
        if not (0 <= f_half <= 1):
            err_msg = "f_half must be between 0 and 1"
        if not (0 <= f_true + f_half <= 1):
            err_msg = "f_true + f_half must be between 0 and 1"

        if err_msg is not None:
            _LOGGER.error(err_msg)
            raise DeckError(err_msg)

        n = int(n)
        ntrue = int(n * f_true)
        nhalf = int(n * f_half)
        nfalse = n - ntrue - nhalf

        names = _np.concatenate([self.deckpool.choice((ntrue, 2),
                                                      replace=True,
                                                      force_unique=True,
                                                      no_lands=no_lands),
                                 self.deckpool.choice((nhalf, 2), n_in_deck=1,
                                                      n_not_in_deck=1,
                                                      replace=True,
                                                      force_unique=True,
                                                      no_lands=no_lands),
                                 self.allcards.choice((nfalse, 2), replace=True,
                                                      force_unique=True,
                                                      no_lands=no_lands), ],
                                axis=0)

        target = _np.zeros(n)
        target[:ntrue] = 1

        return names, target
