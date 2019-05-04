# -*- coding: utf-8 -*-
# !/usr/bin/env python

# unoinspect is object inspectors for LibreOffice
# Copyright (C) 2017-2019  Sasa Kelecevic
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA


from json import dump
from inspect import getsourcefile
from os.path import abspath, dirname, join, realpath

import uno
from com.sun.star.beans.MethodConcept import ALL as _METHOD_CONCEPT_ALL
from com.sun.star.beans.PropertyConcept import ALL as _PROPERTY_CONCEPT_ALL
from com.sun.star.reflection.ParamMode import (
    IN as _PARAM_MODE_IN,
    OUT as _PARAM_MODE_OUT,
    INOUT as _PARAM_MODE_INOUT,
)

_PATH = abspath(getsourcefile(lambda: 0))
# output file path
_DIR = dirname(_PATH)
_RESULTFILE = "result.txt"

# print('**********************')
# print('_PATH = ' + _PATH)
# print('_DIR = ' + _DIR)
# print('_RESULTFILE = ' + _RESULTFILE)


def _mode_to_str(mode):
    ret = "[]"
    if mode == _PARAM_MODE_INOUT:
        ret = "[inout]"
    elif mode == _PARAM_MODE_OUT:
        ret = "[out]"
    elif mode == _PARAM_MODE_IN:
        ret = "[in]"
    return ret


# -----------------------------------------------------------
#               INSPECTION
# -----------------------------------------------------------


class Inspector:
    """Object introspection

    """

    def __init__(self):

        try:
            self.ctx = uno.getComponentContext()
        except Exception as err:
            print(err)

        self.smgr = self.ctx.ServiceManager
        self.introspection = self.ctx.getValueByName(
            "/singletons/com.sun.star.beans.theIntrospection"
        )
        self.reflection = self.ctx.getValueByName(
            "/singletons/com.sun.star.reflection.theCoreReflection"
        )
        self.documenter = self.ctx.getValueByName(
            "/singletons/com.sun.star.util.theServiceDocumenter"
        )

    def _inspectProperties(self, object):
        """Inspect properties

        :param object: Inspect properties for object

        """

        P = {}
        try:
            inspector = self.introspection.inspect(object)
            # properties
            properties = inspector.getProperties(_PROPERTY_CONCEPT_ALL)
            for property in properties:
                try:
                    # name
                    p_name = str(property.Name)
                    P[p_name] = {}
                    # description
                    P[p_name]["desc"] = "uno_property"

                    # type
                    typ = str(property.Type.typeName)

                    # repr
                    if hasattr(object, p_name):
                        prop_value = getattr(object, p_name, None)
                        if typ in [
                            "[]string",
                            "[]type",
                            "[]com.sun.star.datatransfer.DataFlavor",
                            "[]com.sun.star.sheet.opencl.OpenCLPlatform",
                        ]:
                            t = "<tuple with {} elements>".format(
                                str(len(prop_value))
                            )
                            typ = "tuple"
                        elif typ in ["[]com.sun.star.beans.PropertyValue"]:
                            t = "<tuple with {} elements>".format(
                                str(len(prop_value))
                            )
                            typ = ".beans.PropertyValue"
                        elif str(prop_value).startswith("pyuno object"):
                            t = "pyuno object"
                        elif typ == "string":
                            # if prop_value not in ['True', 'False', 'None']:
                            t = "'{}'".format(prop_value)
                        elif typ == "boolean" and prop_value == 0:
                            t = "None"
                        else:
                            t = str(prop_value)

                    else:
                        t = "<unknown>"

                    typ = typ.replace("com.sun.star", "")

                    P[p_name]["type"] = typ
                    P[p_name]["repr"] = t
                    P[p_name]["items"] = []

                except Exception as err:

                    P[p_name]["type"] = typ
                    P[p_name]["repr"] = "<unknown>"
                    all_items = []
                    P[p_name]["items"] = all_items
        except:
            pass

        return P

    def _inspectMethods(self, object):
        """Inspect methods

        :param object: Inspect methods for object

        """

        M = {}

        try:
            inspector = self.introspection.inspect(object)

            # methods
            methods = inspector.getMethods(_METHOD_CONCEPT_ALL)
            for method in methods:

                # name
                m_name = str(method.Name)
                try:
                    M[m_name] = {}
                    # description
                    M[m_name]["desc"] = "uno_method"
                    # type
                    typ = str(method.getReturnType().getName())
                    typ = typ.replace("com.sun.star", "")
                    M[m_name]["type"] = typ

                    all_items = []
                    # name access
                    if m_name == "getByName":
                        items = object.getElementNames()
                        # escape bytes
                        for item in items:
                            all_items.append(str(item))
                        M[m_name]["items"] = sorted(all_items)

                    # index access
                    elif m_name == "getByIndex":
                        items = object.getCount()
                        M[m_name]["items"] = [
                            str(item) for item in range(0, items)
                        ]

                    # supported services
                    elif m_name == "getSupportedServiceNames":
                        items = object.getSupportedServiceNames()
                        M[m_name]["items"] = sorted(items)

                    # enumerate
                    elif m_name == "createEnumeration":
                        idx = len(list(object))
                        all_items.append(str(idx))
                        M[m_name]["items"] = all_items

                    else:
                        # pass
                        M[m_name]["items"] = all_items

                    # repr
                    args = method.ParameterTypes
                    infos = method.ParameterInfos

                    params = "( "
                    for i in range(0, len(args)):

                        params = (
                            params
                            + _mode_to_str(infos[i].aMode)
                            + " "
                            + str(args[i].Name)
                            + " "
                            + str(infos[i].aName)
                            + ", "
                        )

                    params = params + ")"
                    params = params.replace(", )", " )")

                    if params == "()":
                        params = "()"

                    M[m_name]["repr"] = str(params)

                except Exception as err:
                    M[m_name]["type"] = "ERROR"
                    M[m_name]["repr"] = str(err)
                    all_items = []
                    M[p_name]["items"] = all_items

        except:
            pass

        return M

    def _inpectPython(self, object):

        """Inspect standard Python

        :param object: Inspect attrbutes for object

        """

        S = {}

        try:

            for name in dir(object):
                if name.startswith("__"):
                    continue

                atr = getattr(object, name)

                # name
                S[name] = {}

                # description
                S[name]["desc"] = "python"

                # type
                typ = str(type(atr))
                typ = typ.replace("<class ", "").replace(">", "")
                typ = typ.replace("'", "")

                # repr
                if typ == "dict":
                    t = "<dict with {} elements>".format(str(len(repr(atr))))
                else:
                    t = repr(atr)

                S[name]["type"] = typ
                S[name]["repr"] = t
                all_items = []
                S[name]["items"] = all_items

        except:
            S[name]["type"] = "ERROR"
            S[name]["repr"] = ""
            all_items = []
            S[name]["items"] = all_items

        return S

    def inspect(self, object, output="json"):
        """Inspect object
        :param object:  Inspect this object
        :param output:  'console': display result in terminal
                        'dict': return dict
                        'json': store result in json file, default
        Inspector store result in 'result.txt' file in unoinspect.py directory
        Return properties and methods
        """
        # store result in dictionary
        context = {}

        if object is None:
            return context
        else:
            # inspect UNO properties and methods
            p = self._inspectProperties(object)
            m = self._inspectMethods(object)

            # UNO object
            if p and m:
                context.update(sorted(p.items()))
                context.update(sorted(m.items()))

            # not UNO object - try python
            else:
                s = self._inpectPython(object)
                if s:
                    context.update(sorted(s.items()))

        # display result in terminal
        if type == "console":
            for key, value in sorted(context.items()):
                # print('KEY: ' + str(key))
                # print('VALUE: ' + str(value))
                for tp, rep in value.items():
                    t = context[key]["type"]
                    r = context[key]["repr"]
                print("{:<35}".format(key) + "{:<35}".format(t) + r)

        # return dict
        elif type == "dict":
            return context

        # store result in json file
        elif output == "json":
            file_path = join(_DIR, _RESULTFILE)
            with open(file_path, "w") as outfile:
                dump(context, outfile, indent=4)

    def showServiceDocs(self, object):
        """Open browser to show service documentation
        :param object: show docs for this object
        """
        return self.documenter.showServiceDocs(object)

    def showInterfaceDoc(self, object):
        """Open browser to show interface documentation
        :param object: show docs for this object
        """
        return self.documenter.showInterfaceDoc(object)

    def getOutputPath(self):
        """Show full path for output file
        """
        path = join(_DIR, _RESULTFILE)
        return path


def main():
    pass


if __name__ == "__main__":
    main()
