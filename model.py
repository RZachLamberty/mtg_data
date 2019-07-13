#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module: model.py
Author: zlamberty
Created: 2018-05-15

Description:
    collecting various utility functions and modeling approaches for analyzing
    card and deck behavior. this is meant to be more specific to my modelling
    approaches than any of the individual libraries (e.g. there is a regular
    dataframe view of card detail, and then there is this hyper-processed view I
    define below)

Usage:
    <usage>

"""

import logging

import tqdm

import cards as C
import modelutils
import wikiinfo


# ----------------------------- #
#   Module Constants            #
# ----------------------------- #

_LOGGER = logging.getLogger(__name__)

_IGNORE_TYPES = ['Plane', 'Scheme', 'Vanguard']
_IGNORE_SETS = ['UGL', 'UNH', "UST"]


# ----------------------------- #
#   Main routine                #
# ----------------------------- #

def cards_and_text(url=C.CARD_URL, ignore_types=_IGNORE_TYPES,
                   ignore_sets=_IGNORE_SETS, cat_size_thresh=30,
                   vectorizer_kwargs=modelutils._COUNT_VECTORIZER_KWARGS):
    """there are a ton of things to clean up from the standard (useful) card
    dataframe. do those all here

    args:
        url (str): url that defines the json endpoint (default: `C.CARD_URL`)
        ignore_types (list): list of string type names that we should ignore
            (case insensitive) (default: `_IGNORE_TYPES`)
        ignore_sets (list): list of string set names that we should ignore
            (case insensitive, all caps) (default: `_IGNORE_SETS`)
        cat_size_thresh (int): number of elements that must appear in a single
            category of a multi-categorical to warrant a separate binary
            categorical feature
        vectorizer_kwargs (dict): the encapsulated kwargs for the vectorize
            function (this will mostly be arguments to a sklearn feature
            extraction text vectorizer). (default:
            model_utils._VECTORIZER_KWARGS)

    returns:
        pd.DataFrame: the formalized and feature-embedded cards dataframe
        pd.DataFrame: the text content after keyword removal, tokenization, etc

    """
    cards = C.cards_df()

    # drop some types of cards because they are dumb
    cards = _filter_by_type(cards, ignore_types)

    # drop reserved list cards because I am not a billionaire
    # shit... this drops a ton of good cards. if we want to handle
    # set legality or price, let's find a different / better way
    # to do it (e.g. using the actual price column)
    #cards = cards[cards.reserved != True]

    # drop unsets because they cause a billion problems and also aren't legal
    cards = cards[~cards.setname.isin(ignore_sets)]

    # get rid of multiple printings
    cards = cards.sort_values(
        by=['name', 'multiverseid'],
        ascending=False,
        na_position='last'
    ).groupby('name').first()

    # split off text and return it separately
    cards_text = cards[['text']].copy()

    # drop a handful o' columns
    keepcols = [
        'cmc',
        'colorIdentity',
        'types', 'subtypes', 'supertypes',
        'manaCost',
        'power', 'toughness',
        'rarity',
        # stuff I could have kept but want to KISS
        #'loyalty',
    ]
    cards = cards[keepcols]

    # multiple categoricals for several categoricals!
    multicats = ['colorIdentity', 'types', 'subtypes', 'supertypes']
    for multicat in tqdm.tqdm(multicats):
        cards = modelutils.add_multi_category_dummies(
            df=cards,
            dummy_colname=multicat,
            cat_size_thresh=cat_size_thresh
        )

    # fixing mana cost
    # it would be nice if we could leverage the same function as above (e.g. if
    # we just define a more clever preprocessor function of convert the provided
    # column to a list a la the multicategorical columns), but that is not
    # possible -- in order to capture hybrid mana, we must have this weird
    # factor of .5 interjected as we are counting.
    cards = _add_manacost_dummies(cards)

    # fixing power and toughness with stars and shit
    cards = _fix_power_and_toughness(cards)

    # remaining simple categoricals are easy to fix (it's just rarity)
    cards = pd.get_dummies(
        cards,
        dummy_na=cards.rarity.isnull().any(),
        columns=['rarity']
    )

    # new feature: existence of keywords
    keywordtext = wikiinfo.reminder_text()

    # keywords are *so close* to multicategorical, but it's actually just
    # annoying to go out of our way to re-use that function
    cards = _add_keyword_dummies(
        cards=cards,
        cards_text=cards_text,
        keywordtext=keywordtext,
        cat_size_thresh=cat_size_thresh,
    )

    # card text
    # preprocess (convert items to generic tokens for better featurization,
    # cleanup text, etc). this will leave us with a documents column which is
    # suitable for passing to the text vectorizing and embedding functions in
    # modelutils
    cards_text = _process_cards_text(cards_text)

    # documents = cards_text.documents.values
    return cards, cards_text


def _filter_by_type(cards, ignore_types):
    """subset the provided data frame down to the records which do not
    contain the provided ignorable card types

    """
    ignore_types = [_.lower() for _ in ignore_types]
    def f(typelist):
        try:
            typeset = {_.lower() for _ in typelist}
            return typeset.intersection(ignore_types) == set()
        except TypeError:
            # nans don't like being iterated
            return False
    is_ignore_type = cards.types.apply(f)
    cards = cards[~is_ignore_type]
    assert cards[
        cards.name.isin(['Barrin', 'Behold My Grandeur', 'Tember City'])
    ].empty

    return cards


def _add_manacost_dummies(cards):
    """like the multicategorical dummy function but weighting hybred and
    phyrexian mana in a special way

    """
    _LOGGER.debug("adding mana cost categorical features")

    # subset cards to those which have a manacost
    idx_mcnn = cards.manaCost.notnull()

    for c in 'WUBRGX':
        col = 'manaCost_{}'.format(c)
        # find regular mana symbols "{[color]}"
        cards.loc[idx_mcnn, col] = cards[idx_mcnn].manaCost.str.count(
            '{{{}}}'.format(c)
        )

        # find hybrid mana "{[color]/[color]}" and phyrexian mana "{[color]/P}"
        hybrid_phyrexian_symbol = '\{{(?:{}/\w+|\w+/{})\}}'.format(c, c)
        cards.loc[idx_mcnn, col] = (
            cards.loc[idx_mcnn, col]
            + .5 * cards[idx_mcnn].manaCost.str.count(hybrid_phyrexian_symbol)
        )

    # extract the number for the colorless parts "{N}"
    cards.loc[idx_mcnn, 'manaCost_0'] = cards[idx_mcnn].manaCost.str.extract(
        '\{(\d+)\}', expand=False
    ).astype(float)

    # we don't have any use for manaCost now
    cards.drop('manaCost', axis=1, inplace=True)

    # fillna (manacost is 0), and create a nan indicator
    manacostcols = ['manaCost_{}'.format(_) for _ in 'WUBRGX0']
    cards.loc[:, manacostcols] = cards[manacostcols].fillna(0)
    cards.loc[:, 'manaCost_nan'] = cards[manacostcols].sum(axis=1) == 0

    return cards


def _fix_power_and_toughness(cards):
    """power and toughness often have stars and nonsense"""
    repls = ['*', '1+*', '2+*', '7-*']
    cards.loc[:, 'power_star'] = cards.power.isin(repls)
    cards.loc[:, 'toughness_star'] = cards.toughness.isin(repls)

    # replace star terms above with nans
    repldict = {_: np.nan for _ in repls}
    ptcols = ['power', 'toughness']
    cards = cards.replace({_: repldict for _ in ptcols})
    cards.loc[:, ptcols] = cards[ptcols].astype(float)

    # replace power and toughness nans with minimum vals -1
    for pt in ptcols:
        cards.loc[cards[pt].isnull(), pt] = cards[pt].min() - 1

    return cards


def _add_keyword_dummies(cards, cards_text, keywordtext, cat_size_thresh=30):
    """take the keywords and their blah blah blah and create a new
    multi-categorical-esque feature

    """
    re_kw = r'(\b(?:{})\b)'.format('|'.join(keywordtext))

    dfkw = cards_text.text.fillna('') \
                          .str.lower() \
                          .str.extractall(re_kw) \
                          .reset_index()
    dfkw.loc[:, 'match'] = True
    dfkw.columns = ['name', 'is_kw', 'kw']

    # a kw happening twice in a card is possible now (c.f. Abandoned Outpost)
    dfkw.drop_duplicates(inplace=True)

    # pick out only the most popular keywords for categories
    # unlike the multi-cat case, no nan or other will be populated
    # here -- learn that in the text features, I guess
    vc = dfkw.kw.value_counts()
    keepers = vc[vc > cat_size_thresh].index
    dfkw = dfkw[dfkw.kw.isin(keepers)]

    # renaming kws so they are better column names
    dfkw.kw = 'kw_' + dfkw.kw.str.replace(' ', '_')

    # pivot
    dfpivot = dfkw.pivot_table(
        index='name',
        columns='kw',
        values='is_kw',
        fill_value=False
    )
    kwcols = dfpivot.columns

    # join that back in to cards
    cards = cards.join(dfpivot, how='left')
    cards.loc[:, kwcols] = cards[kwcols].fillna(False)

    # delete the created dfs (space constraints)
    del dfpivot, dfkw

    return cards


def _process_cards_text(cards_text):
    """process raw cards text dfs into tokenized, vectorized features"""
    # bare necessities, those simple bare necessities
    cards_text.loc[:, 'document'] = cards_text.text.fillna('').str.lower()

    # drop self-references (as in "CARDNAME enters the battlefield...")
    def card_name_repl(row):
        fn = row.name.lower()
        sn = fn.split('(')[0].split(',')[0]
        return re.sub('{}|{}'.format(fn, sn), "", row.document).strip()

    cards_text.loc[:, 'document'] = cards_text[['document']].apply(
        card_name_repl, axis=1
    )

    # for keywords, drop the annoying "keyword N (....)" strings
    # see before/after for Abbot of Keral Keep (cards_text.head(10))
    pattern = '((?:{})(?: [^)]+)?) \(.*\)'.format(
        '|'.join(sorted(keywordtext.keys()))
    )
    cards_text.loc[:, 'document'] = cards_text.document.str.replace(
        pattern, repl='\\1', case=False
    )

    # replace color symbols (e.g. "{W}")
    cards_text.loc[:, 'document'] = cards_text.document.str.replace(
        '\{[WUBRG]\}', repl=COLOR + ' ', case=False
    )

    # replace color words (e.g. "red", "blue")
    cards_text.loc[:, 'document'] = cards_text.document.str.replace(
        '(?<!\w)(?:white|blue|black|red|green)(?!\w)',
        repl=COLOR + ' ',
        case=False
    )

    # replace color identity mana sources
    cards_text.loc[:, 'document'] = cards_text.document.str.replace(
        '(?<!\w)(?:plain|island|swamp|mountain|forest)((?:s|walk|cycling)?)(?!\w)',
        repl=MS + '\\1 ',
        case=False
    )

    # replace all activated ability prices with tokens
    cards_text.loc[:, 'document'] = cards_text.document.str.replace(
        '\{\w+\}\s*:?', repl=ACTIVATED_ABILITY_PRICE + ' ', case=False
    )

    # replace all remaining numbers with a number token
    number_words = [
        'zer', 'one', 'two', 'three', 'four', 'five', 'six',
        'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve',
        'thirteen',  'fourteen', 'fifteen', 'sixteen',
        'seventeen', 'eighteen', 'nineteen', 'twenty'
    ]
    number_word_regs = [r'(?<!\w){}(?!\w)'.format(_) for _ in number_words]
    number_reg = '|'.join(
        ['\d+'] + number_word_regs
    )
    cards_text.loc[:, 'document'] = cards_text.document.str.replace(
        number_reg, repl=NUMBER + ' ', case=False
    )

    # replace all punctuation characters
    trans = str.maketrans('', '', string.punctuation)
    cards_text.loc[:, 'document'] = cards_text.document.str.translate(trans)

    # one quick assertion test
    assert cards_text[
        cards_text.document.str.contains('island')
    ].document.head().empty

    return cards_text


# ----------------------------- #
#   Command line                #
# ----------------------------- #

def parse_args():
    """ Take a log file from the commmand line """
    parser = argparse.ArgumentParser()
    parser.add_argument("-x", "--xample", help="An Example", action='store_true')

    args = parser.parse_args()

    logger.debug("arguments set to {}".format(vars(args)))

    return args


if __name__ == '__main__':

    args = parse_args()

    main()
