import collections
import xml.dom
import xml.dom.minidom

def _enumerate_child_elements(node):
    for child in node.childNodes:
        if child.nodeType == xml.dom.Node.ELEMENT_NODE:
            yield child

def _str_to_bool(value):
    if value == "true":
        return True
    elif value == "false":
        return False
    else:
        raise RuntimeError("invalid boolean value (%s)" % (value))

def _get_element_attr(element,attrname):
    return element.getAttribute(attrname).encode()

def _get_element_attr_opt(element,attrname,defval=None):
    if element.hasAttribute(attrname):
        return element.getAttribute(attrname).encode()
    else:
        return defval

def _get_element_text(node):
    value = ""

    for n in node.childNodes:
        if n.nodeType == xml.dom.Node.TEXT_NODE:
            value += n.data

    return value.encode()

def _node_has_children(node):
    return node.firstChild is not None

class ProjectVisitor:
    def begin_project(self,name,filename):
        return True

    def end_project(self):
        pass

    def begin_subproject(self,name,filename):
        return True

    def end_subproject(self):
        pass

    def begin_item_group(self,label,condition):
        return True

    def process_clinclude_item(self,include):
        pass

    def begin_clcompile_item(self,include):
        return True

    def process_clcompile_excluded_from_build(self,value,condition):
        pass

    def process_clcompile_additional_options(self,options,condition):
        pass

    def process_clcompile_optimization_element(self,value,condition):
        pass

    def on_unknown_clcompile_element(self,name):
        pass

    def end_clcompile_item(self):
        pass

    def on_unknown_item(self,name):
        pass

    def end_item_group(self):
        pass

    def begin_item_definition_group(self,label,condition):
        return True

    def process_clcompile_definition(self,items):
        pass

    def process_link_definition(self,items):
        pass

    def on_unknown_item_definition(self,name):
        pass

    def end_item_definition_group(self):
        pass

    def begin_property_group(self,label,condition):
        return True

    def end_property_group(self):
        pass

    def begin_import(self,project,condition):
        return None

    def end_import(self):
        pass

    def begin_import_group(self,label,condition):
        return True

    def end_import_group(self):
        pass

    def process_property(self,name,value):
        pass

    def process_project_configuration(self):
        pass

    def on_unknown_element(self,name):
        pass

class ProjectWalker:
    def __init__(self,name,filename):
        doc = xml.dom.minidom.parse(filename)

        self.name     = name
        self.filename = filename
        self.root     = doc.documentElement

    def walk(self,visitor):
        visitor.begin_project(self.name,self.filename)

        self.__walk_project(visitor)

        visitor.end_project()

    def __walk_subproject(self,visitor):
        if visitor.begin_subproject(self.name,self.filename):
            self.__walk_project(visitor)

            visitor.end_subproject()

    def __walk_project(self,visitor):
        for child in _enumerate_child_elements(self.root):
            name = child.tagName

            if   name == "ItemGroup":
                self.__walk_item_group(child,visitor)
            elif name == "ItemDefinitionGroup":
                self.__walk_item_definition_group(child,visitor)
            elif name == "PropertyGroup":
                self.__walk_property_group(child,visitor)
            elif name == "Import":
                self.__walk_import(child,visitor)
            elif name == "ImportGroup":
                self.__walk_import_group(child,visitor)
            else:
                visitor.on_unknown_element(name)

    def __walk_item_group(self,group_element,visitor):
        if visitor.begin_item_group(_get_element_attr_opt(group_element,"Label"),
                                    _get_element_attr_opt(group_element,"Condition")):
            for child in _enumerate_child_elements(group_element):
                name = child.tagName

                if name == "ProjectConfiguration":
                    visitor.process_project_configuration()
                elif name == "ClInclude":
                    self.__walk_clinclude_item(child,visitor)
                elif name == "ClCompile":
                    self.__walk_clcompile_item(child,visitor)
                else:
                    visitor.on_unknown_item(name)

        visitor.end_item_group()

    def __walk_clinclude_item(self,clinclude_element,visitor):
        for child in _enumerate_child_elements(clinclude_element):
            name = child.tagName

            if name == "ExcludedFromBuild":
                pass
            else:
                raise RuntimeError,"ClInclude element's contains unsupported subelement (%s)" % (name)

        visitor.process_clinclude_item(_get_element_attr(clinclude_element,"Include"))

    def __walk_clcompile_item(self,clcompile_element,visitor):
        if clcompile_element.hasAttribute("Condition"):
            raise RuntimeError,"unsupported Condition attribute in ClCompile element"

        if visitor.begin_clcompile_item(_get_element_attr(clcompile_element,"Include")):
            for child in _enumerate_child_elements(clcompile_element):
                name = child.tagName

                if name == "ExcludedFromBuild":
                    text = _get_element_text(child).strip()
                    if text=="":
                        value = False
                    else:
                        value = _str_to_bool(text)
                    visitor.process_clcompile_excluded_from_build(value,_get_element_attr(child,"Condition"))
                elif name == "AdditionalOptions":
                    visitor.process_clcompile_additional_options(_get_element_text(child),_get_element_attr(child,"Condition"))
                elif name == "Optimization":
                    visitor.process_clcompile_optimization_element(_get_element_text(child),_get_element_attr(child,"Condition"))
                else:
                    visitor.on_unknown_clcompile_element(name)

            visitor.end_clcompile_item()

    def __walk_item_definition_group(self,group_element,visitor):
        if visitor.begin_item_definition_group(_get_element_attr_opt(group_element,"Label"),
                                               _get_element_attr_opt(group_element,"Condition")):
            for child in _enumerate_child_elements(group_element):
                name = child.tagName

                if name == "ClCompile":
                    self.__walk_clcompile_definition(child,visitor)
                elif name == "Link":
                    self.__walk_link_definition(child,visitor)
                else:
                    visitor.on_unknown_item_definition(name)

        visitor.end_item_definition_group()

    def __walk_clcompile_definition(self,clcompile_element,visitor):
        if (clcompile_element.attributes is not None) and (len(clcompile_element.attributes) > 0):
            raise RuntimeError,"unexpected attribute in ClCompile definition"

        items = []

        for child in _enumerate_child_elements(clcompile_element):
            items.append((child.tagName,_get_element_text(child)))

        visitor.process_clcompile_definition(items)

    def __walk_link_definition(self,link_element,visitor):
        if (link_element.attributes is not None) and (len(link_element.attributes) > 0):
            raise RuntimeError,"unexpected attribute in Link definition"

        items = []

        for child in _enumerate_child_elements(link_element):
            items.append((child.tagName,_get_element_text(child)))

        visitor.process_link_definition(items)

    def __walk_property_group(self,group_element,visitor):
        if visitor.begin_property_group(_get_element_attr_opt(group_element,"Label"),
                                        _get_element_attr_opt(group_element,"Condition")):
            for child in _enumerate_child_elements(group_element):
                name  = child.tagName
                value = _get_element_text(child)

                visitor.process_property(name,value)

            visitor.end_property_group()

    def __walk_import_group(self,group_element,visitor):
        if visitor.begin_import_group(_get_element_attr_opt(group_element,"Label"),
                                      _get_element_attr_opt(group_element,"Condition")):
            for child in _enumerate_child_elements(group_element):
                if child.tagName == "Import":
                    self.__walk_import(child,visitor)
                else:
                    raise RuntimeError,"invalid element (%s) in <ImportGroup>" % (child.tagName)

            visitor.end_import_group()

    def __walk_import(self,import_element,visitor):
        project_name = _get_element_attr(import_element,"Project")
        import_filename = visitor.begin_import(project_name,_get_element_attr_opt(import_element,"Condition"))

        if import_filename is not None:
            if type(import_filename) is list or type(import_filename) is tuple:
                projs = import_filename
            else:
                projs = [ import_filename ]

            for proj in projs:
                subprj = ProjectWalker(project_name,proj)

                subprj.__walk_subproject(visitor)

            visitor.end_import()

