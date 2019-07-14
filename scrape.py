#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module: scrape.py
Author: zlamberty
Created: 2016-02-14

Description:
    a top-level script for reading cards and decks and persisting them to neo4j

Usage:

    $ python scrape.py

"""

import argparse
import logging.config
import os
import yaml


from mtg import cards, utils, decks
from mtg.config import F_LOGGING_CONFIG
from mtg.load.graphdb import NEO4J_URI

# ----------------------------- #
#   Module Constants            #
# ----------------------------- #

# credential file
F_CRED = os.path.expanduser(
    os.path.join('~', '.secrets', 'aws.neo4j.credentials.yaml'))

# logging and file IO constants
logging.getLogger("requests").setLevel(logging.WARNING)
logger = logging.getLogger("scrape")

with open(F_LOGGING_CONFIG, 'rb') as f:
    logging.config.dictConfig(yaml.load(f))


# ----------------------------- #
#   Main routine                #
# ----------------------------- #

def main(decksrc='scg2', neo4juri=NEO4J_URI, credyaml=F_CRED):
    """do ery ol thang

    args:
        decksrc: string, the source of deck database elements we should parse
            into json for loading into our neo4j database. currently, only
            "scg2" is a supported option (default: scg2)
        neo4juri: string, the uri of the neo4j database into which we will load
            card and deck info (default: common.NEO4J_URI)

    returns: Nothing

    raises:
        ValueError: unhandled decksrc value

    """
    with open(credyaml, 'r') as f:
        creds = yaml.load(f)

    cards.json_to_neo4j(neo4juri=neo4juri, **creds)
    if decksrc == 'scg2':
        decks.load_decks_to_neo4j(neo4juri=neo4juri, **creds)
    else:
        raise ValueError(
            "decksrc '{}' is not a valid deck src enumeration".format(decksrc))


# ----------------------------- #
#   Command line                #
# ----------------------------- #

def parse_args():
    """ Take a log file from the commmand line """
    parser = argparse.ArgumentParser()

    decksrc = "type of deck source we are using"
    parser.add_argument("-d", "--decksrc", help=decksrc, default='scg2')

    neo4juri = "uri of the neo4j database"
    parser.add_argument("-u", "--neo4juri", help=neo4juri,
                        default=utils.NEO4J_URI)

    credyaml = "credentials holding neo4j db credentials"
    parser.add_argument('-c', "--credyaml", help=credyaml, default=F_CRED)

    args = parser.parse_args()

    logger.debug("arguments set to {}".format(vars(args)))

    return args


if __name__ == '__main__':
    args = parse_args()
    main(decksrc=args.decksrc, neo4juri=args.neo4juri, credyaml=args.credyaml)
