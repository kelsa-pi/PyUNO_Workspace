# -*- coding: utf-8 -*-
# !/usr/bin/env python

# unoinspect is object inspectors for LibreOffice
# Copyright (C) 2017  Sasa Kelecevic
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

import uno
from json import dump
import pickle
import sys
from com.sun.star.beans.MethodConcept import \
    ALL as _METHOD_CONCEPT_ALL
from com.sun.star.beans.PropertyConcept import \
    ALL as _PROPERTY_CONCEPT_ALL
from com.sun.star.reflection.ParamMode import \
    IN as _PARAM_MODE_IN, \
    OUT as _PARAM_MODE_OUT, \
    INOUT as _PARAM_MODE_INOUT
    
from inspect import getsourcefile
from os.path import abspath, dirname, join

_PATH = abspath(getsourcefile(lambda: 0))
_DIR = dirname(_PATH)
_RESULTFILE = 'result.txt'


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
    def __init__(self, context=None):
        
        if context:
            try:
                self.ctx = context
            except Exception as err:
                print(err)
        else:
            try:
                self.ctx = uno.getComponentContext()
            except Exception as err:
                print(err)
                
        self.smgr = self.ctx.ServiceManager
        self.desktop = self.ctx.getValueByName('/singletons/com.sun.star.frame.theDesktop')
        self.introspection = self.ctx.getValueByName("/singletons/com.sun.star.beans.theIntrospection")
        self.reflection = self.ctx.getValueByName("/singletons/com.sun.star.reflection.theCoreReflection")
        self.documenter = self.ctx.getValueByName('/singletons/com.sun.star.util.theServiceDocumenter')

    def _inspectProperties(self, object):
        """Inspect properties

        :param object: Inspect this object

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
                    # type
                    typ = str(property.Type)
                    typ = typ.split('(')
                    typ = typ[0].replace('<Type instance ', '')
                    typ = typ.replace('com.sun.star', '')
                    P[p_name]['type'] = typ.strip()
                    # repr
                    v = object.getPropertyValue(p_name)
                    t = str(v)
                    if t.startswith("pyuno object"):
                        v = "()"
                    if t.startswith("("):
                        v = "()"
                    
                    P[p_name]['repr'] = str(v)
                except:

                    P[p_name]['repr'] = "()"

        except:
            pass

        return P

    def _inspectMethods(self, object):
        """Inspect methods

        :param object: Inspect this object

        """
        M = {}
        try:
            inspector = self.introspection.inspect(object)
            # methods
            methods = inspector.getMethods(_METHOD_CONCEPT_ALL)
            for method in methods:
                # name
                m_name = str(method.Name)
                M[m_name] = {}
                # type
                typ = str(method.getReturnType().getName())
                typ = typ.replace('com.sun.star', '')
                M[m_name]['type'] = typ
                
                all_items = []
                # name access
                if m_name == 'getByName':
                    items = object.getElementNames()
                    # escape bytes
                    for item in items:
                        all_items.append(str(item))
                    M[m_name]['items'] = sorted(all_items)
                
                # index access
                elif m_name == 'getByIndex':
                    items = object.getCount()
                    M[m_name]['items'] = [str(item) for item in range(0, items)]
                
                # supported services
                elif m_name == 'getSupportedServiceNames':
                    items = object.getSupportedServiceNames()
                    M[m_name]['items'] = sorted(items)
                
                # enumerate
                elif m_name == 'createEnumeration':
                    idx = len(list(object))
                    all_items.append(str(idx))
                    M[m_name]['items'] = all_items
                
                else:
                    # pass
                    M[m_name]['items'] = all_items

                # repr
                args = method.ParameterTypes
                infos = method.ParameterInfos
                
                params = "( "
                for i in range(0, len(args)):
                    
                    params = params + _mode_to_str(infos[i].aMode) + " " + str(args[i].Name) + " " + str(infos[i].aName) + ", "
                
                params = params + ")"
                
                if params == "()":
                    params = "()"

                M[m_name]['repr'] = str(params)
        except:
            pass
        
        return M

    def inspect(self, object, item=None, output='json', dir=_DIR, filename=_RESULTFILE):
        """Inspect object

        :param object: Inspect this object
        :param item: List of properties and methods to inspect, optional
        :param output: 'stdout': display result in sys.stdout
                       'console': display result in terminal
                       'dict': return dict
                       'json': store result in json file, default
                       'pickle': store result in pickle file
                       'csv': store result in csv file
                       
        :param dir: full output directory path, use with 'json', 'pickle' or 'csv'
        :param filename: output file name, use with 'json', 'pickle' or 'csv'
        
        
        Return properties and methods
        """
        p = self._inspectProperties(object)
        m = self._inspectMethods(object)
        
        # store result in dictionary
        context = {}
        if item is None:
            context.update(sorted(p.items()))
            context.update(sorted(m.items()))
        else:
            for k, v in p.items():
                if k in item:
                    context[k] = v
            for k, v in m.items():
                if k in item:
                    context[k] = v
        
        # write result in sys.stdout
        if output == 'stdout':
            sys.stdout.write(str(context) + '\n')
        
        # display result in terminal
        if output == 'console':
            for key, value in sorted(context.items()):
                for tp, rep in value.items():
                    t = context[key]['type']
                    r = context[key]['repr']
                print('{:<35}'.format(key) + '{:<35}'.format(t) + r)
        
        # return dict        
        elif output == 'dict':
            return context
        
        # store result in json file
        elif output == 'json':
            file_path = join(_DIR, filename)
            with open(file_path, 'w') as outfile:
                dump(context, outfile, indent=4)
        
        # store result in pickle file
        elif output == 'pickle':
            file_path = join(_DIR, filename)
            with open(file_path, 'wb') as outfile:
                pickle.dump(context, outfile)
        
        # store result in csv file
        if output == 'csv':
            data = ''
            sep = ';'
            for key, value in sorted(context.items()):
                for tp, rep in value.items():
                    t = context[key]['type']
                    r = context[key]['repr']
                data = data + key + sep + t + sep + r + '\n'
                
            file_path = join(_DIR, filename)
            with open(file_path, 'w') as outfile:
                outfile.write(data)

    def showServiceDocs(self, object):
        """Open browser to show service documentation
        :param object:
        """
        return self.documenter.showServiceDocs(object)

    def showInterfaceDoc(self, object):
        """Open browser to show interface documentation
        :param object:
        """
        return self.documenter.showInterfaceDoc(object)

