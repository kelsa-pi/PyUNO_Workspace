# -*- coding: utf-8 -*-
# PyUNO Workspace helper module
from re import findall
from os.path import join


def splitName(name):
    """ splitName(name)
    Split an object name in parts, taking dots and indexing into account.
    """
    name = name.replace("[", ".[")
    parts = name.split(".")
    return [p for p in parts if p]


def splitNameCleaner(name):
    """ splitNameCleaner(name)
    Split an object name in parts, taking dots, quotes, indexing etc. into account.
    Object name with extra dots eg. ctx.getByName("/singletons/com.sun.star.beans.theIntrospection"),
    enumerated objects eg. list(document.Text)
    """
    name = name.replace("[", ".[")
    parts = name.split(".")

    # Fix extra dots
    if '"' in parts[-1]:
        extra_dots = findall(r'"(.*?)"', name)
        if extra_dots:
            for part in extra_dots:
                new = part.replace(".", "_")
                new_name = name.replace(part, new)

            new_parts = new_name.split(".")
            np = [p for p in new_parts if p]

    else:

        np = [p for p in parts if p]

    # Fix list
    if np[0].startswith("list(list(") and np[-1].endswith(")"):
        np[0] = np[0].replace("list(list(", "list(")
        np[-1] = np[-1][:-1]
        np.append(np[-1])

    elif np[0].startswith("list(") and np[-1].endswith(")"):
        np[0] = np[0].replace("list(", "")
        np[-1] = np[-1][:-1]
        np.append(np[-1])

    return np


def joinName(parts):
    """ joinName(parts)
    Join the parts of an object name, taking dots and indexing into account.
    """

    name = ".".join(parts)
    return name.replace(".[", "[")
