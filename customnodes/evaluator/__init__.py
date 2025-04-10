# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later


# NOTE:
# the evaluator module role is to evaluate the value of a socket upstream.
# it will assume that the node class upstream possess 'node.evaluator_properties' set, 
# and an evaluator() function that accepts a socket as argument.
# the evaluator shall return the value for the equivalent passed socket.

# TODO:
# - need some sort of system to see which node is dirty.
# - we could store the evaluated values as a node python numpy property


import bpy
from ...utils.node_utils import parcour_node_tree


def evaluate_upstream_value(sock, match_evaluator_properties:set=None, set_link_invalid:bool=False, cached_values:dict=None):
    """evaluate the value of a socket upstream, fallback to None if the node upstream is not compatible or not linked.
    -Pass a match_evaluator_properties set to check if the node upstream node is compatible. ex: {'INTERPOLATION_NODE',}
    -Pass a set_link_invalid to set the link invalid if the node upstream is not compatible.
    -Pass a cached_values dict to cache the evaluated values, in order to avoid redundand evaluations calculations.
    """

    # if the socket is not links, there's nothing to fetch upstream..
    if (not sock.links):
        return None

    #get colliding nodes upstream, on the left in {socket:links}
    #return a dictionary of {colliding_socket:parcoured_links[]}
    parcour_info = parcour_node_tree(sock, direction='LEFT')
    # print(f"DEBUG: parcour_info: {parcour_info}, len: {len(parcour_info)}")

    #nothing hit?
    if (not parcour_info):
        # print("DEBUG: no parcour info.")
        return None

    #get our colliding socket. when parcouring right to left, we expect only one collision.
    if (len(parcour_info) > 1):
        raise Exception(f"It should not be possible to collide with more than one socket type, when parcouring from right to left. how did you manage that?\n{parcour_info}")

    # Extract the first (and only) item from the dictionary
    colliding_socket = list(parcour_info.keys())[0]
    parcoured_links = parcour_info[colliding_socket]
    colliding_node = colliding_socket.node

    #we are expecting to collide with specific socket types!
    if (not hasattr(colliding_node,'evaluator_properties')) \
        or (not hasattr(colliding_node,'evaluator')) \
        or (not match_evaluator_properties.intersection(colliding_node.evaluator_properties)):
        
        # print(f"DEBUG: parcour not successful.\n{colliding_node}")
        if (set_link_invalid and parcoured_links):
            first_link = parcoured_links[0]
            first_link.is_valid = False
        return None

    #caching system, perhaps multiple input sockets links to the same out socket..
    if (cached_values):
          cachekey = colliding_node.name + ':' + colliding_socket.identifier
          r = cached_values.get(cachekey)
    else: r = None

    if (r is None):
        r = colliding_node.evaluator(colliding_socket)
        if (cached_values):
            cached_values[cachekey] = r

    return r