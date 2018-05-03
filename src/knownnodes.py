import os
import pickle
# import sys
import threading
import time

import state
from bmconfigparser import BMConfigParser
from debug import logger

knownNodesLock = threading.Lock()
knownNodes = {stream: {} for stream in range(1, 4)}

knownNodesTrimAmount = 2000

# forget a node after rating is this low
knownNodesForgetRating = -0.5


def saveKnownNodes(dirName=None):
    if dirName is None:
        dirName = state.appdata
    with knownNodesLock:
        with open(os.path.join(dirName, 'knownnodes.dat'), 'wb') as output:
            pickle.dump(knownNodes, output)


def addKnownNode(stream, peer, lastseen=None, is_self=False):
    if lastseen is None:
        lastseen = time.time()
    knownNodes[stream][peer] = {
        "lastseen": lastseen,
        "rating": 0,
        "self": is_self,
    }


def readKnownNodes():
    try:
        with open(state.appdata + 'knownnodes.dat', 'rb') as source:
            with knownNodesLock:
                knownNodes = pickle.load(source)
    except (IOError, OSError):
        logger.warning(
            'Failed to read nodes from knownnodes.dat', exc_info=True)
    else:
        # the old format was {Peer:lastseen, ...}
        # the new format is {Peer:{"lastseen":i, "rating":f}}
        for stream in knownNodes.keys():
            for node, params in knownNodes[stream].items():
                if isinstance(params, (float, int)):
                    addKnownNode(stream, node, params)

    config = BMConfigParser()
    # if config.safeGetInt('bitmessagesettings', 'settingsversion') > 10:
    #     sys.exit(
    #         'Bitmessage cannot read future versions of the keys file'
    #         ' (keys.dat). Run the newer version of Bitmessage.')

    # your own onion address, if setup
    onionhostname = config.safeGet('bitmessagesettings', 'onionhostname')
    if onionhostname and ".onion" in onionhostname:
        onionport = config.safeGetInt('bitmessagesettings', 'onionport')
        if onionport:
            addKnownNode(1, state.Peer(onionhostname, onionport), is_self=True)


def increaseRating(peer):
    increaseAmount = 0.1
    maxRating = 1
    with knownNodesLock:
        for stream in knownNodes.keys():
            try:
                knownNodes[stream][peer]["rating"] = min(
                    knownNodes[stream][peer]["rating"] + increaseAmount,
                    maxRating
                )
            except KeyError:
                pass


def decreaseRating(peer):
    decreaseAmount = 0.1
    minRating = -1
    with knownNodesLock:
        for stream in knownNodes.keys():
            try:
                knownNodes[stream][peer]["rating"] = max(
                    knownNodes[stream][peer]["rating"] - decreaseAmount,
                    minRating
                )
            except KeyError:
                pass


def trimKnownNodes(recAddrStream=1):
    if len(knownNodes[recAddrStream]) < \
            BMConfigParser().safeGetInt("knownnodes", "maxnodes"):
        return
    with knownNodesLock:
        oldestList = sorted(
            knownNodes[recAddrStream],
            key=lambda x: x['lastseen']
        )[:knownNodesTrimAmount]
        for oldest in oldestList:
            del knownNodes[recAddrStream][oldest]
