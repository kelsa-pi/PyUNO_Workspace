# -*- coding: utf-8 -*-
# !/usr/bin/env python

import uno


def MyMacro(*args):

    try:
        ctx = remote_ctx                   # use in development
    except:
        ctx = uno.getComponentContext()    # use in production

    # get desktop
    desktop = ctx.getByName("/singletons/com.sun.star.frame.theDesktop")
    # get document
    document = desktop.getCurrentComponent()
    # access the document's text property
    text = document.Text
    # create a cursor
    cursor = text.createTextCursor()
    # insert the text into the document
    text.insertString(cursor, "Hello World", 0)
    

# Execute macro from LibreOffice UI (Tools - Macro)
g_exportedScripts = MyMacro,

# Execute macro from IDE
if __name__ == "__main__":
    """ Connect to LibreOffice proccess.
    
    Start the office in shell with command:
    soffice "--accept=socket,host=localhost,port=2002;urp;StarOffice.ComponentContext" --norestore
    """
    
    local_ctx= uno.getComponentContext()
    resolver = local_ctx.ServiceManager.createInstance("com.sun.star.bridge.UnoUrlResolver")
    try:
        remote_ctx = resolver.resolve("uno:socket,"
                                      "host=localhost,"
                                      "port=2002;"
                                      "urp;"
                                      "StarOffice.ComponentContext")
    except Exception as err:
        print(err)

    MyMacro()
