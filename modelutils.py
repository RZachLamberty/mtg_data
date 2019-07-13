#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module: modelutils.py
Author: zlamberty
Created: 2018-05-15

Description:
    utilities for our modelling approach -- these are the sorts of things that
    definitely could make it into a general purpose model-building, training,
    and scoring library

Usage:
    <usage>

"""

import logging

import pandas as pd
import sklearn.decomposition
import sklearn.feature_extraction


# ----------------------------- #
#   Module Constants            #
# ----------------------------- #

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.INFO)

class ModelUtilsError(Exception):
    pass


# ----------------------------- #
#   data munging and prep       #
# ----------------------------- #

_IDENTITY = lambda x: x


def add_multi_category_dummies(df, dummy_colname, cat_size_thresh=30,
                               preprocessor=_IDENTITY, tokenizer=_IDENTITY,
                               other_cat=True, nan_cat=True):
    """convert features which are iterables of values into categorical flags.

    an example use case: recipes with multiple ingredients. one column
    (ingredients) has values like ["rice", "beans"] and ["rice", "tomatos"]
    (that is, the values of this feature are lists). this single column would be
    converted into three columns ("is_rice", "is_beans", "is_tomatoes").

    because we are hacking the sklearn countvectorizer we can do funky things by
    defining a clever preprocessor or tokenizer. as written, they will use the
    identity function (`lambda x: x`)

    args:
        df (pd.DataFrame): a dataframe which has a mutlicategorical column
        dummy_colname (str): column name of multicategorical column
        cat_size_thresh (int): a required number of instances of a given
            category before it gets its own feature. if only one in one million
            ingredeint lists contains "sharks head", don't create a
            "is_sharks_head" feature (default: 30)
        preprocessor (function): function which will be passed to sklearn
            CountVectorizer for "text" token preparation (obviously doesn't need
             to be strings) (default: `_IDENTITY`)
        tokenizer (function): function which will be passed to sklearn
            CountVectorizer for "text" token preparation (obviously doesn't need
             to be strings) (default: `_IDENTITY`)
        other_cat (bool): whether or not to include a category indicating the
            existence of a value that didn't surpass our provided threshold
            (default: True)
        nan_cat (bool): whether or not to include a category indicating no
            values at all (a nan) (default: True)

    returns:
        pd.DataFrame: the input data frame with the dummy_colname dropped and
            N new binary target features

    raises:

    """
    _LOGGER.debug(
        'calculating dummy categories for column "{}"'.feature(dummy_colname)
    )
    preprocessor = tokenizer = lambda x: x
    countvect = sklearn.feature_extraction.text.CountVectorizer(
        preprocessor=preprocessor,
        tokenizer=tokenizer,
        # can't use the thresh here if we want "other" information
        #min_df=cat_size_thresh
    )

    col_non_null = df.colorIdentity.notnull()

    dfmc = pd.DataFrame(
        data=countvect.fit_transform(
            df[col_non_null][dummy_colname].values
        ).toarray(),
        columns=sorted(countvect.vocabulary_),
        index=col_non_null[col_non_null].index
    )

    # add all columns that don't meet the threshold into an `other` column, then
    # binarize it
    other_cat_colnames = dfmc.sum()[dfmc.sum() < cat_size_thresh].index
    if not other_cat_colnames.empty:
        dfmc.loc[:, 'other'] = dfmc[other_cat_colnames].sum(axis=1) > 0
        dfmc.loc[:, 'other'] = dfmc.other.astype(int)
        dfmc.drop(columns=other_cat_colnames, inplace=True)

    # change the column names to reflect the category
    dfmc.columns = [
        '{}_{}'.format(dummy_colname, _.replace(' ', '_'))
        for _ in dfmc.columns
    ]

    # join that back into df
    df = df.join(dfmc, how='left')

    # add nan records
    df.loc[~col_non_null, '{}_nan'.format(dummy_colname)] = 1
    cols = dfmc.columns.tolist() + ['{}_nan'.format(dummy_colname)]

    # replace nans (unknown values) with 0 (we know they aren't cat X)
    df[cols] = df[cols].fillna(0)

    return df


# ----------------------------- #
#   model training and scoring  #
# ----------------------------- #
