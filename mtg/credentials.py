#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module: credentials
Created: 2019-07-14

Description:

    just holds links out to credentials. simple shit

Usage:

    >>> import credentials

"""

import os

import yaml

# ----------------------------- #
#   Module Constants            #
# ----------------------------- #

SECRETS_DIR = os.path.expanduser(os.path.join('~', '.secrets'))
F_NEO_CONF = os.path.join(SECRETS_DIR, 'neo4j.yaml')

# ----------------------------- #
#   main functions              #
# ----------------------------- #

def load_neo_config(f_neo_creds=F_NEO_CONF):
    with open(f_neo_creds) as fp:
        return yaml.load(fp, yaml.FullLoader)
