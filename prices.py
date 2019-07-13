#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module: prices.py
Author: zlamberty
Created: 2018-10-05

Description:


Usage:
    <usage>

"""

import argparse
import functools
import logging
import logging.config
import os
import time
import yaml

import lxml.html
import pandas as pd
import requests

from pandas.errors import EmptyDataError


# ----------------------------- #
#   Module Constants            #
# ----------------------------- #

HERE = os.path.dirname(os.path.realpath(__file__))
LOGGER = logging.getLogger(__name__)
LOGCONF = os.path.join(HERE, 'logging.yaml')
with open(LOGCONF, 'rb') as f:
    logging.config.dictConfig(yaml.load(f))
LOGGER.setLevel(logging.DEBUG)


# ----------------------------- #
#   Main routine                #
# ----------------------------- #

def login(user, pw):
    """log in to mtggoldfish so we can use them sweet, sweet csv downloads"""
    LOGGER.debug('logging in')
    session = requests.Session()

    # get the "authenticity token" value
    resp = session.get("https://www.mtggoldfish.com")
    root = lxml.html.fromstring(resp.text)
    at_form = root.xpath(
        './/form[contains(@class, "layout-auth-identity-form")]'
    )[0]
    #at_elem = at_form.xpath('.//input[@name="authenticity_token"]')[0]

    # make login form data
    data = {
        _.attrib['name']: _.attrib['value'] for _ in at_form.xpath('.//input')
    }

    data['auth_key'] = user
    data['password'] = pw

    resp = session.post(
        'https://www.mtggoldfish.com/auth/identity/callback',
        data=data,
        allow_redirects=True,
    )

    LOGGER.debug("successfully logged in")

    return session


def set_urls(session=None):
    """generator of urls for different mtg card sets (limit to modern)"""
    session = session or requests
    resp = session.get("https://www.mtggoldfish.com/prices/select")
    root = lxml.html.fromstring(resp.text)
    modern_div = root.xpath(
        './/div[contains(@class, "priceList-setMenu-Modern")]'
    )[0]
    for url in modern_div.xpath('./li[@role="presentation"]/a/@href'):
        if url.startswith('/index') and not url.endswith('modern'):
            setcode = url[-3:]
            seturl = 'https://www.mtggoldfish.com{}#paper'.format(url)
            LOGGER.info('set {} @ {}'.format(setcode, seturl))
            yield (setcode, seturl)


@functools.lru_cache(maxsize=None)
def card_urls(seturl, session=None):
    """list of urls for different cards keyed off of setlists"""
    session = session or requests
    resp = session.get(seturl)
    root = lxml.html.fromstring(resp.text)
    paper_table = root.xpath('.//div[@class="index-price-table-paper"]')[0]
    return [
        'https://www.mtggoldfish.com{}'.format(url)
        for url in paper_table.xpath('.//td[@class="card"]/a/@href')
    ]


def _clean_name(n):
    return n.replace('(', '<').replace(')', '>').replace('//', '%2F%2F')


@functools.lru_cache(maxsize=None)
def card_urls(seturl, setcode, session=None):
    """list of urls built for direct csv download keyed off of setlists"""
    session = session or requests
    csvfmt = 'https://www.mtggoldfish.com/price-download/paper/{} [{}]'
    resp = session.get(seturl)
    root = lxml.html.fromstring(resp.text)
    paper_table = root.xpath('.//div[@class="index-price-table-paper"]')[0]
    return [
        (elem.text, csvfmt.format(_clean_name(elem.text), setcode))
        for elem in paper_table.xpath('.//td[@class="card"]/a')
    ]


@functools.lru_cache(maxsize=None)
def get_prices(url, session=None, throttle_pause=0.0):
    """given a url for a card, parse the price history as a dataframe"""
    session = session or requests
    time.sleep(throttle_pause)
    LOGGER.debug('obtaining pxs for {}'.format(url))
    resp = session.get(url)
    try:
        df = pd.DataFrame([
            dict(zip(['px_date', 'px'], line.split(',')))
            for line in resp.text.splitlines()
        ])

        # some cards *exist* but have no prices (e.g. Ajani, Valiant Protector
        # in AER only exists in foil, but you can download non-foil prices)
        if df.empty:
            LOGGER.warning('no prices for {}'.format(os.path.basename(url)))
            return df

        # otherwise, merry way
        df.px_date = pd.to_datetime(df.px_date)
        df.px = df.px.replace('', 'nan')
        df.px = df.px.astype('float')
        return df
    except ValueError:
        if resp.text.strip() == 'Throttled':
            throttle_pause = max(throttle_pause * 2, 30)
            LOGGER.debug('throttled')
            LOGGER.debug('increasing throttle pause to {}'.format(throttle_pause))
            return get_prices(url, session, throttle_pause)
        raise


def load_from_csv(csvdir='.'):
    """given csvdir, load contents of mtg sets into a dataframe"""
    df = pd.DataFrame()
    for basename in os.listdir(csvdir):
        LOGGER.debug("loading {}".format(basename))
        try:
            dfnow = pd.read_csv(
                os.path.join(csvdir, basename), parse_dates=['px_date']
            )
            df = df.append(dfnow, ignore_index=True)
        except EmptyDataError:
            LOGGER.debug("csv {} was empty".format(basename))

    LOGGER.debug("loaded all files")
    df = df.reset_index(drop=True)

    LOGGER.debug("converting name and set into categories")
    df.card_name = df.card_name.astype('category')
    df.setcode = df.setcode.astype('category')

    return df


def main(user, pw, csvdir='.', force_refresh=False):
    """attempt to get the prices of every modern card

    args:
        csvdir (str): path to output csv directory

    returns:
        None

    raises:
        None

    """
    session = login(user, pw)
    for setcode, seturl in set_urls(session=session):
        fcsv = os.path.join(csvdir, "{}.csv".format(setcode))
        if os.path.isfile(fcsv) and not force_refresh:
            LOGGER.debug('results cached for set {}'.format(setcode))
            continue

        df = pd.DataFrame()
        for (cardname, cardurl) in card_urls(seturl, setcode, session=session):
            dfnow = get_prices(cardurl, session=session)
            # skip empty cards (successfully parsed but not priced)
            if dfnow.empty:
                continue
            dfnow.loc[:, 'card_name'] = cardname
            df = df.append(dfnow, ignore_index=True)

        # non-foil masterpiece sets exist but are empty
        if df.empty:
            LOGGER.warning('set {} has no cards in it'.format(setcode))
        else:
            df.loc[:, 'setcode'] = setcode
        df = df.reset_index(drop=True)

        df.to_csv(fcsv, header=True, index=False)


# ----------------------------- #
#   Command line                #
# ----------------------------- #

def parse_args():
    """ Take a log file from the commmand line """
    parser = argparse.ArgumentParser()
    parser.add_argument("-x", "--xample", help="An Example", action='store_true')

    args = parser.parse_args()

    LOGGER.debug("arguments set to {}".format(vars(args)))

    return args


if __name__ == '__main__':

    args = parse_args()

    main()
