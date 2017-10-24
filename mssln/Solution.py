import re

_SLN_HEADER_STRING = "Microsoft Visual Studio Solution File, Format Version 12.00"
_UNICODE_BOM = "\xef\xbb\xbf"

class _TextFile:
    def __init__(self,src):
        self.__src  = src
        self.__line = 0

    def readline(self):
        self.__line += 1
        return self.__src.readline()

    def get_line_number(self):
        return self.__line

    def get_filename(self):
        return self.__src.name

class SlnException:
    pass

class SlnParseException(SlnException) :
    def __init__(self,message,src):
        self.message  = message
        self.filename = src.get_filename()
        self.line     = src.get_line_number();

class ProjectInfo:
    def __init__(self,sln_uuid,name,filename,prj_uuid):
        self.sln_uuid = sln_uuid
        self.name     = name
        self.filename = filename
        self.prj_uuid = prj_uuid

class Solution:
    def __init__(self,filename=None):
        self.__buffered_line = None

        if filename is None:
            self.clear()
        else:
            self.load(filename)

    def clear(self):
        self.vars     = {}
        self.projects = []

    def load(self,filename):
        self.clear()

        with open(filename,"rt") as src:
            lsrc = _TextFile(src)

            self.__parse_header(lsrc)
            self.__parse_vars(lsrc)
            self.__parse_projects(lsrc)
#            self.__parse_global(lsrc)

            src.close();

    def __parse_header(self,src):
        line = self.__getline(src)

        if line != _SLN_HEADER_STRING:
            raise SlnParseException("invalid sln header (%s), format unsupported",src)

    def __parse_vars(self,src):
        done = False

        while not done:
            line = self.__readline(src)
            done = True

            if line is not None:
                if not line.startswith("Project(") and\
                   not line.startswith("Global"):
                    parts = line.split("=",1)

                    if len(parts) == 2:
                        self.vars[parts[0].strip()] = parts[1].strip()
                        done = False

        if line is not None:
            self.__unreadline(line)

    def __parse_projects(self,src):
        done = False

        while not done:
            line = self.__readline(src)
            done = True

            if line is not None:
                if line.startswith("Project("):
                    prj = self.__parse_project(src,line)

                    self.projects.append(prj)

                    done = False

        if line is not None:
            self.__unreadline(line)

    def __parse_project_def(self,src,line):
        def_re = 'Project\("{(.+?)}"\)\s*=\s*"(.+?)"\s*,\s*"(.+?)"\s*,\s*"{(.+?)}"'

        m = re.match(def_re,line)

        if m is None:
            raise SlnParseException("invalid project definition (%s)" % (line),src)

        return m.group(1),m.group(2),m.group(3),m.group(4)

    def __parse_project(self,src,project_def):
        sln_uuid,prj_name,prj_filename,prj_uuid = self.__parse_project_def(src,project_def)

        prj = ProjectInfo(sln_uuid,prj_name,prj_filename,prj_uuid)

        done = False

        while not done:
            line = self.__readline(src)

            if line == "EndProject":
                done = True

        return prj

    def __readline(self,src):
        if self.__buffered_line is not None:
            line = self.__buffered_line
            self.__buffered_line = None

            return line

        done = False

        while not done:
            line = src.readline()

            if line is not None:
                line = line.strip()

                if len(line) > 0 and not line.startswith("#") and not line == _UNICODE_BOM:
                    done = True
            else:
                done = True;

        return line

    def __getline(self,src):
        line = self.__readline(src)

        if line is None:
            raise SlnParseException("unexpected end of file",src)

        return line

    def __unreadline(self,line):
        if self.__buffered_line is not None:
            raise RuntimeError,"double ungetline is not supported"

        self.__buffered_line = line

