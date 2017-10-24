#!/usr/bin/python

"""
Convert Microsoft project(s) solution file converter to cmake.
The tool designed to convert Microsoft Visual Studio .sln files with Linux C++ projects to cmake compatible file tree.
You can customize operation by overwriting Setup object with your methods.
"""

import sys
import re
import os
import os.path
import traceback

__author__  = "OpenLab: https://github.com/openlab-vn-ua"
__license__ = "MIT"
__version__ = "1.0.5"

if os.path.exists('sln2cmake_config_user.py'):
    # use sln2cmake_config_user if it exists
    from sln2cmake_config_user import Setup
elif os.path.exists('../sln2cmake_config_user.py'):
    # use ../sln2cmake_config_user if it exists
    import imp
    SetupMod = imp.load_source('sln2cmake_config_user', '../sln2cmake_config_user.py')
    Setup = SetupMod.Setup
else:
    # import empty setup file
    from sln2cmake_config import Setup

from mssln.Solution import Solution
from mssln.ProjectWalker import ProjectWalker,ProjectVisitor
from mssln.Evaluator import Environment,evaluate_expression,substitute_vars

FPIC_OPTION_GCC="-fpic"

IGNORED_PROJECTS = [] if Setup.get_ignored_projects() == None else Setup.get_ignored_projects()

INSTALL_SUBDIR_SHARED_LIB = "lib"
INSTALL_SUBDIR_STATIC_LIB = "static_lib"
INSTALL_SUBDIR_EXECUTABLE = "bin"

PLATFORM_LIST      = ( "x64","ARM" )
CONFIGURATION_LIST = ( "Debug", "Release" )

MAIN_CMAKELISTS_FILE_HEADER = """
cmake_minimum_required (VERSION 3.0)

project (TheProject)

set(CMAKE_INSTALL_PREFIX "")

if (CMAKE_SYSTEM_PROCESSOR MATCHES "(arm)")
set (ARM 1)
else()
set (X86 1)
endif()

"""+Setup.cmake_root_get_after_head_section()+"""

set(CMAKE_C_FLAGS "-std=c11")
set(CMAKE_CXX_FLAGS "-std=c++11")

set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -Wall")
set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -fthreadsafe-statics")

set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wall")
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -fthreadsafe-statics")

set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -fexceptions")
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -frtti")

set(CMAKE_C_FLAGS_DEBUG "-g2 -gdwarf-2")
set(CMAKE_C_FLAGS_DEBUG "${CMAKE_C_FLAGS_DEBUG} -O0")
set(CMAKE_C_FLAGS_DEBUG "${CMAKE_C_FLAGS_DEBUG} -fno-strict-aliasing")
set(CMAKE_C_FLAGS_DEBUG "${CMAKE_C_FLAGS_DEBUG} -fno-omit-frame-pointer")

set(CMAKE_CXX_FLAGS_DEBUG "${CMAKE_CXX_FLAGS_DEBUG} -g2 -gdwarf-2")
set(CMAKE_CXX_FLAGS_DEBUG "${CMAKE_CXX_FLAGS_DEBUG} -O0")
set(CMAKE_CXX_FLAGS_DEBUG "${CMAKE_CXX_FLAGS_DEBUG} -fno-strict-aliasing")
set(CMAKE_CXX_FLAGS_DEBUG "${CMAKE_CXX_FLAGS_DEBUG} -fno-omit-frame-pointer")

set(CMAKE_C_FLAGS_RELEASE "-g1")
set(CMAKE_C_FLAGS_RELEASE "${CMAKE_C_FLAGS_RELEASE} -O3")
set(CMAKE_C_FLAGS_RELEASE "${CMAKE_C_FLAGS_RELEASE} -fno-strict-aliasing")
set(CMAKE_C_FLAGS_RELEASE "${CMAKE_C_FLAGS_RELEASE} -fomit-frame-pointer")

set(CMAKE_CXX_FLAGS_RELEASE "-g1")
set(CMAKE_CXX_FLAGS_RELEASE "${CMAKE_CXX_FLAGS_RELEASE} -O3")
set(CMAKE_CXX_FLAGS_RELEASE "${CMAKE_CXX_FLAGS_RELEASE} -fno-strict-aliasing")
set(CMAKE_CXX_FLAGS_RELEASE "${CMAKE_CXX_FLAGS_RELEASE} -fomit-frame-pointer")

set(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} -Wl,--no-undefined -Wl,-z,relro -Wl,-z,now -Wl,-z,noexecstack")
set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} -Wl,--no-undefined -Wl,-z,relro -Wl,-z,now -Wl,-z,noexecstack")

"""

def get_file_list_by_mask(mask):
    star_index = mask.find('*')

    if star_index < 0:
        return [mask]

    full_prefix = mask[:star_index]
    dir_prefix  = os.path.dirname(full_prefix)
    name_prefix = os.path.basename(full_prefix)
    name_suffix = mask[star_index + 1:]

    if len(dir_prefix) == 0:
        dir_prefix = "."

    result = []

    for name in os.listdir(dir_prefix):
        if name.startswith(name_prefix) and name.endswith(name_suffix):
            if len(name) >= len(name_prefix) + len(name_suffix):
                result.append(os.path.join(dir_prefix,name))

    return result

def split_string_normalized(s,separator=';'):
    return filter(lambda y : len(y) > 0,map(lambda x : x.strip(),s.split(separator)))

def path_normalize_slashes(path):
    skip   = True
    result = ""

    for c in path:
        if c == '/' or c == '\\':
            if not skip:
                skip = True
                result += '/'
        else:
            skip    = False
            result += c

    if result.endswith('/'):
        return result[:-1]
    else:
        return result

class UserData:
      # just empty class 
      pass

class CMakeProjectInfo:
    def __init__(self):
        self.project_name                   = None
        self.project_filename               = None
        self.configuration_type             = None
        self.compile_items                  = []
        self.library_dependencies           = []
        self.additional_library_directories = []
        self.include_dirs                   = []
        self.defines                        = []
        self.project_master_path            = None
        self.additional_compile_options     = []
        self.compile_pic                    = False
        self.additional_link_options        = []
        self.user_load_data                 = UserData()

class CompileItem:
    def __init__(self,include=None):
        self.include     = include
        self.add_options = []

class LibraryDependencyItem:
    def __init__(self,name):
        self.name = name

class MetaSubEnvironment(Environment):
    def __init__(self,name,parent,initial_vars = None):
        Environment.__init__(self,initial_vars)

        self.name   = name
        self.parent = parent

    def set_var(self,name,value):
        self.parent.set_var(name,value)

    def get_var(self,name):
        return self.parent.get_var(name)

    def set_meta_var(self,name,value):
        self.meta[name] = value

    def get_meta_var(self,name):
        if self.meta.has_key(name):
            return self.meta[name]
        else:
            return self.parent.get_meta_var(name)

class CMakeGeneratorEnvironment(Environment):
    def __init__(self,initital_vars):
        Environment.__init__(self,initital_vars)

        self.clcompile_env = MetaSubEnvironment("ClCompile",self)
        self.link_env      = MetaSubEnvironment("Link",self)

    def set_var(self,name,value):
        if name == "RemoteRootDir":
            # ignore RemoteRootDir setup - it should be filled already
            pass
        else:
            Environment.set_var(self,name,value)

    def set_visitor(self,visitor):
        self.visitor = visitor

    def get_undefined_var(self,name):
        if name == "MSBuildThisFileName":
            return os.path.splitext(os.path.basename(self.visitor.get_current_filename()))[0]
        elif name == "MSBuildProjectFile":
            return os.path.basename(self.visitor.get_project_filename())
        elif name == "MSBuildProjectName":
            return self.visitor.get_project_name()
        else:
            print "warning: access to undefined variable %s" % (name)
            return ""

class CMakeGeneratorVisitor(ProjectVisitor):
    def __init__(self,env):
        self.env = env
        self.compile_items = []
        self.curr_compile_item = None
        self.project_info = CMakeProjectInfo()
        self.user_load_data = UserData()

        self.ignored_imports_list = []
        self.import_projects_stack = []

        Setup.on_load_init(self)

    def get_current_filename(self):
        return self.import_projects_stack[-1]

    def get_project_name(self):
        return self.project_name

    def get_project_filename(self):
        return self.import_projects_stack[0]

    def add_ignored_import(self,ignored_re):
        self.ignored_imports_list.append(ignored_re)

    def begin_project(self,name,filename):
        print "parsing ",name,"(%s)..." % (filename)

        self.project_name = name
        self.import_projects_stack.append(filename)

        self.project_info.project_name     = name
        self.project_info.project_filename = filename

        return True

    def end_project(self):
        self.project_info.compile_items = self.compile_items
        self.project_info.library_dependencies = map(lambda x : LibraryDependencyItem(x),split_string_normalized(self.env.link_env.get_meta_var("LibraryDependencies")))
        self.project_info.additional_library_directories = split_string_normalized(self.env.link_env.get_meta_var("AdditionalLibraryDirectories"))
        self.project_info.include_dirs = map(lambda x : path_normalize_slashes(x),split_string_normalized(self.env.get_var("IncludePath")))
        self.project_info.defines      = split_string_normalized(self.env.clcompile_env.get_meta_var("PreprocessorDefinitions"))
        self.project_info.configuration_type = self.env.get_var("ConfigurationType")
        self.project_info.project_master_path = self.env.get_var("ProjectMasterPath")
        self.project_info.user_load_data = self.user_load_data
        self.project_info.additional_compile_options = split_string_normalized(self.env.clcompile_env.get_meta_var("AdditionalOptions"),None)
        self.project_info.compile_pic            = self.env.clcompile_env.get_meta_var("PositionIndependentCode") == "true"
        self.project_info.additional_link_options = split_string_normalized(self.env.link_env.get_meta_var("AdditionalOptions"),None)
        self.project_info.project_name = self.env.get_var("TargetName")
        self.project_info.c_additional_warning_default = split_string_normalized(self.env.get_var("CAdditionalWarningDefault"))
        self.project_info.cpp_additional_warning_default = split_string_normalized(self.env.get_var("CppAdditionalWarningDefault"))
        self.project_info.c_additional_warning = split_string_normalized(self.env.clcompile_env.get_meta_var("CAdditionalWarning"))
        self.project_info.cpp_additional_warning = split_string_normalized(self.env.clcompile_env.get_meta_var("CppAdditionalWarning"))

        if self.project_info.project_name.startswith("lib"):
            self.project_info.project_name = self.project_info.project_name[3:]

        Setup.on_load_done(self, self.project_info)

    def begin_item_group(self,label,condition):
        if condition is not None:
            return evaluate_expression(condition,self.env)
        else:
            return True

    def begin_clcompile_item(self,include):
        include_value = evaluate_expression(include,self.env)
        self.curr_compile_item = CompileItem(include_value)

        return True

    def end_clcompile_item(self):
        if self.curr_compile_item is not None:
            self.compile_items.append(self.curr_compile_item)

            self.curr_compile_item = None

    def process_clcompile_excluded_from_build(self,value,condition):
        if value:
            if condition is not None:
                if evaluate_expression(condition,self.env):
                    self.curr_compile_item = None
            else:
                self.curr_compile_item = None

    def process_clcompile_additional_options(self,options,condition):
        if self.curr_compile_item is None:
            return

        if condition is not None:
            if not evaluate_expression(condition,self.env):
                return

        evaluated_options = substitute_vars(options,self.env)

        self.curr_compile_item.add_options.append(evaluated_options)

    def process_clcompile_optimization_element(self,value,condition):
        if self.curr_compile_item is None:
            return

        if condition is not None:
            if not evaluate_expression(condition,self.env):
                return

        evaluated_value = evaluate_expression(value,self.env)

        if evaluated_value == "Disabled":
            self.curr_compile_item.add_options.append("-O0")
        else:
            raise RuntimeError,"unsupported optimization value (%s) in project file" % (evaluated_value)

    def on_unknown_clcompile_element(self,name):
        print "warning: unknown ClCompile element - ",name

    def begin_property_group(self,label,condition):
        if condition is not None:
            if not evaluate_expression(condition,self.env):
                return False
        return True

    def process_property(self,name,value):
        self.env.set_var(name,evaluate_expression(value,self.env))

    def begin_item_definition_group(self,label,condition):
        if condition is not None:
            return evaluate_expression(condition,self.env)
        else:
            return True

    def process_clcompile_definition(self,items):
        for item in items:
            self.env.clcompile_env.set_meta_var(item[0],evaluate_expression(item[1],self.env.clcompile_env))

    def process_link_definition(self,items):
        for item in items:
            self.env.link_env.set_meta_var(item[0],evaluate_expression(item[1],self.env.link_env))

    def begin_import_group(self,label,condition):
        if condition is not None:
            return evaluate_expression(condition,self.env)
        else:
            return True

    def end_import_group(self):
        pass

    def begin_subproject(self,name,filename):
        print "including file",name,"(%s)..." % (filename)
        self.import_projects_stack.append(filename)

        return True

    def end_subproject(self):
        self.import_projects_stack = self.import_projects_stack[:-1]

    def begin_import(self,project,condition):
        ignore = False if condition is None else evaluate_expression(condition,self.env)

        if ignore:
            return None

        filename = evaluate_expression(project,self.env)

        if self._is_in_ignored_imports_list(filename):
            return None

        star_index = filename.find('*')

        if not os.path.isabs(filename):
            filename = os.path.join(os.path.dirname(self.import_projects_stack[-1]),filename)

        if star_index >= 0:
            filename_list = filter(lambda x : not self._is_in_ignored_imports_list(x),get_file_list_by_mask(filename))
            Setup.on_load_import_file_list(self, filename_list)
            return filename_list
        else:
            Setup.on_load_import_file_list(self, [ filename ])
            return filename

    def end_import(self):
        pass

    def end_item_group(self):
        pass

    def on_unknown_item(self,name):
        print "warning: unknown item - ",name

    def on_unknown_element(self,name):
        print "warning: unknown element - ",name

    def on_unknown_item_definition(self,name):
        print "unknown item definition - ",name

    def _is_in_ignored_imports_list(self,import_name):
        for rexpr in self.ignored_imports_list:
            if re.match(rexpr,import_name):
                return True
        return False

def make_path(path):
    path = path_normalize_slashes(path)
    subdirs = path.split('/')
    currdir = subdirs[0]

    if not os.path.exists(currdir):
        os.mkdir(currdir)

    for subdir in subdirs[1:]:
        currdir = os.path.join(currdir,subdir)

        if not os.path.exists(currdir):
            os.mkdir(currdir)

def cmake_get_var_name_sources(project):
    return project.project_name.upper() + "_SRCS"

def cmake_get_var_name_libs(project):
    return project.project_name.upper() + "_LIBS"

def cmake_get_var_name_incdirs(project):
    return project.project_name.upper() + "_CPPPATH"

def cmake_get_var_name_defines(project):
    return project.project_name.upper() + "_DEFINES"

def cmake_generate_sources_list(cmake_file,project):
    var_name_sources = cmake_get_var_name_sources(project)

    cmake_file.write("set(%s\n" % (var_name_sources))

    for compile_item in project.compile_items:
        cmake_file.write("%s\n" % (path_normalize_slashes(compile_item.include)))

    cmake_file.write(")\n\n")

def cmake_generate_library_dependencies_list(cmake_file,project):
    if len(project.library_dependencies) > 0:
        var_name_libs = cmake_get_var_name_libs(project)

        cmake_file.write("set(%s\n" % (var_name_libs))

        for lib in project.library_dependencies:
            cmake_file.write("%s\n" % (lib.name))

        cmake_file.write(")\n\n")

def cmake_generate_include_dirs_list(cmake_file,project):
    if len(project.include_dirs) > 0:
        var_name_cpppath = cmake_get_var_name_incdirs(project)

        cmake_file.write("set(%s\n" % (var_name_cpppath))

        for include_dir in project.include_dirs:
            cmake_file.write("%s\n" % (path_normalize_slashes(include_dir)))

        cmake_file.write(")\n\n")

def cmake_generate_defines_list(cmake_file,project):
    if len(project.defines) > 0:
        var_name_defines = cmake_get_var_name_defines(project)

        cmake_file.write("set(%s\n" % (var_name_defines))

        for define in project.defines:
            cmake_file.write("%s\n" % (define))

        cmake_file.write(")\n\n")

def cmake_generate_compile_options_section(cmake_file,project):
#    if len(project.additional_compile_options) > 0 or project.compile_pic:
    target_name = project.project_name
    options = project.additional_compile_options[:]

    if project.compile_pic:
        options.append(FPIC_OPTION_GCC)

    options.extend(map(lambda x : "-W" + x,project.cpp_additional_warning_default))
    options.extend(map(lambda x : "-W" + x,project.cpp_additional_warning))

    if len(options) > 0:
        cmake_file.write("target_compile_options(%s PRIVATE %s)\n\n" % (target_name,";".join(options)))

    for compile_item in project.compile_items:
        if len(compile_item.add_options) > 0:
            cmake_file.write("set_source_files_properties(%s PROPERTIES COMPILE_FLAGS \"%s\")\n\n" %\
             (path_normalize_slashes(compile_item.include)," ".join(compile_item.add_options)))

def cmake_generate_link_options_section(cmake_file,project):
    if len(project.additional_link_options) > 0 or len(project.additional_library_directories) > 0:
        target_name = project.project_name

        link_opts = " ".join(project.additional_link_options) +\
                    " ".join(map(lambda x : "-L" + path_normalize_slashes(x),project.additional_library_directories))

        cmake_file.write("set_target_properties(%s PROPERTIES LINK_FLAGS \"%s\")\n\n" % (target_name,link_opts))

#    if len(project.additional_link_options) > 0:
#        cmake_file.write("set_target_properties(%s PROPERTIES LINK_FLAGS \"%s\")\n\n" % (target_name," ".join(project.additional_link_options)))
#
#    if len(project.additional_library_directories) > 0:
#        cmake_file.write("set_target_properties(%s PROPERTIES LINK_FLAGS \"%s\")\n\n" %\
#         (target_name," ".join(map(lambda x : "-L" + path_normalize_slashes(x),project.additional_library_directories))))

def cmake_generate_target_section(cmake_file,project):
    target_name = project.project_name
    if project.configuration_type == "StaticLibrary":
        cmake_file.write("add_library(%s STATIC ${%s})\n" % (target_name,cmake_get_var_name_sources(project)))
    elif project.configuration_type == "DynamicLibrary":
        cmake_file.write("add_library(%s SHARED ${%s})\n" % (target_name,cmake_get_var_name_sources(project)))
    else: # executable
        cmake_file.write("add_executable(%s ${%s})\n" % (target_name,cmake_get_var_name_sources(project)))

    if len(project.library_dependencies) > 0:
        cmake_file.write("target_link_libraries(%s LINK_PRIVATE ${%s})\n" % (target_name,cmake_get_var_name_libs(project)))

    if len(project.include_dirs) > 0:
        cmake_file.write("target_include_directories(%s PRIVATE ${%s})\n" % (target_name,cmake_get_var_name_incdirs(project)))

    if len(project.defines) > 0:
        cmake_file.write("target_compile_definitions(%s PRIVATE ${%s})\n" % (target_name,cmake_get_var_name_defines(project)))

    cmake_file.write("\n")

def get_install_mode_by_configuration_type(conf_type):
    if conf_type == "StaticLibrary":
        return "ARCHIVE"
    elif conf_type == "DynamicLibrary":
        return "LIBRARY"
    else:
        return "RUNTIME"

def get_install_subdir_by_configuration_type(conf_type):
    if conf_type == "StaticLibrary":
        return INSTALL_SUBDIR_STATIC_LIB
    elif conf_type == "DynamicLibrary":
        return INSTALL_SUBDIR_SHARED_LIB
    else:
        return INSTALL_SUBDIR_EXECUTABLE

def cmake_generate_install_section(cmake_file,project):
    target_name = project.project_name
    conf_type   = project.configuration_type

    cmake_file.write("install(TARGETS %s\n" % (target_name))
    cmake_file.write("        %s DESTINATION %s)\n\n" %\
                     (get_install_mode_by_configuration_type(conf_type),
                      get_install_subdir_by_configuration_type(conf_type)))

def path_remove_trailing_twodots_entries(path):
    while (path.startswith("../") or path.startswith("..\\")):
        path = path[3:]

    return path

def format_dest_project_dir(project,dest_base_dir):
    filename = path_remove_trailing_twodots_entries(project.project_filename)

    return os.path.join(dest_base_dir,os.path.dirname(filename))

def format_project_cmake_filename(project_name,platform,configuration):
    return project_name + "-" + platform + "-" + configuration + ".cmake"

def generate_cmake_for_project(project,dest_base_dir):
    print "Project name: %s project file name: %s" % (project.project_name,project.project_filename)
    destdir = format_dest_project_dir(project,dest_base_dir)

    make_path(destdir)

    project_cmake_filename = os.path.join(destdir,format_project_cmake_filename(project.project_name,project.platform,project.configuration))

    with open(project_cmake_filename,"wt") as cmake_file:

        Setup.cmake_generate_begin(cmake_file,project)
        cmake_generate_sources_list(cmake_file,project)
        cmake_generate_library_dependencies_list(cmake_file,project)
        cmake_generate_include_dirs_list(cmake_file,project)
        cmake_generate_defines_list(cmake_file,project)
        cmake_generate_target_section(cmake_file,project)
        cmake_generate_compile_options_section(cmake_file,project)
        cmake_generate_link_options_section(cmake_file,project)
        cmake_generate_install_section(cmake_file,project)
        Setup.cmake_generate_end(cmake_file,project)

        cmake_file.close()

def format_include_list(project_names,platform,configuration):
    return "\n".join(map(lambda x : "    include (%s)" % (format_project_cmake_filename(x,platform,configuration)),project_names)) + "\n"

def generate_cmakelists(project_packs,dest_base_dir):
    project_dirs = {}

    for project_pack in project_packs:
        project_dest_dir = format_dest_project_dir(project_pack[0],dest_base_dir)

        if project_dirs.has_key(project_dest_dir):
            project_dirs[project_dest_dir].append(project_pack)
        else:
            project_dirs[project_dest_dir] = [project_pack]

    for project_dir,project_pack_list in project_dirs.iteritems():
        with open(os.path.join(project_dir,"CMakeLists.txt"),"wt") as cmakelists_file:
            project_names = map(lambda x : x[0].project_name,project_pack_list)

            cmakelists_file.write("if (CMAKE_BUILD_TYPE STREQUAL \"Release\")\n")
            cmakelists_file.write("  if (CMAKE_SYSTEM_PROCESSOR MATCHES \"(arm)\")\n")
            cmakelists_file.write(format_include_list(project_names,"ARM","Release"))
            cmakelists_file.write("  else()\n")
            cmakelists_file.write(format_include_list(project_names,"x64","Release"))
            cmakelists_file.write("  endif()\n")
            cmakelists_file.write("else()\n")
            cmakelists_file.write("  if (CMAKE_SYSTEM_PROCESSOR MATCHES \"(arm)\")\n")
            cmakelists_file.write(format_include_list(project_names,"ARM","Debug"))
            cmakelists_file.write("  else()\n")
            cmakelists_file.write(format_include_list(project_names,"x64","Debug"))
            cmakelists_file.write("  endif()\n")
            cmakelists_file.write("endif()\n")

            cmakelists_file.close()

    with open(os.path.join(dest_base_dir,"CMakeLists.txt"),"wt") as main_file:
        main_file.write(MAIN_CMAKELISTS_FILE_HEADER)

        for project_dir in project_dirs.iterkeys():
            main_file.write("add_subdirectory(%s)\n" % (path_remove_trailing_twodots_entries(path_normalize_slashes(os.path.dirname(project_dirs[project_dir][0][0].project_filename)))))

        main_file.close()

INIT_ENV = { "VCTargetsPath" : "" }

def convert_sln_to_cmakes(args):
    sln_filename = args.sln_filename
    remote_root_dir = args.root_dir
    solution = Solution(sln_filename)
    dest_base_dir = args.dest_dir if os.path.isabs(args.dest_dir) else os.path.normpath(args.dest_dir)

    if os.path.exists(dest_base_dir):
        raise RuntimeError,"destination directory (%s) already exists" % (dest_base_dir)

    project_packs = []

    for project in solution.projects:
        if project.filename == project.name:
            pass # it's forward reference???
        elif project.name in IGNORED_PROJECTS:
            print "note: project %s is ignored (by ignored list)" % (project.name)
            pass # it's not used and have strange "ExcludedFromBuild" value in .vcxproj
        else:
            project_filename = os.path.normpath(os.path.join(os.path.dirname(sln_filename),path_normalize_slashes(project.filename)))

            project_pack = []

            for configuration in CONFIGURATION_LIST:
                for platform in PLATFORM_LIST:
                    walker  = ProjectWalker(project.name,project_filename)
                    env_dict = dict(INIT_ENV)
                    env_dict["RemoteRootDir"] = remote_root_dir

                    env     = CMakeGeneratorEnvironment(env_dict)
                    visitor = CMakeGeneratorVisitor(env)

                    env.set_visitor(visitor)

                    visitor.add_ignored_import(r"^\\Microsoft.Cpp.Default.props$")
                    visitor.add_ignored_import(r"^\\Microsoft.Cpp.props$")
                    visitor.add_ignored_import(r"^\\Microsoft.Cpp.targets$")

                    env.set_var("Platform",platform)
                    env.set_var("Configuration",configuration)
                    env.set_var("LinkAdditionalOptionsLinuxStub","")
                    env.set_var("IncludePath","")
                    env.set_var("ISenseIncludePath","")
                    env.set_var("TargetName",project.name)

                    env.set_meta_var("PreprocessorDefinitions","")
                    env.set_meta_var("CAdditionalWarning","")
                    env.set_meta_var("CppAdditionalWarning","")
                    env.set_meta_var("AdditionalOptions","")
                    env.set_meta_var("AdditionalLibraryDirectories","")
                    env.set_meta_var("AdditionalIncludeDirectories","")

                    walker.walk(visitor)

                    visitor.project_info.platform      = platform
                    visitor.project_info.configuration = configuration

                    project_pack.append(visitor.project_info)

            project_packs.append(project_pack)

    for project_pack in project_packs:
        for project in project_pack:
            Setup.proc_project_custom_params(project)

    for project_pack in project_packs:
        for project in project_pack:
            generate_cmake_for_project(project,dest_base_dir)

    generate_cmakelists(project_packs,dest_base_dir)

class Arguments:
    def __init__(self):
        self.sln_filename = None
        self.dest_dir     = None
        self.root_dir     = None

    def parse_command_line(self,args):
        if len(args) != 3:
            raise RuntimeError,"root dir, .sln file name and dest dir parameters required"

        self.root_dir     = args[0]
        self.sln_filename = args[1]
        self.dest_dir     = args[2]

def main():
    args = Arguments()
    args.parse_command_line(sys.argv[1:])

    try:
        convert_sln_to_cmakes(args)
    except RuntimeError,e:
        print e
        # traceback.print_exc()

main()

